from __future__ import annotations

from typing import Any, Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignalPayload(StrictModel):
    type: Literal["offer", "answer", "ice", "end-of-candidates"]
    sdp: str | None = None
    candidate: str | None = None
    sdpMid: str | None = None
    sdpMLineIndex: int | None = None


class LauncherHello(StrictModel):
    type: Literal["launcher.hello"]
    launcher_name: str
    slave_app_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LauncherHeartbeat(StrictModel):
    type: Literal["launcher.heartbeat"]
    status: Literal["ready", "busy"] = "ready"
    current_job_id: str | None = None
    loaded_slave_app_id: str | None = None
    worker_status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LauncherAccepted(StrictModel):
    type: Literal["launcher.accepted"]
    launcher_id: str
    server_time: str
    capabilities: dict[str, Any] = Field(default_factory=dict)


class JobStart(StrictModel):
    type: Literal["job.start"]
    job_id: str
    handler_type: str
    slave_app_id: str
    offer: SignalPayload


class JobCancel(StrictModel):
    type: Literal["job.cancel"]
    job_id: str
    reason: str = "cancelled"


class WorkerReset(StrictModel):
    type: Literal["worker.reset"]
    reason: str = "reset requested"


class JobAnswer(StrictModel):
    type: Literal["job.answer"]
    job_id: str
    answer: SignalPayload


class JobRunning(StrictModel):
    type: Literal["job.running"]
    job_id: str


class JobProgress(StrictModel):
    type: Literal["job.progress"]
    job_id: str
    progress: Any = None


class JobResult(StrictModel):
    type: Literal["job.result"]
    job_id: str


class JobError(StrictModel):
    type: Literal["job.error"]
    job_id: str
    code: str = "job_error"
    detail: str


class JobCancelled(StrictModel):
    type: Literal["job.cancelled"]
    job_id: str
    reason: str = "cancelled"


class WorkerResetDone(StrictModel):
    type: Literal["worker.reset.done"]


LauncherToServerMessage = Annotated[
    Union[
        LauncherHello,
        LauncherHeartbeat,
        JobAnswer,
        JobRunning,
        JobProgress,
        JobResult,
        JobError,
        JobCancelled,
        WorkerResetDone,
    ],
    Field(discriminator="type"),
]

ServerToLauncherMessage = Annotated[
    Union[
        LauncherAccepted,
        JobStart,
        JobCancel,
        WorkerReset,
    ],
    Field(discriminator="type"),
]

_launcher_to_server_adapter = TypeAdapter(LauncherToServerMessage)
_server_to_launcher_adapter = TypeAdapter(ServerToLauncherMessage)


def parse_launcher_message(value: Any) -> LauncherToServerMessage:
    return _launcher_to_server_adapter.validate_python(value)


def parse_server_message(value: Any) -> ServerToLauncherMessage:
    return _server_to_launcher_adapter.validate_python(value)


class DataChannelAttachment(StrictModel):
    id: str
    name: str | None = None
    mimeType: str | None = None
    size: int | None = Field(default=None, ge=0)
    data: bytes = b""

    @model_validator(mode="after")
    def fill_size(self) -> "DataChannelAttachment":
        if self.size is None:
            self.size = len(self.data)
        return self


class DataChannelMessage(StrictModel):
    id: str
    type: str
    payload: Any = None
    attachments: list[DataChannelAttachment] = Field(default_factory=list)
