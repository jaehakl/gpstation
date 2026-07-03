from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models import UserData, WorkerSessionData
from service.worker_session_service import WorkerSessionService
from user_auth.utils.auth_wrapper import require_roles

router = APIRouter(tags=["web-worker-sessions"])


@router.get("/worker-sessions", response_model=list[WorkerSessionData])
async def api_list_worker_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
):
    return await WorkerSessionService.list_worker_sessions(db, current_user)
