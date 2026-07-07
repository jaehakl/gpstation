from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Job, get_db
from app.models import JobData, OkResponse, UserData
from app.service.job_service import JobService, job_to_data
from app.service.realtime_service import send_to_launcher
from app.state import runtime
from app.user_auth.utils.auth_wrapper import require_roles

router = APIRouter(prefix="/jobs", tags=["web-jobs"])


@router.get("", response_model=list[JobData])
async def api_list_jobs(
    active_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> list[JobData]:
    stmt = select(Job).order_by(Job.created_at.desc(), Job.id.asc()).limit(limit)
    if current_user.role != "admin":
        stmt = stmt.where(Job.user_id == current_user.id)
    if active_only:
        stmt = stmt.where(Job.state.in_(("queued", "assigned", "answer_ready", "running")))
    jobs = (await db.execute(stmt)).scalars().all()
    return [job_to_data(job) for job in jobs]


@router.post("/{job_id}/kill", response_model=OkResponse)
async def api_kill_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> OkResponse:
    stmt = select(Job).where(Job.id == job_id)
    if current_user.role != "admin":
        stmt = stmt.where(Job.user_id == current_user.id)
    job = await db.scalar(stmt)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    launcher_id = str(job.launcher_id) if job.launcher_id and job.state in {"assigned", "answer_ready", "running"} else None
    await JobService.request_kill(db, job=job)
    await runtime.set_job_event(job_id)
    if launcher_id is not None:
        try:
            await send_to_launcher(launcher_id, {"type": "job.cancel", "job_id": job_id, "reason": "killed by website"})
        except HTTPException:
            await runtime.mark_launcher_job(launcher_id, None, worker_status="idle")
    from app.routers.v1.jobs import dispatch_queued_jobs

    await dispatch_queued_jobs(db, user_id=None if current_user.role == "admin" else current_user.id)
    return OkResponse()
