from __future__ import annotations

import asyncio
import ipaddress
import secrets
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AccessKey, get_db
from app.user_auth.db import User
from app.user_auth.utils.auth_utils import hash_token


@dataclass(frozen=True)
class Principal:
    access_key_id: str
    user_id: str
    scopes: frozenset[str]

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def token_from_authorization(authorization: str) -> str:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    return authorization.split(" ", 1)[1].strip()


_rate_limit_lock = asyncio.Lock()
_rate_limit_requests: dict[str, deque[float]] = {}
_last_rate_limit_sweep_at = 0.0


async def authenticate_bearer_token(
    db: AsyncSession,
    token: str,
    *,
    client_ip: str | None = None,
    origin: str | None = None,
) -> Principal:
    principal = await authenticate_access_key(db, token, client_ip=client_ip, origin=origin)
    if principal is not None:
        return principal
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid AccessKey")


async def authenticate_access_key(
    db: AsyncSession,
    token: str,
    *,
    client_ip: str | None = None,
    origin: str | None = None,
) -> Principal | None:
    token_hash = hash_token(token)
    access_key = await db.scalar(select(AccessKey).where(AccessKey.key_hash == token_hash))
    if access_key is None:
        return None
    if not secrets.compare_digest(bytes(access_key.key_hash), token_hash):
        return None
    if access_key.status != "active" or access_key.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid AccessKey")
    if access_key.expires_at is not None and normalize_utc(access_key.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired AccessKey")

    user = await db.get(User, access_key.user_id)
    if user is None or user.status != "active" or user.role not in {"admin", "user"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AccessKey user inactive")

    enforce_access_key_network_policy(access_key, client_ip=client_ip, origin=origin)
    await enforce_access_key_rate_limit(access_key)

    principal = Principal(
        access_key_id=str(access_key.id),
        user_id=str(access_key.user_id),
        scopes=frozenset(access_key.scopes or []),
    )
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=60)
    if access_key.last_used_at is None or normalize_utc(access_key.last_used_at) <= cutoff:
        updated_key_id = await db.scalar(
            update(AccessKey)
            .where(
                AccessKey.id == access_key.id,
                or_(AccessKey.last_used_at.is_(None), AccessKey.last_used_at <= cutoff),
            )
            .values(last_used_at=now)
            .returning(AccessKey.id)
        )
        if updated_key_id is not None:
            access_key.last_used_at = now
            await db.commit()
        else:
            await db.rollback()
    else:
        await db.rollback()
    return principal


async def authenticate_db_authorization(
    db: AsyncSession,
    authorization: str,
    *,
    client_ip: str | None = None,
    origin: str | None = None,
) -> Principal:
    return await authenticate_bearer_token(
        db,
        token_from_authorization(authorization),
        client_ip=client_ip,
        origin=origin,
    )


async def require_client(
    request: Request,
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    principal = await authenticate_db_authorization(
        db,
        authorization,
        client_ip=request.client.host if request.client else None,
        origin=request.headers.get("origin"),
    )
    principal.require_scope("client")
    return principal


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def enforce_access_key_network_policy(access_key: AccessKey, *, client_ip: str | None, origin: str | None) -> None:
    allowed_ips = access_key.allowed_ips or []
    if allowed_ips:
        try:
            address = ipaddress.ip_address(client_ip or "")
            permitted = any(address in ipaddress.ip_network(item, strict=False) for item in allowed_ips)
        except ValueError:
            permitted = False
        if not permitted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AccessKey IP not allowed")

    allowed_origins = access_key.allowed_origins or []
    if allowed_origins and origin not in allowed_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AccessKey origin not allowed")


async def enforce_access_key_rate_limit(access_key: AccessKey) -> None:
    global _last_rate_limit_sweep_at
    limit = access_key.rate_limit_per_minute
    if limit is None:
        return
    if limit <= 0:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="AccessKey rate limit exceeded")

    now = time.monotonic()
    async with _rate_limit_lock:
        if now - _last_rate_limit_sweep_at >= 60:
            cutoff = now - 60
            for key_id, key_requests in list(_rate_limit_requests.items()):
                while key_requests and key_requests[0] <= cutoff:
                    key_requests.popleft()
                if not key_requests:
                    _rate_limit_requests.pop(key_id, None)
            _last_rate_limit_sweep_at = now
        requests = _rate_limit_requests.setdefault(str(access_key.id), deque())
        while requests and requests[0] <= now - 60:
            requests.popleft()
        if len(requests) >= limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="AccessKey rate limit exceeded")
        requests.append(now)
