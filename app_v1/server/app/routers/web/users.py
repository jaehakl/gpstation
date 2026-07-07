from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import AccessKeyCreate, AccessKeyCreateResult, AccessKeyData, OkResponse, UserAdminUpdate, UserData
from app.routers.web.auth import auth_cookie_kwargs
from app.service.access_key_service import AccessKeyService
from app.service.user_service import UserService, user_to_data
from app.user_auth.utils.auth_wrapper import require_roles

router = APIRouter(prefix="/users", tags=["web-users"])


@router.get("/me", response_model=UserData)
async def api_get_me(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user", "unauthorized"])),
) -> UserData:
    user = await UserService.get_user(db, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_to_data(user)


@router.get("", response_model=list[UserData])
async def api_get_users(
    limit: int | None = 100,
    offset: int | None = 0,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin"])),
) -> list[UserData]:
    return await UserService.list_users(db, limit, offset)


@router.get("/me/access-tokens", response_model=list[AccessKeyData])
async def api_list_my_access_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> list[AccessKeyData]:
    return await AccessKeyService.list_user_access_keys(db, current_user.id)


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


@router.delete("/me/access-tokens/{access_key_id}", response_model=OkResponse)
async def api_revoke_my_access_token(
    access_key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> OkResponse:
    revoked = await AccessKeyService.revoke_user_access_key(db, access_key_id, current_user.id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access Token not found")
    return OkResponse()


@router.get("/{user_id}", response_model=UserData)
async def api_get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user", "unauthorized"])),
) -> UserData:
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    user = await UserService.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_to_data(user)


@router.patch("/{user_id}", response_model=UserData)
async def api_update_user(
    user_id: str,
    payload: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin"])),
) -> UserData:
    try:
        user = await UserService.update_user(db, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/{user_id}", response_model=OkResponse)
async def api_delete_user(
    user_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user", "unauthorized"])),
) -> OkResponse:
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    deleted = await UserService.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.id == user_id:
        kwargs = auth_cookie_kwargs()
        response.delete_cookie("access_token", path="/", **kwargs)
        response.delete_cookie("refresh_token", path="/", **kwargs)
    return OkResponse()


@router.get("/{user_id}/access-tokens", response_model=list[AccessKeyData])
async def api_list_user_access_tokens(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin"])),
) -> list[AccessKeyData]:
    return await AccessKeyService.list_user_access_keys(db, user_id)


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


@router.delete("/{user_id}/access-tokens/{access_key_id}", response_model=OkResponse)
async def api_revoke_user_access_token(
    user_id: str,
    access_key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin"])),
) -> OkResponse:
    revoked = await AccessKeyService.revoke_user_access_key(db, access_key_id, user_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access Token not found")
    return OkResponse()
