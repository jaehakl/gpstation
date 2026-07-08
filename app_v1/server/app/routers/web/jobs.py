from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Job, get_db
from app.models import JobAnswerWaitResult, JobCreateRequest, JobCreateResult, JobData, OkResponse, UserData
from app.service.job_service import JOB_TERMINAL_STATES, JobService, job_to_data
from app.service.realtime_service import send_to_launcher
from app.settings import settings
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


@router.post("", response_model=JobCreateResult)
async def api_create_job(
    body: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> JobCreateResult:
    try:
        job = await JobService.create_job(
            db,
            user_id=current_user.id,
            handler_type=body.handler_type,
            slave_app_id=body.slave_app_id,
            offer=body.offer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    from app.routers.v1.jobs import dispatch_queued_jobs

    await dispatch_queued_jobs(db, user_id=current_user.id)
    return JobCreateResult(job=job_to_data(job), answer_wait_url=build_web_job_wait_url(str(job.id)))


@router.get("/{job_id}/wait-answer", response_model=JobAnswerWaitResult)
async def api_wait_job_answer(
    job_id: str,
    wait_seconds: float = Query(default=30.0, ge=0, le=60),
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> JobAnswerWaitResult:
    job = await get_accessible_job(db, job_id, current_user)
    if job.answer is None and job.state not in JOB_TERMINAL_STATES and wait_seconds > 0:
        await runtime.wait_job_event(job_id, wait_seconds)
        job = await get_accessible_job(db, job_id, current_user)
    return JobAnswerWaitResult(
        job_id=str(job.id),
        state=job.state,
        answer=job.answer,
        last_error=job.last_error,
    )


@router.post("/{job_id}/kill", response_model=OkResponse)
async def api_kill_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> OkResponse:
    job = await get_accessible_job(db, job_id, current_user)
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


async def get_accessible_job(db: AsyncSession, job_id: str, current_user: UserData) -> Job:
    stmt = select(Job).where(Job.id == job_id)
    if current_user.role != "admin":
        stmt = stmt.where(Job.user_id == current_user.id)
    job = await db.scalar(stmt)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def build_web_job_wait_url(job_id: str) -> str:
    parsed = urlparse(settings.public_base_url)
    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/web/jobs/{job_id}/wait-answer" if base_path else f"/web/jobs/{job_id}/wait-answer"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
