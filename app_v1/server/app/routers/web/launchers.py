from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.db import get_db
from app.models import UserData
from app.service.launcher_service import LauncherService
from app.state import runtime
from app.user_auth.utils.auth_wrapper import require_roles

router = APIRouter(prefix="/launchers", tags=["web-launchers"])


class LauncherReconcileResponse(BaseModel):
    ok: bool = True
    launchers: int
    slave_sessions: int


@router.post("/reconcile-disconnected", response_model=LauncherReconcileResponse)
async def api_reconcile_disconnected_launchers(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> LauncherReconcileResponse:
    connected_launcher_ids = await runtime.get_launcher_ids()
    user_id = None if current_user.role == "admin" else current_user.id
    launchers, slave_sessions = await LauncherService.reconcile_disconnected_launchers(
        db,
        connected_launcher_ids=connected_launcher_ids,
        user_id=user_id,
    )
    return LauncherReconcileResponse(launchers=launchers, slave_sessions=slave_sessions)
