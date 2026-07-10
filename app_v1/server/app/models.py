from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

UserRole = Literal["admin", "user", "unauthorized"]
AccessKeyScope = Literal["client", "launcher"]
JobState = Literal[
    "queued",
    "assigned",
    "answer_ready",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "killed",
]


class UserData(BaseModel):
    id: str
    email: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    role: UserRole = "unauthorized"
    status: str = "active"
    is_active: bool = True
    roles: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OkResponse(BaseModel):
    ok: bool = True


class LauncherView(BaseModel):
    id: str
    user_id: str
    launcher_name: str
    status: str
    slave_app_ids: list[str]
    connected_at: datetime
    last_heartbeat_at: datetime
    ip_address: Optional[str] = None
    disconnected_at: Optional[datetime] = None


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handler_type: str = Field(min_length=1, max_length=128)
    slave_app_id: str = Field(default="ai", min_length=1, max_length=128)
    offer: dict[str, Any]


class JobData(BaseModel):
    id: str
    user_id: str
    handler_type: str
    slave_app_id: str
    offer: dict[str, Any]
    answer: dict[str, Any] | None = None
    progress: list[Any] = Field(default_factory=list)
    state: JobState
    launcher_id: str | None = None
    assigned_at: datetime | None = None
    answer_ready_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    last_error: str | None = None
    attempt_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobSummary(BaseModel):
    id: str
    user_id: str
    handler_type: str
    slave_app_id: str
    state: JobState
    launcher_id: str | None = None
    assigned_at: datetime | None = None
    answer_ready_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    last_error: str | None = None
    attempt_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobCreateResult(BaseModel):
    job: JobData
    answer_wait_url: str


class JobAnswerWaitResult(BaseModel):
    job_id: str
    state: JobState
    answer: dict[str, Any] | None = None
    last_error: str | None = None


class CrudListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offset: int = Field(default=0, ge=0)
    limit: int | None = Field(default=100, ge=1, le=1000)
    selected_ids: list[str] = Field(default_factory=list, max_length=1000)
    search_text: str | None = None
    text_filter: dict[str, list[str]] = Field(default_factory=dict)
    filter: dict[str, list[Any]] = Field(default_factory=dict)
    sort: list[str] | None = None


class CrudListResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]


class CrudUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[dict[str, Any]] = Field(max_length=1000)


class CrudUpsertResponse(BaseModel):
    id: str


class CrudDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(max_length=1000)


class CrudDeleteResponse(BaseModel):
    deleted: int


class AccessKeyData(BaseModel):
    id: str
    user_id: str
    key_type: str
    name: str
    key_prefix: str
    scopes: list[str]
    status: str
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class AccessKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    scopes: list[AccessKeyScope] = Field(min_length=1, max_length=2)
    expires_at: Optional[datetime] = None

    @field_validator("scopes", mode="before")
    @classmethod
    def deduplicate_scopes(cls, value: Any) -> Any:
        if isinstance(value, list):
            return list(dict.fromkeys(value))
        return value


class AccessKeyCreateResult(BaseModel):
    access_key: AccessKeyData
    secret: str

__all__ = [
    "AccessKeyCreate",
    "AccessKeyCreateResult",
    "AccessKeyData",
    "AccessKeyScope",
    "CrudDeleteRequest",
    "CrudDeleteResponse",
    "CrudListRequest",
    "CrudListResponse",
    "CrudUpsertRequest",
    "CrudUpsertResponse",
    "LauncherView",
    "OkResponse",
    "JobAnswerWaitResult",
    "JobCreateRequest",
    "JobCreateResult",
    "JobData",
    "JobSummary",
    "JobState",
    "UserData",
    "UserRole",
]
