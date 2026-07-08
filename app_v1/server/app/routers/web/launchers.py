from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Job, Launcher, get_db
from app.models import OkResponse, UserData
from app.service.job_service import JobService
from app.service.launcher_service import LauncherService
from app.service.realtime_service import send_to_launcher
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
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/reconcile-disconnected", response_model=LauncherReconcileResponse)
async def api_reconcile_disconnected_launchers(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> LauncherReconcileResponse:
    connected_launcher_ids = await runtime.get_launcher_ids()
    user_id = None if current_user.role == "admin" else current_user.id
    launchers = await LauncherService.reconcile_disconnected_launchers(
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
    await mark_runtime_job_cancel_requested(db, str(job_id), str(launcher.id), current_user)
    try:
        await send_to_launcher(str(launcher.id), {"type": "job.cancel", "job_id": str(job_id), "reason": "cancelled by website"})
    except HTTPException:
        await runtime.mark_launcher_job(str(launcher.id), None, worker_status="idle")
        await dispatch_more_jobs(db, current_user)
    return OkResponse()


@router.post("/{launcher_id}/reset-worker", response_model=OkResponse)
async def api_reset_launcher_worker(
    launcher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> OkResponse:
    launcher = await scoped_launcher(db, launcher_id, current_user)
    snapshot = (await runtime.launcher_snapshots()).get(str(launcher.id))
    job_id = snapshot.get("current_job_id") if snapshot else None
    if job_id:
        await mark_runtime_job_cancel_requested(db, str(job_id), str(launcher.id), current_user)
    try:
        await send_to_launcher(str(launcher.id), {"type": "worker.reset", "reason": "reset by website"})
    except HTTPException:
        await runtime.clear_launcher_worker(str(launcher.id))
        await dispatch_more_jobs(db, current_user)
    return OkResponse()


async def scoped_launcher(db: AsyncSession, launcher_id: str, current_user: UserData) -> Launcher:
    stmt = select(Launcher).where(Launcher.id == launcher_id)
    if current_user.role != "admin":
        stmt = stmt.where(Launcher.user_id == current_user.id)
    launcher = await db.scalar(stmt)
    if launcher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Launcher not found")
    return launcher


async def mark_runtime_job_cancel_requested(
    db: AsyncSession,
    job_id: str,
    launcher_id: str,
    current_user: UserData,
) -> None:
    stmt = select(Job).where(Job.id == job_id, Job.launcher_id == launcher_id)
    if current_user.role != "admin":
        stmt = stmt.where(Job.user_id == current_user.id)
    job = await db.scalar(stmt)
    if job is not None:
        await JobService.request_kill(db, job=job)
        await runtime.set_job_event(job_id)


async def dispatch_more_jobs(db: AsyncSession, current_user: UserData) -> None:
    from app.routers.v1.jobs import dispatch_queued_jobs

    await dispatch_queued_jobs(db, user_id=None if current_user.role == "admin" else current_user.id)
