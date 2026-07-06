from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Worker
from app.models import WorkerSessionView


def worker_to_view(worker: Worker) -> WorkerSessionView:
    return WorkerSessionView(
        id=str(worker.id),
        user_id=str(worker.user_id),
        worker_name=worker.worker_name,
        status=worker.status,
        slave_app_ids=[str(item) for item in (worker.slave_app_ids or [])],
        active_session_count=len(worker.active_session_ids or []),
        connected_at=worker.connected_at.astimezone(timezone.utc),
        last_heartbeat_at=worker.last_heartbeat_at.astimezone(timezone.utc),
    )


class WorkerService:
    @staticmethod
    async def list_workers_for_user(db: AsyncSession, user_id: str) -> list[WorkerSessionView]:
        stmt = (
            select(Worker)
            .where(Worker.user_id == user_id, Worker.disconnected_at.is_(None))
            .order_by(Worker.last_heartbeat_at.desc(), Worker.connected_at.desc(), Worker.id.asc())
        )
        workers = (await db.execute(stmt)).scalars().all()
        return [worker_to_view(worker) for worker in workers]

    @staticmethod
    async def create_connected_worker(
        db: AsyncSession,
        *,
        user_id: str,
        worker_name: str,
        slave_app_ids: list[str],
        ip_address: str | None,
    ) -> Worker:
        now = datetime.now(timezone.utc)
        unique_slave_app_ids = list(dict.fromkeys(slave_app_ids))
        worker = Worker(
            user_id=user_id,
            worker_name=worker_name,
            ip_address=ip_address,
            status="ready",
            slave_app_ids=unique_slave_app_ids,
            active_session_ids=[],
            connected_at=now,
            last_heartbeat_at=now,
        )
        db.add(worker)
        await db.commit()
        await db.refresh(worker)
        return worker

    @staticmethod
    async def mark_heartbeat(
        db: AsyncSession,
        worker_id: str,
        status: str,
        active_session_ids: list[str],
    ) -> None:
        worker = await db.get(Worker, worker_id)
        if worker is None:
            return

        worker.status = status
        worker.active_session_ids = active_session_ids
        worker.last_heartbeat_at = datetime.now(timezone.utc)
        await db.commit()

    @staticmethod
    async def mark_disconnected(db: AsyncSession, worker_id: str) -> None:
        worker = await db.get(Worker, worker_id)
        if worker is None:
            return

        worker.status = "disconnected"
        worker.active_session_ids = []
        worker.disconnected_at = datetime.now(timezone.utc)
        await db.commit()

    @staticmethod
    async def mark_stale_workers_disconnected(db: AsyncSession) -> None:
        now = datetime.now(timezone.utc)
        await db.execute(
            update(Worker)
            .where(Worker.disconnected_at.is_(None))
            .values(status="disconnected", active_session_ids=[], disconnected_at=now)
        )
        await db.commit()
