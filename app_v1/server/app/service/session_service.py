from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SlaveSession, Launcher
from app.user_auth.utils.auth_utils import hash_token, random_urlsafe


ACTIVE_SESSION_STATUSES = {"starting", "ready"}


def is_expired(expires_at: datetime, now: datetime | None = None) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= (now or datetime.now(timezone.utc))


class SessionService:
    @staticmethod
    async def create_session(
        db: AsyncSession,
        *,
        user_id: str,
        launcher_id: str,
        slave_app_id: str,
        ttl_seconds: int,
        master_ip_address: str | None,
        master_user_agent: str | None,
    ) -> tuple[SlaveSession, str]:
        launcher = await db.get(Launcher, launcher_id)
        if launcher is None or launcher.user_id != user_id or launcher.disconnected_at is not None:
            raise KeyError("launcher not available")
        if launcher.status not in {"ready", "busy"}:
            raise KeyError("launcher not available")

        if slave_app_id not in {str(item) for item in (launcher.slave_app_ids or [])}:
            raise ValueError("slave app not available")

        now = datetime.now(timezone.utc)
        token = random_urlsafe(32)
        session = SlaveSession(
            user_id=user_id,
            launcher_id=launcher.id,
            slave_app_id=slave_app_id,
            master_ip_address=master_ip_address,
            master_user_agent=master_user_agent,
            session_token_hash=hash_token(token),
            status="starting",
            ttl_seconds=ttl_seconds,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        db.add(session)
        await db.flush()

        active_session_ids = list(launcher.active_session_ids or [])
        if session.id not in active_session_ids:
            active_session_ids.append(session.id)
        launcher.active_session_ids = active_session_ids
        launcher.status = "busy"

        await db.commit()
        await db.refresh(session)
        return session, token

    @staticmethod
    async def verify_session_token(db: AsyncSession, session_id: str, token: str) -> SlaveSession | None:
        session = await db.get(SlaveSession, session_id)
        if session is None or session.status not in ACTIVE_SESSION_STATUSES:
            return None
        if is_expired(session.expires_at):
            await SessionService.close_session(db, session_id, "expired", status="expired")
            return None
        if not secrets.compare_digest(bytes(session.session_token_hash), hash_token(token)):
            return None
        return session

    @staticmethod
    async def mark_session_ready(db: AsyncSession, session_id: str) -> SlaveSession | None:
        session = await db.get(SlaveSession, session_id)
        if session is None:
            return None

        session.status = "ready"
        session.ready_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def mark_session_error(
        db: AsyncSession,
        session_id: str,
        detail: str,
        code: str | None = None,
    ) -> SlaveSession | None:
        session = await db.get(SlaveSession, session_id)
        if session is None:
            return None

        session.status = "error"
        session.last_error = detail
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def close_session(
        db: AsyncSession,
        session_id: str,
        reason: str,
        *,
        status: str = "closed",
    ) -> SlaveSession | None:
        session = await db.get(SlaveSession, session_id)
        if session is None:
            return None

        session.status = status
        session.closed_at = datetime.now(timezone.utc)
        session.last_error = reason if status in {"error", "expired"} else session.last_error
        if session.launcher_id:
            launcher = await db.get(Launcher, session.launcher_id)
            if launcher is not None:
                active_session_ids = [item for item in (launcher.active_session_ids or []) if item != session_id]
                launcher.active_session_ids = active_session_ids
                if launcher.disconnected_at is None and not active_session_ids:
                    launcher.status = "ready"

        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def collect_expired_sessions(db: AsyncSession) -> list[SlaveSession]:
        now = datetime.now(timezone.utc)
        sessions = (
            await db.execute(
                select(SlaveSession).where(
                    SlaveSession.status.in_(ACTIVE_SESSION_STATUSES),
                    SlaveSession.expires_at <= now,
                )
            )
        ).scalars().all()

        closed: list[SlaveSession] = []
        for session in sessions:
            closed_session = await SessionService.close_session(db, session.id, "expired", status="expired")
            if closed_session is not None:
                closed.append(closed_session)
        return closed

    @staticmethod
    async def mark_stale_sessions_error(db: AsyncSession) -> None:
        sessions = (
            await db.execute(select(SlaveSession).where(SlaveSession.status.in_(ACTIVE_SESSION_STATUSES)))
        ).scalars().all()
        for session in sessions:
            session.status = "error"
            session.closed_at = datetime.now(timezone.utc)
            session.last_error = "server restarted"
        await db.commit()
