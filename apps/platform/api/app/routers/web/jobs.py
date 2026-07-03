from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models import JobCreateRequest, JobCreateResult, JobData, JobDetailData, UserData
from service.job_service import JobService
from user_auth.utils.auth_wrapper import require_roles

router = APIRouter(prefix="/jobs", tags=["web-jobs"])


@router.get("", response_model=list[JobData])
async def api_list_jobs(
    limit: int | None = 100,
    offset: int | None = 0,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
):
    return await JobService.list_jobs(db, current_user, limit, offset)


@router.post("", response_model=JobCreateResult, status_code=status.HTTP_201_CREATED)
async def api_create_job(
    payload: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
):
    try:
        return await JobService.create_job_request(db, current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{job_id}", response_model=JobDetailData)
async def api_get_job_detail(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
):
    detail = await JobService.get_job_detail(db, current_user, job_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return detail
