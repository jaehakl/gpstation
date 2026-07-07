from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sdk.protocol.constants import DATA_CHANNEL_LABEL
from sdk.protocol.messages import DataChannelAttachment, DataChannelMessage

CHUNK_SIZE = 16 * 1024
JOB_RESULT_ACK_TIMEOUT_SECONDS = 5.0
RTC_ICE_SERVERS_ENV = "GPSTATION_V1_RTC_ICE_SERVERS_JSON"
DEFAULT_RTC_ICE_SERVERS = [{"urls": "stun:stun.l.google.com:19302"}]


@dataclass(frozen=True)
class SlaveContext:
    session_id: str
    ttl_seconds: int


@dataclass(frozen=True)
class MessageHandler:
    message_type: str
    handle: Callable[
        [DataChannelMessage, Any, SlaveContext],
        DataChannelMessage | Awaitable[DataChannelMessage | None] | None,
    ]


@dataclass
class PendingAttachment:
    meta: DataChannelAttachment
    chunks: list[bytes] = field(default_factory=list)
    received_size: int = 0
    next_index: int = 0
    complete: bool = False


@dataclass
class PendingCall:
    id: str
    type: str
    payload: Any
    attachments: dict[str, PendingAttachment]

    def is_complete(self) -> bool:
        return all(attachment.complete for attachment in self.attachments.values())

    def to_message(self) -> DataChannelMessage:
        attachments = [
            DataChannelAttachment(
                id=attachment.meta.id,
                name=attachment.meta.name,
                mimeType=attachment.meta.mimeType,
                size=attachment.meta.size,
                data=b"".join(attachment.chunks),
            )
            for attachment in self.attachments.values()
        ]
        return DataChannelMessage(id=self.id, type=self.type, payload=self.payload, attachments=attachments)


class SlaveApp:
    def __init__(self, memory: Any = None) -> None:
        self.memory = memory
        self.handlers: list[MessageHandler] = []
        self.initializer: Callable[[Any, SlaveContext], Awaitable[None] | None] | None = None

    def initialize(self, func: Callable[[Any, SlaveContext], Awaitable[None] | None]) -> Callable[[Any, SlaveContext], Awaitable[None] | None]:
        self.initializer = func
        return func

    def handler(
        self,
        message_type: str,
    ) -> Callable[
        [
            Callable[
                [DataChannelMessage, Any, SlaveContext],
                DataChannelMessage | Awaitable[DataChannelMessage | None] | None,
            ]
        ],
        Callable[
            [DataChannelMessage, Any, SlaveContext],
            DataChannelMessage | Awaitable[DataChannelMessage | None] | None,
        ],
    ]:
        def decorator(
            func: Callable[
                [DataChannelMessage, Any, SlaveContext],
                DataChannelMessage | Awaitable[DataChannelMessage | None] | None,
            ],
        ) -> Callable[
            [DataChannelMessage, Any, SlaveContext],
            DataChannelMessage | Awaitable[DataChannelMessage | None] | None,
        ]:
            self.handlers.append(MessageHandler(message_type=message_type, handle=func))
            return func

        return decorator

    async def run_initialize(self, context: SlaveContext) -> None:
        if self.initializer is None:
            return
        result = self.initializer(self.memory, context)
        if inspect.isawaitable(result):
            await result

    async def dispatch(self, message: DataChannelMessage, context: SlaveContext) -> DataChannelMessage | None:
        for handler in self.handlers:
            if handler.message_type != message.type:
                continue
            response = handler.handle(message, self.memory, context)
            if inspect.isawaitable(response):
                response = await response
            return response
        raise ValueError(f"unsupported data channel message: {message.type}")


def run_app(app: SlaveApp) -> None:
    args = parse_args()
    if args.worker:
        asyncio.run(_run_worker_stdio(app=app))
        return
    if not args.session_id or args.ttl_seconds is None:
        raise SystemExit("--session-id and --ttl-seconds are required unless --worker is set")
    asyncio.run(_run_app_stdio(app=app, session_id=args.session_id, ttl_seconds=args.ttl_seconds))


