from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import UserData
from app.routers.web.auth import check_user


async def get_user_optional(request: Request, db: AsyncSession = Depends(get_db)) -> UserData | None:
    try:
        return await check_user(request, db)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def require_roles(allowed_roles: list[str]) -> Callable:
    allow_anonymous = "*" in allowed_roles

    async def dependency(
        user: UserData | None = Depends(get_user_optional if allow_anonymous else check_user),
    ) -> UserData | None:
        if allow_anonymous:
            return user
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        if not any(role in allowed_roles for role in user.roles):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        return user

    return dependency
