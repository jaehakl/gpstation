from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, require_client
from app.db import get_db
from app.models import JobAnswerWaitResult, JobCreateRequest, JobCreateResult, JobData, OkResponse, SessionLogResponse
from app.service.job_service import JOB_TERMINAL_STATES, JobService, job_to_data
from app.service.realtime_service import send_to_launcher
from app.settings import settings
from app.state import runtime

router = APIRouter(prefix="/jobs", tags=["v1-jobs"])


@router.post("", response_model=JobCreateResult)
async def create_job(
    body: JobCreateRequest,
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> JobCreateResult:
    try:
        job = await JobService.create_job(
            db,
            user_id=principal.user_id,
            handler_type=body.handler_type,
            slave_app_id=body.slave_app_id,
            input=body.input,
            offer=body.offer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await dispatch_queued_jobs(db, user_id=principal.user_id)
    return JobCreateResult(job=job_to_data(job), answer_wait_url=build_job_wait_url(str(job.id)))


@router.get("/{job_id}", response_model=JobData)
async def get_job(
    job_id: str,
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> JobData:
    job = await JobService.get_user_job(db, job_id=job_id, user_id=principal.user_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_to_data(job)


@router.get("/{job_id}/logs", response_model=SessionLogResponse)
async def get_job_logs(
    job_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> SessionLogResponse:
    job = await JobService.get_user_job(db, job_id=job_id, user_id=principal.user_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return SessionLogResponse(items=await runtime.get_session_logs(job_id, limit=limit))


@router.get("/{job_id}/wait-answer", response_model=JobAnswerWaitResult)
async def wait_job_answer(
    job_id: str,
    wait_seconds: float = Query(default=30.0, ge=0, le=60),
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> JobAnswerWaitResult:
    job = await JobService.get_user_job(db, job_id=job_id, user_id=principal.user_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.answer is None and job.state not in JOB_TERMINAL_STATES and wait_seconds > 0:
        await runtime.wait_job_event(job_id, wait_seconds)
        job = await JobService.get_user_job(db, job_id=job_id, user_id=principal.user_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobAnswerWaitResult(
        job_id=str(job.id),
        state=job.state,
        answer=job.answer,
        result=job.result,
        last_error=job.last_error,
    )


@router.post("/{job_id}/kill", response_model=OkResponse)
async def kill_job(
    job_id: str,
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> OkResponse:
    job = await JobService.get_user_job(db, job_id=job_id, user_id=principal.user_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    launcher_id = str(job.launcher_id) if job.launcher_id and job.state in {"assigned", "answer_ready", "running"} else None
    await JobService.request_kill(db, job=job)
    await runtime.set_job_event(job_id)
    if launcher_id is not None:
        try:
            await send_to_launcher(launcher_id, {"type": "job.cancel", "job_id": job_id, "reason": "killed by client"})
        except HTTPException:
            await runtime.mark_launcher_job(launcher_id, None, worker_status="idle")
    await dispatch_queued_jobs(db, user_id=principal.user_id)
    return OkResponse()


async def dispatch_queued_jobs(db: AsyncSession, *, user_id: str | None = None) -> None:
    while True:
        job = await JobService.select_next_queued_job(db, user_id=user_id)
        if job is None:
            return
        launcher = await JobService.select_idle_launcher_for_job(
            db,
            job=job,
            idle_launcher_ids=await runtime.idle_launcher_ids(),
        )
        if launcher is None:
            return
        job = await JobService.assign_job(db, job=job, launcher=launcher)
        await runtime.mark_launcher_job(str(launcher.id), str(job.id), loaded_slave_app_id=job.slave_app_id, worker_status="assigned")
        try:
            await send_to_launcher(
                str(launcher.id),
                {
                    "type": "job.start",
                    "job_id": str(job.id),
                    "handler_type": job.handler_type,
                    "slave_app_id": job.slave_app_id,
                    "input": job.input,
                    "offer": job.offer,
                },
            )
        except HTTPException:
            await runtime.mark_launcher_job(str(launcher.id), None, worker_status="idle")
            await JobService.mark_error(db, job_id=str(job.id), detail="launcher unavailable")
            await runtime.set_job_event(str(job.id))
            continue


def build_job_wait_url(job_id: str) -> str:
    parsed = urlparse(settings.public_base_url)
    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/v1/jobs/{job_id}/wait-answer" if base_path else f"/v1/jobs/{job_id}/wait-answer"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
