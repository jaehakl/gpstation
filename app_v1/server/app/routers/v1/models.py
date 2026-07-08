from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handler_type: str
    slave_app_id: str = "ai"
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


class JobCreateResult(BaseModel):
    job: JobData
    answer_wait_url: str


class JobAnswerWaitResult(BaseModel):
    job_id: str
    state: JobState
    answer: dict[str, Any] | None = None
    last_error: str | None = None
