from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AccessKey
from app.models import AccessKeyCreate, AccessKeyCreateResult, AccessKeyData
from app.user_auth.db import User
from app.user_auth.utils.auth_utils import hash_token, random_urlsafe

ACCESS_KEY_PREFIX = "gpsk_"
ACCESS_KEY_TYPE = "user_api"
ACCESS_KEY_DISPLAY_PREFIX_LENGTH = 16
ALLOWED_ACCESS_KEY_SCOPES = {"client", "launcher"}


def access_key_to_data(access_key: AccessKey) -> AccessKeyData:
    return AccessKeyData(
        id=str(access_key.id),
        user_id=str(access_key.user_id),
        key_type=access_key.key_type,
        name=access_key.name,
        key_prefix=access_key.key_prefix,
        scopes=[str(item) for item in (access_key.scopes or [])],
        status=access_key.status,
        last_used_at=access_key.last_used_at,
        expires_at=access_key.expires_at,
        created_at=access_key.created_at,
        revoked_at=access_key.revoked_at,
    )


def make_access_key_secret() -> str:
    return f"{ACCESS_KEY_PREFIX}{random_urlsafe(48)}"


def normalize_optional_datetime(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class AccessKeyService:
    @staticmethod
    async def create_user_access_key(
        db: AsyncSession,
        user_id: str,
        payload: AccessKeyCreate,
    ) -> AccessKeyCreateResult:
        user = await db.get(User, user_id)
        if user is None:
            raise ValueError("User not found")
        if user.status != "active" or user.role not in {"admin", "user"}:
            raise ValueError("Access Tokens require an active admin or user account")

        name = payload.name.strip()
        if not name:
            raise ValueError("Access Token name is required")
        scopes = list(dict.fromkeys(payload.scopes or []))
        if not scopes:
            raise ValueError("At least one scope is required")
        if any(scope not in ALLOWED_ACCESS_KEY_SCOPES for scope in scopes):
            raise ValueError("Invalid Access Token scope")

        secret = make_access_key_secret()
        access_key = AccessKey(
            user_id=user_id,
            key_type=ACCESS_KEY_TYPE,
            name=name,
            key_prefix=secret[:ACCESS_KEY_DISPLAY_PREFIX_LENGTH],
            key_hash=hash_token(secret),
            scopes=scopes,
            status="active",
            expires_at=normalize_optional_datetime(payload.expires_at),
        )
        db.add(access_key)
        await db.commit()
        await db.refresh(access_key)
        return AccessKeyCreateResult(access_key=access_key_to_data(access_key), secret=secret)
