from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import AccessKeyCreate, AccessKeyCreateResult, UserData
from app.service.access_key_service import AccessKeyService
from app.user_auth.utils.auth_wrapper import require_roles

router = APIRouter(prefix="/users", tags=["web-users"])


@router.post("/me/access-tokens", response_model=AccessKeyCreateResult)
async def api_create_my_access_token(
    payload: AccessKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> AccessKeyCreateResult:
    try:
        return await AccessKeyService.create_user_access_key(db, current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{user_id}/access-tokens", response_model=AccessKeyCreateResult)
async def api_create_user_access_token(
    user_id: str,
    payload: AccessKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin"])),
) -> AccessKeyCreateResult:
    try:
        return await AccessKeyService.create_user_access_key(db, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
