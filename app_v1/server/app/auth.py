from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AccessKey, get_db
from app.user_auth.db import User
from app.user_auth.utils.auth_utils import hash_token


@dataclass(frozen=True)
class Principal:
    token: str
    user_id: str
    scopes: frozenset[str]

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def token_from_authorization(authorization: str) -> str:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    return authorization.split(" ", 1)[1].strip()


async def authenticate_bearer_token(db: AsyncSession, token: str) -> Principal:
    principal = await authenticate_access_key(db, token)
    if principal is not None:
        return principal
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid AccessKey")


async def authenticate_access_key(db: AsyncSession, token: str) -> Principal | None:
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

    access_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return Principal(token=token, user_id=str(access_key.user_id), scopes=frozenset(access_key.scopes or []))


async def authenticate_db_authorization(db: AsyncSession, authorization: str) -> Principal:
    return await authenticate_bearer_token(db, token_from_authorization(authorization))


async def require_client(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    principal = await authenticate_db_authorization(db, authorization)
    principal.require_scope("client")
    return principal


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
