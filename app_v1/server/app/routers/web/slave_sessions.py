from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SlaveSession, get_db
from app.models import OkResponse, UserData
from app.service.realtime_service import safe_close_client, stop_launcher_session
from app.service.session_service import SessionService
from app.state import runtime
from app.user_auth.utils.auth_wrapper import require_roles

router = APIRouter(prefix="/slave-sessions", tags=["web-slave-sessions"])


@router.post("/{session_id}/close", response_model=OkResponse)
async def api_close_slave_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_roles(["admin", "user"])),
) -> OkResponse:
    stmt = select(SlaveSession).where(SlaveSession.id == session_id)
    if current_user.role != "admin":
        stmt = stmt.where(SlaveSession.user_id == current_user.id)
    session = await db.scalar(stmt)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SlaveSession not found")
    if session.status not in {"starting", "ready"}:
        return OkResponse()

    db_session = await SessionService.close_session(db, session_id, "closed by website")
    runtime_session = await runtime.close_session(session_id)
    launcher_id = (
        runtime_session.launcher_id
        if runtime_session
        else str(db_session.launcher_id)
        if db_session and db_session.launcher_id
        else None
    )
    if launcher_id is not None:
        await stop_launcher_session(launcher_id, session_id, "closed by website")
    if runtime_session is not None:
        await safe_close_client(runtime_session, "closed by website")
    return OkResponse()
