from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Launcher, get_db
from app.models import OkResponse, UserData
from app.service.job_orchestrator import job_orchestrator
from app.service.launcher_service import LauncherService
from app.state import runtime
from app.user_auth.utils.auth_wrapper import require_roles

router = APIRouter(prefix="/launchers", tags=["web-launchers"])


class LauncherReconcileResponse(BaseModel):
    ok: bool = True
    launchers: int


class LauncherRuntimeData(BaseModel):
    launcher_id: str
    current_job_id: str | None = None
    loaded_slave_app_id: str | None = None
    worker_status: str | None = None
    resetting: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/reconcile-disconnected", response_model=LauncherReconcileResponse)
async def api_reconcile_disconnected_launchers(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> LauncherReconcileResponse:
    connected_launcher_ids = await runtime.get_launcher_ids()
    user_id = None if current_user.role == "admin" else current_user.id
    launchers = await job_orchestrator.reconcile_disconnected_launchers(
        db,
        connected_launcher_ids=connected_launcher_ids,
        user_id=user_id,
    )
    return LauncherReconcileResponse(launchers=launchers)


@router.get("/runtime", response_model=list[LauncherRuntimeData])
async def api_list_launcher_runtime(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> list[LauncherRuntimeData]:
    snapshots = await runtime.launcher_snapshots()
    if not snapshots:
        return []
    stmt = select(Launcher).where(Launcher.id.in_(snapshots.keys()))
    if current_user.role != "admin":
        stmt = stmt.where(Launcher.user_id == current_user.id)
    launchers = (await db.execute(stmt)).scalars().all()
    return [
        LauncherRuntimeData(launcher_id=str(launcher.id), **snapshots[str(launcher.id)])
        for launcher in launchers
        if str(launcher.id) in snapshots
    ]


@router.post("/{launcher_id}/cancel-current-job", response_model=OkResponse)
async def api_cancel_launcher_current_job(
    launcher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> OkResponse:
    launcher = await scoped_launcher(db, launcher_id, current_user)
    snapshot = (await runtime.launcher_snapshots()).get(str(launcher.id))
    job_id = snapshot.get("current_job_id") if snapshot else None
    if not job_id:
        return OkResponse()
    await job_orchestrator.kill_job(
        db,
        job_id=str(job_id),
        user_id=None if current_user.role == "admin" else current_user.id,
        launcher_id=str(launcher.id),
        reason="cancelled by website",
    )
    return OkResponse()


@router.post("/{launcher_id}/reset-worker", response_model=OkResponse)
async def api_reset_launcher_worker(
    launcher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> OkResponse:
    launcher = await scoped_launcher(db, launcher_id, current_user)
    accepted = await job_orchestrator.reset_launcher_worker(
        db,
        launcher_id=str(launcher.id),
        user_id=None if current_user.role == "admin" else current_user.id,
    )
    if not accepted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Launcher reset is already in progress or the launcher is offline",
        )
    return OkResponse()


async def scoped_launcher(db: AsyncSession, launcher_id: str, current_user: UserData) -> Launcher:
    stmt = select(Launcher).where(Launcher.id == launcher_id)
    if current_user.role != "admin":
        stmt = stmt.where(Launcher.user_id == current_user.id)
    launcher = await db.scalar(stmt)
    if launcher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Launcher not found")
    return launcher
