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
    active_session_ids: list[str] = Field(default_factory=list)
    current_job_id: str | None = None
    loaded_slave_app_id: str | None = None
    worker_status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LauncherAccepted(StrictModel):
    type: Literal["launcher.accepted"]
    launcher_session_id: str
    server_time: str
    capabilities: dict[str, Any] = Field(default_factory=dict)


class SessionStart(StrictModel):
    type: Literal["session.start"]
    session_id: str
    token: str
    slave_app_id: str
    ttl_seconds: int


class SessionReady(StrictModel):
    type: Literal["session.ready"]
    session_id: str


class SessionStop(StrictModel):
    type: Literal["session.stop"]
    session_id: str
    reason: str = "closed"


class SessionClosed(StrictModel):
    type: Literal["session.closed"]
    session_id: str
    reason: str = "closed"


class SessionError(StrictModel):
    type: Literal["session.error"]
    session_id: str
    code: str
    detail: str


class SessionLog(StrictModel):
    type: Literal["session.log"]
    session_id: str
    time: str
    stream: Literal["stderr"]
    line: str


class SignalToLauncher(StrictModel):
    type: Literal["signal.to_launcher"]
    session_id: str
    signal: SignalPayload


class SignalToClient(StrictModel):
    type: Literal["signal.to_client"]
    session_id: str
    signal: SignalPayload


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


class WorkerResetFailed(StrictModel):
    type: Literal["worker.reset.failed"]
    detail: str


class Ping(StrictModel):
    type: Literal["ping"]


class Pong(StrictModel):
    type: Literal["pong"]
    server_time: str | None = None


ControlMessage = Annotated[
    Union[
        LauncherHello,
        LauncherHeartbeat,
        LauncherAccepted,
        SessionStart,
        SessionReady,
        SessionStop,
        SessionClosed,
        SessionError,
        SessionLog,
        SignalToLauncher,
        SignalToClient,
        JobStart,
        JobCancel,
        WorkerReset,
        JobAnswer,
        JobRunning,
        JobProgress,
        JobResult,
        JobError,
        JobCancelled,
        WorkerResetDone,
        WorkerResetFailed,
        Ping,
        Pong,
    ],
    Field(discriminator="type"),
]

_control_adapter = TypeAdapter(ControlMessage)


def parse_control_message(value: Any) -> ControlMessage:
    return _control_adapter.validate_python(value)


class ClientSignalMessage(StrictModel):
    signal: SignalPayload


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
