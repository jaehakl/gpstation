from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import DashboardSummary, UserData
from app.service.management_service import ManagementService
from app.user_auth.utils.auth_wrapper import require_roles

router = APIRouter(prefix="/dashboard", tags=["web-dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def api_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> DashboardSummary:
    return await ManagementService.dashboard_summary(db, current_user)
