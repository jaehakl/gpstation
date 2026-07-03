from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Job, JobMessage, JobMessagePart, StoredObject, WorkerSession
from models import (
    JobCreateRequest,
    JobCreateResult,
    JobData,
    JobDetailData,
    JobMessageData,
    JobMessagePartData,
    StoredObjectData,
    UserData,
)
from service.worker_session_service import worker_session_to_data


def job_to_data(job: Job) -> JobData:
    return JobData(
        id=str(job.id),
        requester_user_id=str(job.requester_user_id),
        worker_user_id=str(job.worker_user_id) if job.worker_user_id else None,
        worker_session_id=str(job.worker_session_id) if job.worker_session_id else None,
        task_type=job.task_type,
        status=job.status,
        priority=job.priority,
        required_model_id=job.required_model_id,
        required_vram_gb=job.required_vram_gb,
        required_trust_tier=job.required_trust_tier,
        verification_policy=job.verification_policy,
        price_limit_credit=job.price_limit_credit,
        estimated_cost_credit=job.estimated_cost_credit,
        final_cost_credit=job.final_cost_credit,
        worker_reward_credit=job.worker_reward_credit,
        platform_fee_credit=job.platform_fee_credit,
        lease_expires_at=job.lease_expires_at,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failed_at=job.failed_at,
        cancelled_at=job.cancelled_at,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        metadata_json=job.metadata_json or {},
    )


def job_message_to_data(message: JobMessage) -> JobMessageData:
    return JobMessageData(
        id=str(message.id),
        job_id=str(message.job_id),
        kind=message.kind,
        role=message.role,
        status=message.status,
        parent_message_id=str(message.parent_message_id) if message.parent_message_id else None,
        created_by_user_id=str(message.created_by_user_id) if message.created_by_user_id else None,
        created_at=message.created_at,
        metadata_json=message.metadata_json or {},
    )


def job_message_part_to_data(part: JobMessagePart) -> JobMessagePartData:
    return JobMessagePartData(
        id=str(part.id),
        message_id=str(part.message_id),
        object_id=str(part.object_id) if part.object_id else None,
        name=part.name,
        part_type=part.part_type,
        sort_order=part.sort_order,
        required=part.required,
        created_at=part.created_at,
        metadata_json=part.metadata_json or {},
    )


def stored_object_to_data(stored_object: StoredObject) -> StoredObjectData:
    return StoredObjectData(
        id=str(stored_object.id),
        object_type=stored_object.object_type,
        storage_backend=stored_object.storage_backend,
        uri=stored_object.uri,
        mime_type=stored_object.mime_type,
        size_bytes=stored_object.size_bytes,
        sha256=stored_object.sha256,
        created_by_user_id=str(stored_object.created_by_user_id) if stored_object.created_by_user_id else None,
        expires_at=stored_object.expires_at,
        created_at=stored_object.created_at,
        metadata_json=stored_object.metadata_json or {},
    )


class JobService:
    @staticmethod
    async def create_job_request(
        db: AsyncSession,
        requester_user_id: str,
        payload: JobCreateRequest,
    ) -> JobCreateResult:
        task_type = payload.task_type.strip()
        if not task_type:
            raise ValueError("task_type is required")

        job = Job(
            requester_user_id=requester_user_id,
            task_type=task_type,
            status="pending",
            metadata_json={},
        )
        db.add(job)
        await db.flush()

        message = JobMessage(
            job_id=job.id,
            kind="request",
            role="user",
            status="pending",
            created_by_user_id=requester_user_id,
            metadata_json=payload.request_json,
        )
        db.add(message)

        await db.commit()
        await db.refresh(job)
        await db.refresh(message)
        return JobCreateResult(
            job_id=str(job.id),
            message_id=str(message.id),
            task_type=job.task_type,
            status=job.status,
        )

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        current_user: UserData,
        limit: int | None,
        offset: int | None,
    ) -> list[JobData]:
        stmt = select(Job).order_by(Job.created_at.desc(), Job.id.asc())
        if current_user.role != "admin":
            stmt = stmt.where(Job.requester_user_id == current_user.id)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        jobs = (await db.execute(stmt)).scalars().all()
        return [job_to_data(job) for job in jobs]

    @staticmethod
    async def get_job_detail(
        db: AsyncSession,
        current_user: UserData,
        job_id: str,
    ) -> JobDetailData | None:
        stmt = select(Job).where(Job.id == job_id)
        if current_user.role != "admin":
            stmt = stmt.where(Job.requester_user_id == current_user.id)

        job = await db.scalar(stmt)
        if job is None:
            return None

        messages = (
            (
                await db.execute(
                    select(JobMessage)
                    .where(JobMessage.job_id == job.id)
                    .order_by(JobMessage.created_at.asc(), JobMessage.id.asc())
                )
            )
            .scalars()
            .all()
        )
        message_ids = [message.id for message in messages]

        parts: list[JobMessagePart] = []
        if message_ids:
            parts = (
                (
                    await db.execute(
                        select(JobMessagePart)
                        .where(JobMessagePart.message_id.in_(message_ids))
                        .order_by(
                            JobMessagePart.message_id.asc(),
                            JobMessagePart.sort_order.asc(),
                            JobMessagePart.created_at.asc(),
                            JobMessagePart.id.asc(),
                        )
                    )
                )
                .scalars()
                .all()
            )

        stored_objects: list[StoredObject] = []
        object_ids = [part.object_id for part in parts if part.object_id is not None]
        if object_ids:
            stored_objects = (
                (
                    await db.execute(
                        select(StoredObject)
                        .where(StoredObject.id.in_(object_ids))
                        .order_by(StoredObject.created_at.asc(), StoredObject.id.asc())
                    )
                )
                .scalars()
                .all()
            )

        worker_session = None
        if job.worker_session_id:
            worker_session = await db.get(WorkerSession, job.worker_session_id)

        return JobDetailData(
            job=job_to_data(job),
            messages=[job_message_to_data(message) for message in messages],
            message_parts=[job_message_part_to_data(part) for part in parts],
            stored_objects=[stored_object_to_data(stored_object) for stored_object in stored_objects],
            worker_session=worker_session_to_data(worker_session) if worker_session else None,
        )
