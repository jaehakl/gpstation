from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Launcher, SlaveSession
from app.models import LauncherSessionView
from app.service.session_service import ACTIVE_SESSION_STATUSES


ACTIVE_LAUNCHER_STATUSES = {"ready", "busy"}
LAUNCHER_DISCONNECTED_REASON = "launcher disconnected"


def launcher_to_view(launcher: Launcher) -> LauncherSessionView:
    return LauncherSessionView(
        id=str(launcher.id),
        user_id=str(launcher.user_id),
        launcher_name=launcher.launcher_name,
        status=launcher.status,
        slave_app_ids=[str(item) for item in (launcher.slave_app_ids or [])],
        active_session_count=len(launcher.active_session_ids or []),
        connected_at=launcher.connected_at.astimezone(timezone.utc),
        last_heartbeat_at=launcher.last_heartbeat_at.astimezone(timezone.utc),
    )


class LauncherService:
    @staticmethod
    async def list_launchers_for_user(db: AsyncSession, user_id: str) -> list[LauncherSessionView]:
        stmt = (
            select(Launcher)
            .where(Launcher.user_id == user_id, Launcher.disconnected_at.is_(None))
            .order_by(Launcher.last_heartbeat_at.desc(), Launcher.connected_at.desc(), Launcher.id.asc())
        )
        launchers = (await db.execute(stmt)).scalars().all()
        return [launcher_to_view(launcher) for launcher in launchers]

    @staticmethod
    async def create_connected_launcher(
        db: AsyncSession,
        *,
        user_id: str,
        launcher_name: str,
        slave_app_ids: list[str],
        ip_address: str | None,
    ) -> Launcher:
        now = datetime.now(timezone.utc)
        unique_slave_app_ids = list(dict.fromkeys(slave_app_ids))
        launcher = Launcher(
            user_id=user_id,
            launcher_name=launcher_name,
            ip_address=ip_address,
            status="ready",
            slave_app_ids=unique_slave_app_ids,
            active_session_ids=[],
            connected_at=now,
            last_heartbeat_at=now,
        )
        db.add(launcher)
        await db.commit()
        await db.refresh(launcher)
        return launcher

    @staticmethod
    async def mark_heartbeat(
        db: AsyncSession,
        launcher_id: str,
        status: str,
        active_session_ids: list[str],
    ) -> None:
        launcher = await db.get(Launcher, launcher_id)
        if launcher is None:
            return

        launcher.status = status
        launcher.active_session_ids = active_session_ids
        launcher.last_heartbeat_at = datetime.now(timezone.utc)
        await db.commit()

    @staticmethod
    async def mark_disconnected(db: AsyncSession, launcher_id: str) -> None:
        launcher = await db.get(Launcher, launcher_id)
        if launcher is None:
            return

        launcher.status = "disconnected"
        launcher.active_session_ids = []
        launcher.disconnected_at = datetime.now(timezone.utc)
        await db.commit()

    @staticmethod
    async def mark_stale_launchers_disconnected(db: AsyncSession) -> None:
        now = datetime.now(timezone.utc)
        await db.execute(
            update(Launcher)
            .where(Launcher.disconnected_at.is_(None))
            .values(status="disconnected", active_session_ids=[], disconnected_at=now)
        )
        await db.commit()

    @staticmethod
    async def reconcile_disconnected_launchers(
        db: AsyncSession,
        *,
        connected_launcher_ids: set[str],
        user_id: str | None = None,
    ) -> tuple[int, int]:
        launcher_clauses = [
            (Launcher.status.in_(ACTIVE_LAUNCHER_STATUSES)) | (Launcher.disconnected_at.is_(None))
        ]
        if connected_launcher_ids:
            launcher_clauses.append(Launcher.id.notin_(connected_launcher_ids))
        if user_id is not None:
            launcher_clauses.append(Launcher.user_id == user_id)
        candidates = (
            await db.execute(
                select(Launcher).where(*launcher_clauses)
            )
        ).scalars().all()
        target_launchers = [
            launcher
            for launcher in candidates
            if (launcher.status in ACTIVE_LAUNCHER_STATUSES or launcher.disconnected_at is None)
            and str(launcher.id) not in connected_launcher_ids
            and (user_id is None or str(launcher.user_id) == user_id)
        ]
        if not target_launchers:
            return 0, 0

        now = datetime.now(timezone.utc)
        target_launcher_ids = {str(launcher.id) for launcher in target_launchers}
        sessions = (
            await db.execute(
                select(SlaveSession).where(
                    SlaveSession.launcher_id.in_(target_launcher_ids),
                    SlaveSession.status.in_(ACTIVE_SESSION_STATUSES),
                )
            )
        ).scalars().all()
        target_sessions = [
            session
            for session in sessions
            if str(session.launcher_id) in target_launcher_ids and session.status in ACTIVE_SESSION_STATUSES
        ]

        for launcher in target_launchers:
            launcher.status = "disconnected"
            launcher.active_session_ids = []
            launcher.disconnected_at = now
        for session in target_sessions:
            session.status = "error"
            session.closed_at = now
            session.last_error = LAUNCHER_DISCONNECTED_REASON

        await db.commit()
        return len(target_launchers), len(target_sessions)
