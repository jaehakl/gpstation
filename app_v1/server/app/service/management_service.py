from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AccessKey, Launcher, SlaveSession
from app.models import DashboardSummary, LauncherSessionView, SlaveSessionData, UserData
from app.user_auth.db import User

ACTIVE_SESSION_STATUSES = {"starting", "ready"}


def launcher_to_admin_view(launcher: Launcher) -> LauncherSessionView:
    return LauncherSessionView(
        id=str(launcher.id),
        user_id=str(launcher.user_id),
        launcher_name=launcher.launcher_name,
        status=launcher.status,
        slave_app_ids=[str(item) for item in (launcher.slave_app_ids or [])],
        active_session_count=len(launcher.active_session_ids or []),
        connected_at=launcher.connected_at,
        last_heartbeat_at=launcher.last_heartbeat_at,
        ip_address=launcher.ip_address,
        disconnected_at=launcher.disconnected_at,
    )


def slave_session_to_data(session: SlaveSession) -> SlaveSessionData:
    return SlaveSessionData(
        id=str(session.id),
        user_id=str(session.user_id),
        launcher_id=str(session.launcher_id) if session.launcher_id else None,
        slave_app_id=session.slave_app_id,
        master_ip_address=session.master_ip_address,
        master_user_agent=session.master_user_agent,
        status=session.status,
        ttl_seconds=session.ttl_seconds,
        expires_at=session.expires_at,
        ready_at=session.ready_at,
        closed_at=session.closed_at,
        last_error=session.last_error,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def effective_user_id(current_user: UserData, requested_user_id: str | None) -> str | None:
    if current_user.role == "admin":
        return requested_user_id
    return current_user.id


class ManagementService:
    @staticmethod
    async def dashboard_summary(db: AsyncSession, current_user: UserData) -> DashboardSummary:
        user_id = None if current_user.role == "admin" else current_user.id
        launcher_stmt = select(Launcher.id)
        session_stmt = select(SlaveSession.id).where(SlaveSession.status.in_(ACTIVE_SESSION_STATUSES))
        key_stmt = select(AccessKey.id)
        if user_id is not None:
            launcher_stmt = launcher_stmt.where(Launcher.user_id == user_id)
            session_stmt = session_stmt.where(SlaveSession.user_id == user_id)
            key_stmt = key_stmt.where(AccessKey.user_id == user_id)
            users = 1
        else:
            users = len((await db.execute(select(User.id))).all())
        return DashboardSummary(
            launchers=len((await db.execute(launcher_stmt)).all()),
            active_sessions=len((await db.execute(session_stmt)).all()),
            users=users,
            access_keys=len((await db.execute(key_stmt)).all()),
        )

    @staticmethod
    async def list_launchers(
        db: AsyncSession,
        current_user: UserData,
        requested_user_id: str | None = None,
    ) -> list[LauncherSessionView]:
        user_id = effective_user_id(current_user, requested_user_id)
        stmt = select(Launcher).order_by(Launcher.last_heartbeat_at.desc(), Launcher.connected_at.desc(), Launcher.id.asc())
        if user_id is not None:
            stmt = stmt.where(Launcher.user_id == user_id)
        launchers = (await db.execute(stmt)).scalars().all()
        return [launcher_to_admin_view(launcher) for launcher in launchers]

    @staticmethod
    async def get_launcher(db: AsyncSession, current_user: UserData, launcher_id: str) -> LauncherSessionView | None:
        launcher = await db.get(Launcher, launcher_id)
        if launcher is None:
            return None
        if current_user.role != "admin" and str(launcher.user_id) != current_user.id:
            return None
        return launcher_to_admin_view(launcher)

    @staticmethod
    async def list_slave_sessions(
        db: AsyncSession,
        current_user: UserData,
        requested_user_id: str | None = None,
    ) -> list[SlaveSessionData]:
        user_id = effective_user_id(current_user, requested_user_id)
        stmt = select(SlaveSession).order_by(SlaveSession.created_at.desc(), SlaveSession.id.asc())
        if user_id is not None:
            stmt = stmt.where(SlaveSession.user_id == user_id)
        sessions = (await db.execute(stmt)).scalars().all()
        return [slave_session_to_data(session) for session in sessions]

    @staticmethod
    async def get_slave_session(db: AsyncSession, current_user: UserData, session_id: str) -> SlaveSessionData | None:
        session = await db.get(SlaveSession, session_id)
        if session is None:
            return None
        if current_user.role != "admin" and str(session.user_id) != current_user.id:
            return None
        return slave_session_to_data(session)
