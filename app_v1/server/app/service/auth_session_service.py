from __future__ import annotations

import asyncio
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.auth_audit_service import add_auth_audit
from app.user_auth.db import OAuthState, Session as AuthSession, User
from app.user_auth.utils.auth_utils import hash_token, random_urlsafe

AUTHENTICATED_ROLES = {"admin", "user"}
REFRESH_ROTATION_GRACE_SECONDS = 10
REFRESH_ROTATION_GRACE_HASH_LIMIT = 8
OAUTH_STATE_CLEANUP_INTERVAL_SECONDS = 60
_oauth_state_cleanup_lock = asyncio.Lock()
_last_oauth_state_cleanup_at = 0.0


def can_authenticate_user(user: User | None) -> bool:
    return bool(user is not None and user.status == "active" and user.role in AUTHENTICATED_ROLES)


def create_auth_session(db: AsyncSession, user: User, request: Request, refresh_jti: str) -> str:
    session_id = random_urlsafe(32)
    client = request.client
    db.add(
        AuthSession(
            user_id=user.id,
            session_id_hash=hash_token(session_id),
            refresh_jti_hash=hash_token(refresh_jti),
            ip=client.host if client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    return session_id


async def get_active_auth_session(
    db: AsyncSession,
    session_id: str,
    *,
    for_update: bool = False,
) -> AuthSession | None:
    statement = select(AuthSession).where(AuthSession.session_id_hash == hash_token(session_id))
    if for_update:
        statement = statement.with_for_update()
    auth_session = await db.scalar(statement)
    if auth_session is None or auth_session.revoked_at is not None:
        return None
    return auth_session


async def validate_refresh_rotation(
    db: AsyncSession,
    auth_session: AuthSession,
    claims: dict,
) -> Literal["current", "grace"]:
    refresh_jti = claims.get("jti")
    presented_hash = hash_token(str(refresh_jti)) if refresh_jti else None
    if presented_hash is not None and auth_session.refresh_jti_hash is not None:
        if secrets.compare_digest(bytes(auth_session.refresh_jti_hash), presented_hash):
            return "current"
        grace_until = auth_session.refresh_grace_until
        if grace_until is not None and grace_until.tzinfo is None:
            grace_until = grace_until.replace(tzinfo=timezone.utc)
        if (
            grace_until is not None
            and grace_until > datetime.now(timezone.utc)
            and presented_hash.hex() in (auth_session.refresh_grace_jti_hashes or [])
        ):
            return "grace"

    auth_session.revoked_at = datetime.now(timezone.utc)
    add_auth_audit(
        db,
        "refresh_reuse",
        user_id=str(auth_session.user_id),
        details={"session_id": str(auth_session.id)},
    )
    await db.commit()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token reuse detected")


def rotate_refresh_jti(auth_session: AuthSession, next_refresh_jti: str) -> None:
    now = datetime.now(timezone.utc)
    grace_until = auth_session.refresh_grace_until
    if grace_until is not None and grace_until.tzinfo is None:
        grace_until = grace_until.replace(tzinfo=timezone.utc)
    grace_active = grace_until is not None and grace_until > now
    grace_hashes = list(auth_session.refresh_grace_jti_hashes or []) if grace_active else []
    if auth_session.refresh_jti_hash is not None:
        current_hash = bytes(auth_session.refresh_jti_hash).hex()
        if current_hash not in grace_hashes:
            grace_hashes.append(current_hash)
    auth_session.refresh_grace_jti_hashes = grace_hashes[-REFRESH_ROTATION_GRACE_HASH_LIMIT:]
    if not grace_active:
        auth_session.refresh_grace_until = now + timedelta(seconds=REFRESH_ROTATION_GRACE_SECONDS)
    auth_session.refresh_jti_hash = hash_token(next_refresh_jti)


async def cleanup_expired_oauth_states(db: AsyncSession, *, ttl_seconds: int) -> None:
    global _last_oauth_state_cleanup_at
    now = time.monotonic()
    if now - _last_oauth_state_cleanup_at < OAUTH_STATE_CLEANUP_INTERVAL_SECONDS:
        return
    async with _oauth_state_cleanup_lock:
        now = time.monotonic()
        if now - _last_oauth_state_cleanup_at < OAUTH_STATE_CLEANUP_INTERVAL_SECONDS:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds)
        await db.execute(delete(OAuthState).where(OAuthState.created_at < cutoff))
        _last_oauth_state_cleanup_at = now
