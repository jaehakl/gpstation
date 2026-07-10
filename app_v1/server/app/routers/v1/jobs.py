from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, require_client
from app.db import get_db
from app.models import JobAnswerWaitResult, JobCreateRequest, JobCreateResult, JobData, OkResponse
from app.service.job_orchestrator import job_orchestrator
from app.service.job_service import JobService, job_to_data
from app.settings import settings


router = APIRouter(prefix="/jobs", tags=["v1-jobs"])


@router.post("", response_model=JobCreateResult)
async def create_job(
    body: JobCreateRequest,
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> JobCreateResult:
    try:
        job = await job_orchestrator.create_job(
            db,
            user_id=principal.user_id,
            handler_type=body.handler_type,
            slave_app_id=body.slave_app_id,
            offer=body.offer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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


@router.get("/{job_id}/wait-answer", response_model=JobAnswerWaitResult)
async def wait_job_answer(
    job_id: str,
    wait_seconds: float = Query(default=30.0, ge=0, le=60),
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> JobAnswerWaitResult:
    job = await job_orchestrator.wait_for_answer(
        db,
        job_id=job_id,
        user_id=principal.user_id,
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
async def kill_job(
    job_id: str,
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> OkResponse:
    job = await job_orchestrator.kill_job(
        db,
        job_id=job_id,
        user_id=principal.user_id,
        reason="killed by client",
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return OkResponse()


def build_job_wait_url(job_id: str) -> str:
    parsed = urlparse(settings.public_base_url)
    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/v1/jobs/{job_id}/wait-answer" if base_path else f"/v1/jobs/{job_id}/wait-answer"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
