from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sdk.protocol.messages import SignalPayload
from app.db import Job, Launcher
from app.models import JobData

JOB_TERMINAL_STATES = {"succeeded", "failed", "cancelled", "killed"}
JOB_ACTIVE_STATES = {"assigned", "answer_ready", "running"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def job_to_data(job: Job) -> JobData:
    return JobData(
        id=str(job.id),
        user_id=str(job.user_id),
        handler_type=job.handler_type,
        slave_app_id=job.slave_app_id,
        input=job.input,
        offer=job.offer,
        answer=job.answer,
        result=job.result,
        progress=list(job.progress or []),
        state=job.state,
        launcher_id=str(job.launcher_id) if job.launcher_id else None,
        assigned_at=job.assigned_at,
        answer_ready_at=job.answer_ready_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        cancel_requested_at=job.cancel_requested_at,
        last_error=job.last_error,
        attempt_count=job.attempt_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


class JobService:
    @staticmethod
    async def create_job(
        db: AsyncSession,
        *,
        user_id: str,
        handler_type: str,
        slave_app_id: str,
        input: Any,
        offer: dict[str, Any],
    ) -> Job:
        signal = SignalPayload.model_validate(offer)
        if signal.type != "offer" or not signal.sdp:
            raise ValueError("Job offer must be an SDP offer")
        job = Job(
            user_id=user_id,
            handler_type=handler_type,
            slave_app_id=slave_app_id,
            input=input,
            offer=signal.model_dump(exclude_none=True),
            state="queued",
            progress=[],
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def get_user_job(db: AsyncSession, *, job_id: str, user_id: str) -> Job | None:
        return await db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))

    @staticmethod
    async def select_next_queued_job(db: AsyncSession, *, user_id: str | None = None) -> Job | None:
        stmt = select(Job).where(Job.state == "queued").order_by(Job.created_at.asc(), Job.id.asc())
        if user_id is not None:
            stmt = stmt.where(Job.user_id == user_id)
        return await db.scalar(stmt)

    @staticmethod
    async def select_idle_launcher_for_job(
        db: AsyncSession,
        *,
        job: Job,
        idle_launcher_ids: set[str],
    ) -> Launcher | None:
        if not idle_launcher_ids:
            return None
        launchers = (
            await db.execute(
                select(Launcher)
                .where(
                    Launcher.id.in_(idle_launcher_ids),
                    Launcher.user_id == job.user_id,
                    Launcher.disconnected_at.is_(None),
                    Launcher.status.in_(("ready", "busy")),
                )
                .order_by(Launcher.last_heartbeat_at.desc(), Launcher.connected_at.asc(), Launcher.id.asc())
            )
        ).scalars().all()
        for launcher in launchers:
            if job.slave_app_id in {str(item) for item in (launcher.slave_app_ids or [])}:
                return launcher
        return None

    @staticmethod
    async def assign_job(db: AsyncSession, *, job: Job, launcher: Launcher) -> Job:
        now = utcnow()
        job.launcher_id = launcher.id
        job.state = "assigned"
        job.assigned_at = now
        job.attempt_count = int(job.attempt_count or 0) + 1
        launcher.status = "busy"
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def mark_answer(db: AsyncSession, *, job_id: str, answer: dict[str, Any]) -> Job | None:
        job = await db.get(Job, job_id)
        if job is None or job.state in JOB_TERMINAL_STATES:
            return job
        signal = SignalPayload.model_validate(answer)
        if signal.type != "answer" or not signal.sdp:
            raise ValueError("Job answer must be an SDP answer")
        job.answer = signal.model_dump(exclude_none=True)
        job.answer_ready_at = utcnow()
        job.state = "answer_ready"
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def mark_running(db: AsyncSession, *, job_id: str) -> Job | None:
        job = await db.get(Job, job_id)
        if job is None or job.state in JOB_TERMINAL_STATES:
            return job
        job.state = "running"
        job.started_at = job.started_at or utcnow()
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def append_progress(db: AsyncSession, *, job_id: str, progress: Any) -> Job | None:
        job = await db.get(Job, job_id)
        if job is None or job.state in JOB_TERMINAL_STATES:
            return job
        items = list(job.progress or [])
        items.append({"time": utcnow().isoformat(), "progress": progress})
        job.progress = items
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def mark_result(db: AsyncSession, *, job_id: str, result: Any) -> Job | None:
        job = await db.get(Job, job_id)
        if job is None:
            return None
        job.result = result
        job.state = "succeeded"
        job.finished_at = utcnow()
        await clear_launcher_if_current(db, job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def mark_error(db: AsyncSession, *, job_id: str, detail: str, state: str = "failed") -> Job | None:
        job = await db.get(Job, job_id)
        if job is None:
            return None
        job.state = state
        job.last_error = detail
        job.finished_at = utcnow()
        await clear_launcher_if_current(db, job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def request_kill(db: AsyncSession, *, job: Job) -> Job:
        job.cancel_requested_at = utcnow()
        if job.state == "queued":
            job.state = "killed"
            job.finished_at = utcnow()
        elif job.state in JOB_ACTIVE_STATES:
            job.state = "cancelled"
            job.finished_at = utcnow()
            await clear_launcher_if_current(db, job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def fail_launcher_jobs(db: AsyncSession, *, launcher_id: str, detail: str) -> list[Job]:
        jobs = (
            await db.execute(
                select(Job).where(
                    Job.launcher_id == launcher_id,
                    Job.state.in_(JOB_ACTIVE_STATES),
                )
            )
        ).scalars().all()
        for job in jobs:
            job.state = "failed"
            job.last_error = detail
            job.finished_at = utcnow()
        await db.commit()
        return list(jobs)


async def clear_launcher_if_current(db: AsyncSession, job: Job) -> None:
    if not job.launcher_id:
        return
    launcher = await db.get(Launcher, job.launcher_id)
    if launcher is not None and launcher.disconnected_at is None:
        launcher.status = "ready"