async def _run_worker_stdio(*, app: SlaveApp) -> None:
    try:
        from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
        from aiortc.sdp import candidate_from_sdp
    except Exception as exc:
        emit({"type": "error", "code": "aiortc_import_failed", "detail": str(exc)})
        return

    try:
        rtc_configuration = build_rtc_configuration(RTCConfiguration, RTCIceServer)
    except Exception as exc:
        emit({"type": "error", "code": "rtc_configuration_failed", "detail": str(exc)})
        return

    try:
        await app.run_initialize(SlaveContext(session_id="worker", ttl_seconds=0))
    except Exception as exc:
        emit({"type": "error", "code": "initialize_failed", "detail": str(exc)})
        return

    emit({"type": "worker.ready"})
    current_job_task: asyncio.Task[None] | None = None
    current_job_id: str | None = None
    try:
        while True:
            if current_job_task is not None and current_job_task.done():
                await drain_worker_job_task(current_job_task)
                current_job_task = None
                current_job_id = None

            line = await asyncio.to_thread(read_stdin_line)
            if not line:
                break
            try:
                message = json.loads(line)
                message_type = message.get("type")
                if message_type == "stop":
                    break
                if message_type == "job.cancel":
                    if current_job_task is not None and current_job_id == str(message.get("job_id")):
                        current_job_task.cancel()
                        await drain_worker_job_task(current_job_task)
                        current_job_task = None
                        current_job_id = None
                    continue
                if message_type == "job.start":
                    if current_job_task is not None and not current_job_task.done():
                        emit(
                            {
                                "type": "job.error",
                                "job_id": str(message.get("job_id") or "unknown"),
                                "code": "worker_busy",
                                "detail": f"worker is busy with job {current_job_id}",
                            }
                        )
                        continue
                    current_job_id = str(message["job_id"])
                    current_job_task = asyncio.create_task(
                        run_worker_job(
                            app=app,
                            message=message,
                            rtc_configuration=rtc_configuration,
                            rtc_session_description=RTCSessionDescription,
                            candidate_from_sdp=candidate_from_sdp,
                        )
                    )
            except Exception as exc:
                emit({"type": "error", "code": "worker_runtime_error", "detail": str(exc)})
    finally:
        if current_job_task is not None and not current_job_task.done():
            current_job_task.cancel()
            await drain_worker_job_task(current_job_task)


async def drain_worker_job_task(task: asyncio.Task[None]) -> None:
    try:
        await task
    except asyncio.CancelledError:
        return
    except Exception as exc:
        emit({"type": "error", "code": "worker_runtime_error", "detail": str(exc)})


