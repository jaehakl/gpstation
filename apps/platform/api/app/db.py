from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, LargeBinary, MetaData, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from settings import settings


def make_async_db_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


DB_URL = make_async_db_url(settings.db_url)
engine = create_async_engine(DB_URL, future=True, pool_pre_ping=True, echo=False)
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise


naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)


def uuid_text() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class WorkerSession(TimestampMixin, Base):
    __tablename__ = "worker_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    accepting_jobs: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    session_token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(Text)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    client_version: Mapped[Optional[str]] = mapped_column(Text)
    gpu_name: Mapped[Optional[str]] = mapped_column(Text)
    gpu_vendor: Mapped[Optional[str]] = mapped_column(Text)
    vram_total_mb: Mapped[Optional[int]] = mapped_column(Integer)
    vram_available_mb: Mapped[Optional[int]] = mapped_column(Integer)
    gpu_utilization_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    gpu_temperature_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    supported_task_types: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    installed_model_ids: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    current_job_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("jobs.id", use_alter=True, name="fk_worker_sessions_current_job_id_jobs"),
    )
    connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class AccessKey(Base):
    __tablename__ = "access_keys"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    key_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(Integer)
    allowed_ips: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    allowed_origins: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    requester_user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    worker_user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    worker_session_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("worker_sessions.id", ondelete="SET NULL"))
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    required_model_id: Mapped[Optional[str]] = mapped_column(Text)
    required_vram_gb: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    required_trust_tier: Mapped[Optional[str]] = mapped_column(Text)
    verification_policy: Mapped[Optional[str]] = mapped_column(Text)
    price_limit_credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    estimated_cost_credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    final_cost_credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    worker_reward_credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    platform_fee_credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class JobMessage(Base):
    __tablename__ = "job_messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    parent_message_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("job_messages.id", ondelete="SET NULL"))
    created_by_user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class StoredObject(Base):
    __tablename__ = "stored_objects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_backend: Mapped[str] = mapped_column(Text, nullable=False)
    uri: Mapped[Optional[str]] = mapped_column(Text)
    inline_content: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    mime_type: Mapped[Optional[str]] = mapped_column(Text)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    sha256: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class JobMessagePart(Base):
    __tablename__ = "job_message_parts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    message_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("job_messages.id", ondelete="CASCADE"), nullable=False)
    object_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("stored_objects.id", ondelete="SET NULL"))
    name: Mapped[Optional[str]] = mapped_column(Text)
    part_type: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    required: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    actor_role: Mapped[Optional[str]] = mapped_column(Text)
    from_status: Mapped[Optional[str]] = mapped_column(Text)
    to_status: Mapped[Optional[str]] = mapped_column(Text)
    message_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("job_messages.id", ondelete="SET NULL"))
    object_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("stored_objects.id", ondelete="SET NULL"))
    error_code: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    request_id: Mapped[Optional[str]] = mapped_column(Text)
    trace_id: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class CreditLedger(Base):
    __tablename__ = "credit_ledgers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="SET NULL"))
    counterparty_user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    balance_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    related_ledger_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("credit_ledgers.id", ondelete="SET NULL"))
    idempotency_key: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
