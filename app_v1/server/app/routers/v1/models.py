from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
