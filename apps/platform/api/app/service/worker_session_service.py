from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import WorkerSession
from models import UserData, WorkerSessionData
from user_auth.utils.auth_utils import hash_token, random_urlsafe


def worker_session_to_data(session: WorkerSession) -> WorkerSessionData:
    return WorkerSessionData(
        id=str(session.id),
        user_id=str(session.user_id),
        status=session.status,
        accepting_jobs=session.accepting_jobs,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        client_version=session.client_version,
        gpu_name=session.gpu_name,
        gpu_vendor=session.gpu_vendor,
        vram_total_mb=session.vram_total_mb,
        vram_available_mb=session.vram_available_mb,
        gpu_utilization_pct=session.gpu_utilization_pct,
        gpu_temperature_c=session.gpu_temperature_c,
        supported_task_types=session.supported_task_types,
        installed_model_ids=session.installed_model_ids,
        current_job_id=str(session.current_job_id) if session.current_job_id else None,
        connected_at=session.connected_at,
        last_heartbeat_at=session.last_heartbeat_at,
        disconnected_at=session.disconnected_at,
        expires_at=session.expires_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        metadata_json=session.metadata_json or {},
    )


def optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class WorkerSessionService:
    @staticmethod
    async def list_worker_sessions(db: AsyncSession, current_user: UserData) -> list[WorkerSessionData]:
        stmt = select(WorkerSession).order_by(
            WorkerSession.last_heartbeat_at.desc().nullslast(),
            WorkerSession.connected_at.desc().nullslast(),
            WorkerSession.created_at.desc(),
        )
        if current_user.role != "admin":
            stmt = stmt.where(WorkerSession.user_id == current_user.id)

        sessions = (await db.execute(stmt)).scalars().all()
        return [worker_session_to_data(session) for session in sessions]

    @staticmethod
    async def create_connected_session(
        db: AsyncSession,
        user_id: str,
        hello: dict[str, Any],
        ip_address: str | None,
        user_agent: str | None,
    ) -> WorkerSession:
        now = datetime.now(timezone.utc)
        session = WorkerSession(
            user_id=user_id,
            status="connected",
            accepting_jobs=bool(hello.get("accepting_jobs", False)),
            session_token_hash=hash_token(random_urlsafe(32)),
            ip_address=ip_address,
            user_agent=user_agent,
            client_version=optional_str(hello.get("client_version")),
            connected_at=now,
            last_heartbeat_at=now,
            supported_task_types=[],
            installed_model_ids=[],
            metadata_json={"device_name": optional_str(hello.get("device_name"))},
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def update_gpu_status(
        db: AsyncSession,
        session_id: str,
        message: dict[str, Any],
    ) -> WorkerSession | None:
        session = await db.get(WorkerSession, session_id)
        if session is None:
            return None

        gpu = message.get("gpu")
        if not isinstance(gpu, dict):
            gpu = {}

        now = datetime.now(timezone.utc)
        session.status = optional_str(message.get("status")) or "ready"
        session.last_heartbeat_at = now
        session.gpu_name = optional_str(gpu.get("name"))
        session.gpu_vendor = optional_str(gpu.get("vendor"))
        session.vram_total_mb = optional_int(gpu.get("vram_total_mb"))
        session.vram_available_mb = optional_int(gpu.get("vram_available_mb"))
        session.gpu_temperature_c = optional_decimal(gpu.get("temperature_c"))
        session.gpu_utilization_pct = optional_decimal(gpu.get("utilization_pct"))

        allowed_tasks = message.get("allowed_tasks")
        if isinstance(allowed_tasks, list):
            session.supported_task_types = [str(item) for item in allowed_tasks]

        installed_model_ids = message.get("installed_model_ids")
        if isinstance(installed_model_ids, list):
            session.installed_model_ids = [str(item) for item in installed_model_ids]

        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def mark_disconnected(db: AsyncSession, session_id: str) -> None:
        session = await db.get(WorkerSession, session_id)
        if session is None:
            return

        session.status = "disconnected"
        session.disconnected_at = datetime.now(timezone.utc)
        await db.commit()
