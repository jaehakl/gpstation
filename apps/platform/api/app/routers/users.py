from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from models import UserAdminUpdate, UserData
from service.user_service import UserService, user_to_data
from user_auth.routes import auth_cookie_kwargs, get_db
from user_auth.utils.auth_wrapper import require_roles

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserData)
async def api_get_me(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user", "unauthorized"])),
):
    user = await UserService.get_user(db, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_to_data(user)


@router.get("/users", response_model=list[UserData])
async def api_get_users(
    limit: int | None = 100,
    offset: int | None = 0,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin"])),
):
    return await UserService.list_users(db, limit, offset)


@router.get("/users/{user_id}", response_model=UserData)
async def api_get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user", "unauthorized"])),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    user = await UserService.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_to_data(user)


@router.patch("/users/{user_id}", response_model=UserData)
async def api_update_user(
    user_id: str,
    payload: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin"])),
):
    try:
        user = await UserService.update_user(db, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/users/{user_id}")
async def api_delete_user(
    user_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user", "unauthorized"])),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    deleted = await UserService.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.id == user_id:
        kwargs = auth_cookie_kwargs()
        response.delete_cookie("access_token", path="/", **kwargs)
        response.delete_cookie("refresh_token", path="/", **kwargs)

    return {"ok": True}
