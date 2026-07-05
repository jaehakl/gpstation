from __future__ import annotations

from typing import Any, Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignalPayload(StrictModel):
    type: Literal["offer", "answer", "ice", "end-of-candidates"]
    sdp: str | None = None
    candidate: str | None = None
    sdpMid: str | None = None
    sdpMLineIndex: int | None = None


class WorkerHello(StrictModel):
    type: Literal["worker.hello"]
    worker_name: str
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerHeartbeat(StrictModel):
    type: Literal["worker.heartbeat"]
    status: Literal["ready", "busy"] = "ready"
    active_session_ids: list[str] = Field(default_factory=list)


class WorkerAccepted(StrictModel):
    type: Literal["worker.accepted"]
    worker_session_id: str
    server_time: str


class SessionStart(StrictModel):
    type: Literal["session.start"]
    session_id: str
    token: str
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


class SignalToWorker(StrictModel):
    type: Literal["signal.to_worker"]
    session_id: str
    signal: SignalPayload


class SignalToClient(StrictModel):
    type: Literal["signal.to_client"]
    session_id: str
    signal: SignalPayload


class Ping(StrictModel):
    type: Literal["ping"]


class Pong(StrictModel):
    type: Literal["pong"]
    server_time: str | None = None


ControlMessage = Annotated[
    Union[
        WorkerHello,
        WorkerHeartbeat,
        WorkerAccepted,
        SessionStart,
        SessionReady,
        SessionStop,
        SessionClosed,
        SessionError,
        SignalToWorker,
        SignalToClient,
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


class DataChannelMessage(StrictModel):
    id: str
    type: Literal["echo.request", "echo.result", "error"]
    payload: Any = None
