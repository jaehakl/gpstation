from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

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


class UserAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[str] = None


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

    name: str
    scopes: list[AccessKeyScope] = Field(default_factory=lambda: ["client", "launcher"])
    expires_at: Optional[datetime] = None


class AccessKeyCreateResult(BaseModel):
    access_key: AccessKeyData
    secret: str


class LauncherSessionView(BaseModel):
    id: str
    user_id: str
    launcher_name: str
    status: str
    slave_app_ids: list[str]
    active_session_count: int
    connected_at: datetime
    last_heartbeat_at: datetime
    ip_address: Optional[str] = None
    disconnected_at: Optional[datetime] = None


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    launcher_session_id: str
    slave_app_id: str = "echo"
    ttl_seconds: int | None = Field(default=None, ge=10, le=3600)


class SessionCreateResult(BaseModel):
    session_id: str
    launcher_session_id: str
    slave_app_id: str
    signaling_url: str
    token: str
    expires_at: datetime


class SlaveSessionData(BaseModel):
    id: str
    user_id: str
    launcher_id: Optional[str] = None
    slave_app_id: str
    master_ip_address: Optional[str] = None
    master_user_agent: Optional[str] = None
    status: str
    ttl_seconds: int
    expires_at: datetime
    ready_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DashboardSummary(BaseModel):
    launchers: int
    active_sessions: int
    users: int
    access_keys: int


class OkResponse(BaseModel):
    ok: bool = True
