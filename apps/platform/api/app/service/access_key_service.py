from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import AccessKey
from models import AccessKeyCreate, AccessKeyCreateResult, AccessKeyData
from user_auth.utils.auth_utils import hash_token, random_urlsafe

ACCESS_KEY_PREFIX = "gpsk_"
ACCESS_KEY_TYPE = "user_api"
ACCESS_KEY_DISPLAY_PREFIX_LENGTH = 16


def access_key_to_data(access_key: AccessKey) -> AccessKeyData:
    return AccessKeyData(
        id=str(access_key.id),
        user_id=str(access_key.user_id),
        key_type=access_key.key_type,
        name=access_key.name,
        key_prefix=access_key.key_prefix,
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
    async def list_user_access_keys(db: AsyncSession, user_id: str) -> list[AccessKeyData]:
        stmt = (
            select(AccessKey)
            .where(AccessKey.user_id == user_id)
            .order_by(AccessKey.created_at.desc(), AccessKey.id.asc())
        )
        access_keys = (await db.execute(stmt)).scalars().all()
        return [access_key_to_data(access_key) for access_key in access_keys]

    @staticmethod
    async def create_user_access_key(
        db: AsyncSession,
        user_id: str,
        payload: AccessKeyCreate,
    ) -> AccessKeyCreateResult:
        name = payload.name.strip()
        if not name:
            raise ValueError("AccessKey name is required")

        secret = make_access_key_secret()
        access_key = AccessKey(
            user_id=user_id,
            key_type=ACCESS_KEY_TYPE,
            name=name,
            key_prefix=secret[:ACCESS_KEY_DISPLAY_PREFIX_LENGTH],
            key_hash=hash_token(secret),
            scopes=[],
            status="active",
            expires_at=normalize_optional_datetime(payload.expires_at),
            metadata_json={},
        )
        db.add(access_key)
        await db.commit()
        await db.refresh(access_key)
        return AccessKeyCreateResult(access_key=access_key_to_data(access_key), secret=secret)

    @staticmethod
    async def revoke_user_access_key(db: AsyncSession, user_id: str, access_key_id: str) -> bool:
        stmt = select(AccessKey).where(
            AccessKey.id == access_key_id,
            AccessKey.user_id == user_id,
        )
        access_key = await db.scalar(stmt)
        if access_key is None:
            return False

        access_key.status = "revoked"
        access_key.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        return True
