from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import UserData
from app.routers.web.auth import check_user


async def require_crud_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserData:
    current_user = await check_user(request, db)
    if current_user.role not in {"admin", "user"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return current_user