async def run_worker_job(
    *,
    app: SlaveApp,
    message: dict[str, Any],
    rtc_configuration: Any,
    rtc_session_description: Any,
    candidate_from_sdp: Any,
) -> None:
    job_id = str(message["job_id"])
    handler_type = str(message["handler_type"])
    context = SlaveContext(session_id=job_id, ttl_seconds=0)
    pc = None
    try:
        from aiortc import RTCPeerConnection

        pc = RTCPeerConnection(rtc_configuration)
        ready_event = asyncio.Event()
        result_ack_event = asyncio.Event()
        closed_event = asyncio.Event()
        channel_holder: dict[str, Any] = {}
        ready_payload: dict[str, Any] = {"input": None}
        ready_error: dict[str, str] = {}

        @pc.on("datachannel")
        def on_datachannel(channel: Any) -> None:
            log(f"job datachannel: {channel.label}")
            channel_holder["channel"] = channel

            @channel.on("message")
            def on_message(raw_message: Any) -> None:
                try:
                    if isinstance(raw_message, str):
                        is_ready_message, input_payload, error_detail = parse_job_ready_message(raw_message, job_id)
                        if is_ready_message:
                            if error_detail is not None:
                                ready_error["detail"] = error_detail
                            else:
                                ready_payload["input"] = input_payload
                            ready_event.set()
                            return
                        payload = json.loads(raw_message)
                        if payload.get("kind") == "job.result.ack" and str(payload.get("id")) == job_id:
                            result_ack_event.set()
                            return
                        if not ready_event.is_set():
                            ready_error["detail"] = f"expected job.ready before {payload.get('kind') or 'unknown message'}"
                            ready_event.set()
                            return
                    log(f"unsupported worker job datachannel message: {raw_message}")
                except Exception as exc:
                    if not ready_event.is_set():
                        ready_error["detail"] = f"malformed job.ready frame: {exc}"
                        ready_event.set()
                        return
                    log(f"job datachannel message error: {exc}")

            @channel.on("close")
            def on_close() -> None:
                log("job datachannel closed")
                closed_event.set()

            @channel.on("error")
            def on_error(error: Exception | None = None) -> None:
                log(f"job datachannel error: {error}")
                closed_event.set()

        @pc.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            log(f"job peer connection state: {pc.connectionState}")
            if pc.connectionState in {"closed", "failed", "disconnected"}:
                closed_event.set()

        offer = message["offer"]
        log(f"job offer candidates: {format_candidate_summary(summarize_sdp_candidates(offer['sdp']))}")
        await pc.setRemoteDescription(rtc_session_description(sdp=offer["sdp"], type="offer"))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await wait_for_ice_gathering(pc)
        log(f"job answer candidates: {format_candidate_summary(summarize_sdp_candidates(pc.localDescription.sdp))}")
        emit(
            {
                "type": "job.answer",
                "job_id": job_id,
                "answer": {"type": "answer", "sdp": pc.localDescription.sdp},
            }
        )

        ready_task = asyncio.create_task(ready_event.wait())
        closed_task = asyncio.create_task(closed_event.wait())
        done, pending = await asyncio.wait({ready_task, closed_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if closed_task in done and not ready_event.is_set():
            raise RuntimeError("peer connection closed before job ready")
        if ready_error:
            raise RuntimeError(ready_error["detail"])

        channel = channel_holder.get("channel")
        if channel is None:
            raise RuntimeError("datachannel was not opened")
        emit({"type": "job.running", "job_id": job_id})
        response = await app.dispatch(
            DataChannelMessage(id=job_id, type=handler_type, payload=ready_payload.get("input"), attachments=[]),
            context,
        )
        if response is None:
            response = DataChannelMessage(id=job_id, type=f"{handler_type}.result", payload=None)
        send_job_result(channel, job_id, response)
        log(f"job result sent: id={job_id}")
        log(f"job result ack wait: id={job_id} timeout_s={JOB_RESULT_ACK_TIMEOUT_SECONDS:g}")
        await wait_for_job_result_ack(job_id, result_ack_event, closed_event)
        log(f"job result ack received: id={job_id}")
        emit(
            {
                "type": "job.result",
                "job_id": job_id,
            }
        )
    except asyncio.CancelledError:
        log(f"job cancelled: id={job_id}")
        channel = locals().get("channel_holder", {}).get("channel")
        if channel is not None:
            try:
                channel.send(
                    json.dumps(
                        {"kind": "job.error", "id": job_id, "code": "cancelled", "detail": "job cancelled"},
                        ensure_ascii=False,
                    )
                )
            except Exception:
                pass
        emit({"type": "job.cancelled", "job_id": job_id, "reason": "cancelled"})
    except Exception as exc:
        log(f"job failed: id={job_id} error={exc}")
        channel = locals().get("channel_holder", {}).get("channel")
        if channel is not None:
            try:
                channel.send(json.dumps({"kind": "job.error", "id": job_id, "detail": str(exc)}, ensure_ascii=False))
            except Exception:
                pass
        emit({"type": "job.error", "job_id": job_id, "code": "job_error", "detail": str(exc)})
    finally:
        if pc is not None:
            await pc.close()


def parse_job_ready_message(raw_message: str, job_id: str) -> tuple[bool, Any, str | None]:
    try:
        payload = json.loads(raw_message)
    except Exception as exc:
        return True, None, f"malformed job.ready frame: {exc}"
    if payload.get("kind") != "job.ready":
        return False, None, None
    if str(payload.get("id")) != job_id:
        return True, None, f"job.ready id mismatch: expected {job_id}, got {payload.get('id')}"
    return True, payload.get("input"), None


async def wait_for_job_result_ack(
    job_id: str,
    ack_event: asyncio.Event,
    closed_event: asyncio.Event,
    timeout_seconds: float = JOB_RESULT_ACK_TIMEOUT_SECONDS,
) -> None:
    ack_task = asyncio.create_task(ack_event.wait())
    closed_task = asyncio.create_task(closed_event.wait())
    try:
        done, pending = await asyncio.wait({ack_task, closed_task}, timeout=timeout_seconds, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if not done:
            raise RuntimeError(f"result delivery ack timeout: {job_id}")
        if ack_task in done and ack_event.is_set():
            return
        raise RuntimeError(f"data channel closed before result delivery ack: {job_id}")
    finally:
        for task in (ack_task, closed_task):
            if not task.done():
                task.cancel()


async def _run_app_stdio(
    *,
    app: SlaveApp,
    session_id: str,
    ttl_seconds: int,
) -> None:
    context = SlaveContext(session_id=session_id, ttl_seconds=ttl_seconds)
    try:
        from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
        from aiortc.sdp import candidate_from_sdp
    except Exception as exc:
        emit({"type": "error", "code": "aiortc_import_failed", "detail": str(exc)})
        return

    try:
        rtc_configuration = build_rtc_configuration(RTCConfiguration, RTCIceServer)
    except Exception as exc:
        emit({"type": "error", "code": "rtc_configuration_failed", "detail": str(exc)})
        return

    try:
        await app.run_initialize(context)
    except Exception as exc:
        emit({"type": "error", "code": "initialize_failed", "detail": str(exc)})
        return

    pc = RTCPeerConnection(rtc_configuration)
    closed = asyncio.Event()
    pending_calls: dict[str, PendingCall] = {}

    @pc.on("datachannel")
    def on_datachannel(channel: Any) -> None:
        log(f"datachannel: {channel.label}")

        @channel.on("message")
        def on_message(message: Any) -> None:
            log("datachannel message received")
            asyncio.create_task(handle_datachannel_message(channel, message, app, context, pending_calls))

    @pc.on("connectionstatechange")
    async def on_connectionstatechange() -> None:
        log(f"peer connection state: {pc.connectionState}")
        if pc.connectionState in {"closed", "failed", "disconnected"}:
            closed.set()

    @pc.on("iceconnectionstatechange")
    def on_iceconnectionstatechange() -> None:
        log(f"ICE connection state: {pc.iceConnectionState}")

    @pc.on("icegatheringstatechange")
    def on_icegatheringstatechange_log() -> None:
        log(f"ICE gathering state: {pc.iceGatheringState}")

    emit({"type": "ready", "session_id": session_id})

    try:
        while not closed.is_set():
            line = await asyncio.to_thread(read_stdin_line)
            if not line:
                break
            message = json.loads(line)
            if message.get("type") == "stop":
                break
            if message.get("type") == "signal":
                await handle_signal(pc, message["signal"], RTCSessionDescription, candidate_from_sdp)
    except Exception as exc:
        emit({"type": "error", "code": "runtime_error", "detail": str(exc)})
    finally:
        await pc.close()
        emit({"type": "closed", "session_id": session_id})


async def handle_signal(
    pc: Any,
    signal: dict[str, Any],
    rtc_session_description: Any,
    candidate_from_sdp: Any,
) -> None:
    signal_type = signal.get("type")
    if signal_type == "offer":
        log(f"received offer candidates: {format_candidate_summary(summarize_sdp_candidates(signal['sdp']))}")
        await pc.setRemoteDescription(rtc_session_description(sdp=signal["sdp"], type="offer"))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await wait_for_ice_gathering(pc)
        log(f"created answer candidates: {format_candidate_summary(summarize_sdp_candidates(pc.localDescription.sdp))}")
        emit(
            {
                "type": "signal",
                "signal": {
                    "type": "answer",
                    "sdp": pc.localDescription.sdp,
                },
            }
        )
        return
    if signal_type == "ice":
        candidate_text = signal.get("candidate")
        if not candidate_text:
            await pc.addIceCandidate(None)
            log("received end-of-candidates")
            return
        if candidate_text.startswith("candidate:"):
            candidate_text = candidate_text.removeprefix("candidate:")
        candidate = candidate_from_sdp(candidate_text)
        candidate.sdpMid = signal.get("sdpMid")
        candidate.sdpMLineIndex = signal.get("sdpMLineIndex")
        await pc.addIceCandidate(candidate)
        log("received remote ICE candidate")


def build_rtc_configuration(rtc_configuration_cls: Any, rtc_ice_server_cls: Any) -> Any:
    return rtc_configuration_cls(
        iceServers=[
            rtc_ice_server_cls(**ice_server_kwargs(item))
            for item in load_rtc_ice_servers()
        ]
    )


def load_rtc_ice_servers() -> list[dict[str, Any]]:
    raw_value = os.environ.get(RTC_ICE_SERVERS_ENV, "").strip()
    if not raw_value:
        return [dict(item) for item in DEFAULT_RTC_ICE_SERVERS]
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{RTC_ICE_SERVERS_ENV} must be valid JSON: {exc.msg}") from exc
    return validate_rtc_ice_servers(parsed)


def validate_rtc_ice_servers(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{RTC_ICE_SERVERS_ENV} must be a JSON array")
    servers: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{RTC_ICE_SERVERS_ENV}[{index}] must be an object")
        urls = item.get("urls")
        if not (isinstance(urls, str) or is_string_list(urls)):
            raise ValueError(f"{RTC_ICE_SERVERS_ENV}[{index}].urls must be a string or string array")
        server = {"urls": urls}
        for key in ("username", "credential", "credentialType"):
            optional_value = item.get(key)
            if optional_value is None:
                continue
            if not isinstance(optional_value, str):
                raise ValueError(f"{RTC_ICE_SERVERS_ENV}[{index}].{key} must be a string")
            server[key] = optional_value
        servers.append(server)
    return servers


def ice_server_kwargs(server: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in server.items() if key in {"urls", "username", "credential", "credentialType"}}


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def summarize_sdp_candidates(sdp: str) -> dict[str, int]:
    summary = {"host": 0, "srflx": 0, "relay": 0, "prflx": 0, "unknown": 0, "total": 0}
    for line in sdp.splitlines():
        if not line.startswith("a=candidate:"):
            continue
        summary["total"] += 1
        parts = line.split()
        candidate_type = parts[parts.index("typ") + 1] if "typ" in parts and parts.index("typ") + 1 < len(parts) else "unknown"
        if candidate_type in {"host", "srflx", "relay", "prflx"}:
            summary[candidate_type] += 1
        else:
            summary["unknown"] += 1
    return summary


def format_candidate_summary(summary: dict[str, int]) -> str:
    return (
        f"total={summary['total']} host={summary['host']} srflx={summary['srflx']} "
        f"relay={summary['relay']} prflx={summary['prflx']} unknown={summary['unknown']}"
    )


async def wait_for_ice_gathering(pc: Any) -> None:
    if pc.iceGatheringState == "complete":
        return
    loop = asyncio.get_running_loop()
    done = loop.create_future()

    @pc.on("icegatheringstatechange")
    def on_icegatheringstatechange() -> None:
        if pc.iceGatheringState == "complete" and not done.done():
            done.set_result(None)

    try:
        await asyncio.wait_for(done, timeout=5)
    except TimeoutError:
        return


async def handle_datachannel_message(
    channel: Any,
    raw_message: Any,
    app: SlaveApp,
    context: SlaveContext,
    pending_calls: dict[str, PendingCall] | None = None,
) -> None:
    calls = pending_calls if pending_calls is not None else {}
    try:
        if channel.label != DATA_CHANNEL_LABEL:
            raise ValueError(f"unsupported data channel label: {channel.label}")
        if isinstance(raw_message, str):
            await handle_control_frame(channel, raw_message, app, context, calls)
            return
        await handle_binary_frame(channel, raw_message, app, context, calls)
    except Exception as exc:
        log(f"datachannel error: {exc}")
        send_error(channel, error_call_id(raw_message), str(exc))


async def handle_control_frame(
    channel: Any,
    raw_message: str,
    app: SlaveApp,
    context: SlaveContext,
    pending_calls: dict[str, PendingCall],
) -> None:
    frame = json.loads(raw_message)
    if frame.get("kind") != "call.request":
        raise ValueError(f"unsupported data channel frame: {frame.get('kind')}")
    call_id = str(frame["id"])
    attachments = {
        str(item["id"]): PendingAttachment(
            meta=DataChannelAttachment(
                id=str(item["id"]),
                name=item.get("name"),
                mimeType=item.get("mimeType"),
                size=int(item.get("size") or 0),
            )
        )
        for item in frame.get("attachments", [])
    }
    call = PendingCall(id=call_id, type=str(frame["type"]), payload=frame.get("payload"), attachments=attachments)
    if not attachments:
        await dispatch_call(channel, app, context, call)
        return
    pending_calls[call_id] = call


async def handle_binary_frame(
    channel: Any,
    raw_message: Any,
    app: SlaveApp,
    context: SlaveContext,
    pending_calls: dict[str, PendingCall],
) -> None:
    header, body = decode_binary_frame(raw_message)
    if header.get("kind") != "attachment.chunk":
        raise ValueError(f"unsupported binary frame: {header.get('kind')}")
    call_id = str(header["callId"])
    attachment_id = str(header["attachmentId"])
    call = pending_calls.get(call_id)
    if call is None:
        raise ValueError(f"unknown call for attachment chunk: {call_id}")
    attachment = call.attachments.get(attachment_id)
    if attachment is None:
        raise ValueError(f"unknown attachment chunk: {attachment_id}")
    index = int(header["index"])
    if index != attachment.next_index:
        raise ValueError(f"out-of-order attachment chunk: {attachment_id}")
    if attachment.complete:
        raise ValueError(f"attachment chunk after final: {attachment_id}")

    attachment.chunks.append(body)
    attachment.received_size += len(body)
    attachment.next_index += 1
    attachment.complete = bool(header.get("final"))

    expected_size = attachment.meta.size or 0
    if attachment.received_size > expected_size:
        raise ValueError(f"attachment exceeded declared size: {attachment_id}")
    if attachment.complete and attachment.received_size != expected_size:
        raise ValueError(f"attachment size mismatch: {attachment_id}")

    if call.is_complete():
        pending_calls.pop(call_id, None)
        await dispatch_call(channel, app, context, call)


async def dispatch_call(channel: Any, app: SlaveApp, context: SlaveContext, call: PendingCall) -> None:
    started_at = time.perf_counter()
    log(f"call dispatch start: id={call.id} type={call.type} attachments={len(call.attachments)}")
    try:
        response = await app.dispatch(call.to_message(), context)
        if response is None:
            response = DataChannelMessage(id=call.id, type=f"{call.type}.result", payload=None)
        send_response(channel, response)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        log(f"call dispatch complete: id={call.id} type={call.type} duration_ms={duration_ms}")
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        log(f"call dispatch failed: id={call.id} type={call.type} duration_ms={duration_ms} error={exc}")
        send_error(channel, call.id, str(exc))


def send_response(channel: Any, message: DataChannelMessage) -> None:
    attachments = [attachment_metadata(attachment) for attachment in message.attachments]
    channel.send(
        json.dumps(
            {
                "kind": "call.response",
                "id": message.id,
                "type": message.type,
                "payload": message.payload,
                "attachments": attachments,
            },
            ensure_ascii=False,
        )
    )
    for attachment in message.attachments:
        send_attachment(channel, message.id, attachment)


def send_job_result(channel: Any, job_id: str, message: DataChannelMessage) -> None:
    attachments = [attachment_metadata(attachment) for attachment in message.attachments]
    channel.send(
        json.dumps(
            {
                "kind": "job.result",
                "id": job_id,
                "type": message.type,
                "payload": message.payload,
                "attachments": attachments,
            },
            ensure_ascii=False,
        )
    )
    for attachment in message.attachments:
        send_attachment(channel, job_id, attachment)


def send_error(channel: Any, call_id: str, detail: str, code: str = "call_error") -> None:
    channel.send(json.dumps({"kind": "call.error", "id": call_id, "code": code, "detail": detail}, ensure_ascii=False))


def send_attachment(channel: Any, call_id: str, attachment: DataChannelAttachment) -> None:
    data = attachment.data
    if not data:
        channel.send(encode_binary_frame({"kind": "attachment.chunk", "callId": call_id, "attachmentId": attachment.id, "index": 0, "final": True}, b""))
        return
    index = 0
    for offset in range(0, len(data), CHUNK_SIZE):
        chunk = data[offset : offset + CHUNK_SIZE]
        final = offset + CHUNK_SIZE >= len(data)
        channel.send(
            encode_binary_frame(
                {
                    "kind": "attachment.chunk",
                    "callId": call_id,
                    "attachmentId": attachment.id,
                    "index": index,
                    "final": final,
                },
                chunk,
            )
        )
        index += 1


def attachment_metadata(attachment: DataChannelAttachment) -> dict[str, Any]:
    metadata: dict[str, Any] = {"id": attachment.id, "size": attachment.size or len(attachment.data)}
    if attachment.name is not None:
        metadata["name"] = attachment.name
    if attachment.mimeType is not None:
        metadata["mimeType"] = attachment.mimeType
    return metadata


def encode_binary_frame(header: dict[str, Any], body: bytes) -> bytes:
    header_bytes = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return len(header_bytes).to_bytes(4, "big") + header_bytes + body


def decode_binary_frame(raw_message: Any) -> tuple[dict[str, Any], bytes]:
    data = bytes(raw_message)
    if len(data) < 4:
        raise ValueError("binary frame is too short")
    header_length = int.from_bytes(data[:4], "big")
    if header_length <= 0 or len(data) < 4 + header_length:
        raise ValueError("invalid binary frame header length")
    header = json.loads(data[4 : 4 + header_length].decode("utf-8"))
    return header, data[4 + header_length :]


def error_call_id(raw_message: Any) -> str:
    try:
        if isinstance(raw_message, str):
            return str(json.loads(raw_message).get("id") or "error")
        header, _body = decode_binary_frame(raw_message)
        return str(header.get("callId") or "error")
    except Exception:
        return "error"


def read_stdin_line() -> str:
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is None:
        return sys.stdin.readline()
    raw_line = buffer.readline()
    if not raw_line:
        return ""
    return raw_line.decode("utf-8")


def emit(message: dict[str, Any]) -> None:
    line = json.dumps(message, ensure_ascii=False) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(line)
        sys.stdout.flush()
        return
    buffer.write(line.encode("utf-8"))
    buffer.flush()


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--session-id")
    parser.add_argument("--ttl-seconds", type=int)
    return parser.parse_args()
