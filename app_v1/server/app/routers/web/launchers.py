from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import LauncherSessionView, UserData
from app.service.management_service import ManagementService
from app.user_auth.utils.auth_wrapper import require_roles

router = APIRouter(prefix="/launchers", tags=["web-launchers"])


@router.get("", response_model=list[LauncherSessionView])
async def api_list_launchers(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> list[LauncherSessionView]:
    return await ManagementService.list_launchers(db, current_user, user_id)


@router.get("/{launcher_id}", response_model=LauncherSessionView)
async def api_get_launcher(
    launcher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> LauncherSessionView:
    launcher = await ManagementService.get_launcher(db, current_user, launcher_id)
    if launcher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Launcher not found")
    return launcher
