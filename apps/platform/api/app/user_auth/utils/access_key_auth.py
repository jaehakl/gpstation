from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import AccessKey, get_db
from models import UserData
from service.access_key_service import ACCESS_KEY_PREFIX
from service.user_service import ALLOWED_USER_ROLES, user_to_data
from user_auth.db import User
from user_auth.utils.auth_utils import hash_token


def is_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def get_access_key_secret_from_authorization(auth: str) -> str:
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AccessKey required")

    secret = auth.split(" ", 1)[1].strip()
    if not secret.startswith(ACCESS_KEY_PREFIX):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid AccessKey")
    return secret


async def authenticate_access_key_secret(db: AsyncSession, secret: str) -> UserData:
    if not secret.startswith(ACCESS_KEY_PREFIX):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid AccessKey")

    access_key = await db.scalar(select(AccessKey).where(AccessKey.key_hash == hash_token(secret)))
    if access_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid AccessKey")
    if access_key.status != "active" or access_key.revoked_at is not None or is_expired(access_key.expires_at):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid AccessKey")

    user = await db.get(User, access_key.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    if user.role not in ALLOWED_USER_ROLES:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user role")

    access_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return user_to_data(user)


async def check_access_key_user(request: Request, db: AsyncSession = Depends(get_db)) -> UserData:
    auth = request.headers.get("Authorization", "")
    return await authenticate_access_key_secret(db, get_access_key_secret_from_authorization(auth))


def require_access_key_roles(allowed_roles: list[str]) -> Callable:
    async def dependency(user: UserData = Depends(check_access_key_user)) -> UserData:
        if not any(role in allowed_roles for role in user.roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return dependency
