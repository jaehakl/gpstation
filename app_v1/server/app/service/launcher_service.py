from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Launcher
from app.models import LauncherSessionView


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
