from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import authenticate_db_authorization
from app.db import get_db
from app.models import UserData
from app.routers.web.auth import check_user
from app.service.user_service import user_to_data
from app.user_auth.db import User


async def require_crud_user(
    request: Request,
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> UserData:
    if authorization:
        principal = await authenticate_db_authorization(db, authorization)
        principal.require_scope("client")
        user = await db.get(User, principal.user_id)
        if user is None or user.status != "active" or user.role not in {"admin", "user"}:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        return user_to_data(user)

    current_user = await check_user(request, db)
    if current_user.role not in {"admin", "user", "unauthorized"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return current_user
