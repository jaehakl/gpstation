from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import (
    JobAnswerWaitResult,
    JobCreateRequest,
    JobCreateResult,
    JobData,
    JobSummary,
    OkResponse,
    UserData,
)
from app.service.job_orchestrator import job_orchestrator
from app.service.job_service import JobService, job_to_data
from app.settings import settings
from app.user_auth.utils.auth_wrapper import require_roles


router = APIRouter(prefix="/jobs", tags=["web-jobs"])


@router.get("", response_model=list[JobSummary])
async def api_list_jobs(
    active_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> list[JobSummary]:
    return await JobService.list_job_summaries(
        db,
        user_id=None if current_user.role == "admin" else current_user.id,
        active_only=active_only,
        limit=limit,
    )


@router.post("", response_model=JobCreateResult)
async def api_create_job(
    body: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> JobCreateResult:
    try:
        job = await job_orchestrator.create_job(
            db,
            user_id=current_user.id,
            handler_type=body.handler_type,
            slave_app_id=body.slave_app_id,
            offer=body.offer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return JobCreateResult(job=job_to_data(job), answer_wait_url=build_web_job_wait_url(str(job.id)))


@router.get("/{job_id}", response_model=JobData)
async def api_get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> JobData:
    job = await JobService.get_job(
        db,
        job_id=job_id,
        user_id=None if current_user.role == "admin" else current_user.id,
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_to_data(job)


@router.get("/{job_id}/wait-answer", response_model=JobAnswerWaitResult)
async def api_wait_job_answer(
    job_id: str,
    wait_seconds: float = Query(default=30.0, ge=0, le=60),
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> JobAnswerWaitResult:
    job = await job_orchestrator.wait_for_answer(
        db,
        job_id=job_id,
        user_id=None if current_user.role == "admin" else current_user.id,
        wait_seconds=wait_seconds,
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
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
    job = await job_orchestrator.kill_job(
        db,
        job_id=job_id,
        user_id=None if current_user.role == "admin" else current_user.id,
        reason="killed by website",
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return OkResponse()


def build_web_job_wait_url(job_id: str) -> str:
    parsed = urlparse(settings.public_base_url)
    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/web/jobs/{job_id}/wait-answer" if base_path else f"/web/jobs/{job_id}/wait-answer"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
