from datetime import datetime
from decimal import Decimal
from typing import Any, List, Literal, Optional

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, field_serializer

from utils.datetime_utils import serialize_datetime_utc

UserRole = Literal["admin", "user", "unauthorized"]


class BaseModel(PydanticBaseModel):
    @field_serializer("*", when_used="json")
    def serialize_datetimes(self, value: Any) -> Any:
        return serialize_datetime_utc(value)


class UserData(BaseModel):
    id: str
    email: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    password_hash: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    credit_balance: Optional[Decimal] = None
    credit_pending: Optional[Decimal] = None
    credit_withdrawable: Optional[Decimal] = None
    trust_score: Optional[Decimal] = None
    trust_tier: Optional[str] = None
    success_job_count: Optional[int] = None
    failed_job_count: Optional[int] = None
    disputed_job_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    roles: List[str] = Field(default_factory=list)


class UserAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    password_hash: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[str] = None
    credit_balance: Optional[Decimal] = None
    credit_pending: Optional[Decimal] = None
    credit_withdrawable: Optional[Decimal] = None
    trust_score: Optional[Decimal] = None
    trust_tier: Optional[str] = None
    success_job_count: Optional[int] = None
    failed_job_count: Optional[int] = None
    disputed_job_count: Optional[int] = None
    last_login_at: Optional[datetime] = None
    metadata_json: Optional[dict[str, Any]] = None


class AccessKeyData(BaseModel):
    id: str
    user_id: str
    key_type: str
    name: str
    key_prefix: str
    status: str
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class AccessKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    expires_at: Optional[datetime] = None


class AccessKeyCreateResult(BaseModel):
    access_key: AccessKeyData
    secret: str


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str
    request_json: dict[str, Any]


class JobCreateResult(BaseModel):
    job_id: str
    message_id: str
    task_type: str
    status: str


class JobData(BaseModel):
    id: str
    requester_user_id: str
    worker_user_id: Optional[str] = None
    worker_session_id: Optional[str] = None
    task_type: str
    status: str
    priority: int
    required_model_id: Optional[str] = None
    required_vram_gb: Optional[Decimal] = None
    required_trust_tier: Optional[str] = None
    verification_policy: Optional[str] = None
    price_limit_credit: Optional[Decimal] = None
    estimated_cost_credit: Optional[Decimal] = None
    final_cost_credit: Optional[Decimal] = None
    worker_reward_credit: Optional[Decimal] = None
    platform_fee_credit: Optional[Decimal] = None
    lease_expires_at: Optional[datetime] = None
    retry_count: int
    max_retries: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class JobMessageData(BaseModel):
    id: str
    job_id: str
    kind: str
    role: str
    status: str
    parent_message_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class JobMessagePartData(BaseModel):
    id: str
    message_id: str
    object_id: Optional[str] = None
    name: Optional[str] = None
    part_type: str
    sort_order: int
    required: bool
    created_at: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class StoredObjectData(BaseModel):
    id: str
    object_type: str
    storage_backend: str
    uri: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    created_by_user_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class WorkerSessionData(BaseModel):
    id: str
    user_id: str
    status: str
    accepting_jobs: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    client_version: Optional[str] = None
    gpu_name: Optional[str] = None
    gpu_vendor: Optional[str] = None
    vram_total_mb: Optional[int] = None
    vram_available_mb: Optional[int] = None
    gpu_utilization_pct: Optional[Decimal] = None
    gpu_temperature_c: Optional[Decimal] = None
    supported_task_types: Optional[list[str]] = None
    installed_model_ids: Optional[list[str]] = None
    current_job_id: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class JobDetailData(BaseModel):
    job: JobData
    messages: list[JobMessageData]
    message_parts: list[JobMessagePartData]
    stored_objects: list[StoredObjectData]
    worker_session: Optional[WorkerSessionData] = None
