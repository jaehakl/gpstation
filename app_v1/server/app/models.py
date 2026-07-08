from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

UserRole = Literal["admin", "user", "unauthorized"]
AccessKeyScope = Literal["client", "launcher"]


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


class JobLogItem(BaseModel):
    time: str
    stream: str
    line: str


class JobLogResponse(BaseModel):
    items: list[JobLogItem]


from app.routers.v1.models import (  # noqa: E402
    JobAnswerWaitResult,
    JobCreateRequest,
    JobCreateResult,
    JobData,
)
from app.routers.web.models import (  # noqa: E402
    AccessKeyCreate,
    AccessKeyCreateResult,
    AccessKeyData,
    CrudDeleteRequest,
    CrudDeleteResponse,
    CrudListRequest,
    CrudListResponse,
    CrudUpsertRequest,
    CrudUpsertResponse,
)

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
    "JobLogItem",
    "JobLogResponse",
    "UserData",
    "UserRole",
]
