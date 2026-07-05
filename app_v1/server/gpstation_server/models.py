from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkerSessionView(BaseModel):
    id: str
    user_id: str
    worker_name: str
    status: str
    capabilities: list[str]
    active_session_count: int
    connected_at: datetime
    last_heartbeat_at: datetime


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_session_id: str
    ttl_seconds: int | None = Field(default=None, ge=10, le=3600)


class SessionCreateResult(BaseModel):
    session_id: str
    worker_session_id: str
    signaling_url: str
    token: str
    expires_at: datetime
