from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from sdk.protocol.messages import DataChannelMessage

from sdk.slave.app import SlaveApp, SlaveContext
from sdk.slave.channel import send_job_result
from sdk.slave.config import (
    RTC_ICE_GATHER_TIMEOUT_ENV,
    build_rtc_configuration,
    configure_aioice_gather_timeout,
    iter_rtc_ice_server_urls,
    load_rtc_ice_gather_timeout_seconds,
    load_rtc_ice_servers,
    load_rtc_memory_cache_enabled,
)
from sdk.slave.io import emit, log, read_stdin_line
from sdk.slave.rtc import (
    PreparedWorkerPeer,
    elapsed_ms,
    format_candidate_summary,
    maybe_await,
    prepare_worker_peer,
    summarize_sdp_candidates,
)

JOB_RESULT_ACK_TIMEOUT_SECONDS = 5.0
JOB_DATA_CHANNEL_MESSAGE_MAX_BYTES = 1024 * 1024


@dataclass
class WorkerJobPeerState:
    ready_event: asyncio.Event = field(default_factory=asyncio.Event)
    closed_event: asyncio.Event = field(default_factory=asyncio.Event)
    finish_event: asyncio.Event = field(default_factory=asyncio.Event)
    call_queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    result_ack_events: dict[str, asyncio.Event] = field(default_factory=dict)
    channel_holder: dict[str, Any] = field(default_factory=dict)
    ready_error: dict[str, str] = field(default_factory=dict)
    call_in_progress: bool = False


async def _run_worker_stdio(*, app: SlaveApp) -> None:
    try:
        from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
        from aioice.ice import Connection as AioIceConnection
    except Exception as exc:
        emit({"type": "error", "code": "aiortc_import_failed", "detail": str(exc)})
        return

    try:
        ice_servers = load_rtc_ice_servers()
        ice_gather_timeout_seconds = load_rtc_ice_gather_timeout_seconds(ice_servers)
        memory_cache_enabled = load_rtc_memory_cache_enabled()
        configure_aioice_gather_timeout(AioIceConnection, ice_gather_timeout_seconds)
        rtc_configuration = build_rtc_configuration(RTCConfiguration, RTCIceServer, ice_servers)
        log(f"RTC ICE gather timeout: {ice_gather_timeout_seconds:g}s")
        log(f"RTC memory cache enabled: {memory_cache_enabled}")
    except Exception as exc:
        emit({"type": "error", "code": "rtc_configuration_failed", "detail": str(exc)})
        return

    prepared_peer: PreparedWorkerPeer | None = None
    prepare_task = (
        asyncio.create_task(prepare_worker_peer(RTCPeerConnection, rtc_configuration, label="worker"))
        if memory_cache_enabled
        else None
    )
    try:
        await app.run_initialize(SlaveContext(session_id="worker", ttl_seconds=0))
        if prepare_task is not None:
            try:
                prepared_peer = await prepare_task
            except Exception as exc:
                memory_cache_enabled = False
                log(f"worker ICE memory cache disabled: {exc}")
    except Exception as exc:
        if prepare_task is not None and not prepare_task.done():
            prepare_task.cancel()
        if prepare_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await prepare_task
        emit({"type": "error", "code": "initialize_failed", "detail": str(exc)})
        return

    emit({"type": "worker.ready"})
    current_job_task: asyncio.Task[None] | None = None
    current_job_id: str | None = None
    stdin_task: asyncio.Task[str] | None = asyncio.create_task(asyncio.to_thread(read_stdin_line))
    try:
        while True:
            wait_tasks: set[asyncio.Task[Any]] = set()
            if stdin_task is not None:
                wait_tasks.add(stdin_task)
            if current_job_task is not None:
                wait_tasks.add(current_job_task)
            if not wait_tasks:
                break
            done, _pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)

            if current_job_task is not None and current_job_task in done:
                await drain_worker_job_task(current_job_task)
                current_job_task = None
                current_job_id = None
                if memory_cache_enabled and prepared_peer is None:
                    try:
                        prepared_peer = await prepare_worker_peer(RTCPeerConnection, rtc_configuration, label="worker")
                    except Exception as exc:
                        memory_cache_enabled = False
                        log(f"worker ICE memory cache disabled: {exc}")

            if stdin_task is None or stdin_task not in done:
                continue

            line = stdin_task.result()
            stdin_task = None
            if not line:
                break
            should_stop = False
            try:
                message = json.loads(line)
                message_type = message.get("type")
                if message_type == "stop":
                    should_stop = True
                if message_type == "job.cancel":
                    if current_job_task is not None and current_job_id == str(message.get("job_id")):
                        current_job_task.cancel()
                        await drain_worker_job_task(current_job_task)
                        current_job_task = None
                        current_job_id = None
                        if memory_cache_enabled and prepared_peer is None:
                            try:
                                prepared_peer = await prepare_worker_peer(RTCPeerConnection, rtc_configuration, label="worker")
                            except Exception as exc:
                                memory_cache_enabled = False
                                log(f"worker ICE memory cache disabled: {exc}")
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
                    else:
                        current_job_id = str(message["job_id"])
                        job_prepared_peer = prepared_peer
                        prepared_peer = None
                        current_job_task = asyncio.create_task(
                            run_worker_job(
                                app=app,
                                message=message,
                                rtc_configuration=rtc_configuration,
                                rtc_peer_connection_cls=RTCPeerConnection,
                                rtc_session_description=RTCSessionDescription,
                                ice_servers=ice_servers,
                                prepared_peer=job_prepared_peer,
                            )
                        )
            except Exception as exc:
                emit({"type": "error", "code": "worker_runtime_error", "detail": str(exc)})
            if should_stop:
                break
            stdin_task = asyncio.create_task(asyncio.to_thread(read_stdin_line))
    finally:
        if stdin_task is not None and not stdin_task.done():
            stdin_task.cancel()
        if current_job_task is not None and not current_job_task.done():
            current_job_task.cancel()
            await drain_worker_job_task(current_job_task)
        if prepared_peer is not None:
            await maybe_await(prepared_peer.pc.close())


async def drain_worker_job_task(task: asyncio.Task[None]) -> None:
    try:
        await task
    except asyncio.CancelledError:
        return
    except Exception as exc:
        emit({"type": "error", "code": "worker_runtime_error", "detail": str(exc)})


def create_worker_job_peer(
    rtc_peer_connection_cls: Any,
    rtc_configuration: Any,
    prepared_peer: PreparedWorkerPeer | None,
    job_id: str,
    handler_type: str,
    job_started_at: float,
) -> tuple[Any, WorkerJobPeerState, bool]:
    if prepared_peer is not None:
        pc = prepared_peer.pc
        used_prepared_peer = True
        log(
            f"job peer connection prepared cache hit: id={job_id} "
            f"age_ms={elapsed_ms(prepared_peer.created_at)}"
        )
    else:
        pc = rtc_peer_connection_cls(rtc_configuration)
        used_prepared_peer = False
        log(f"job peer connection created: id={job_id} duration_ms={elapsed_ms(job_started_at)}")
    return pc, attach_worker_job_peer_handlers(pc, job_id, handler_type, job_started_at), used_prepared_peer


def attach_worker_job_peer_handlers(pc: Any, job_id: str, handler_type: str, job_started_at: float) -> WorkerJobPeerState:
    state = WorkerJobPeerState()

    @pc.on("datachannel")
    def on_datachannel(channel: Any) -> None:
        log(f"job datachannel: {channel.label}")
        state.channel_holder["channel"] = channel

        @channel.on("message")
        def on_message(raw_message: Any) -> None:
            try:
                if isinstance(raw_message, (bytes, bytearray, memoryview)):
                    size = len(raw_message)
                    detail = (
                        f"binary job DataChannel message exceeds {JOB_DATA_CHANNEL_MESSAGE_MAX_BYTES} bytes"
                        if size > JOB_DATA_CHANNEL_MESSAGE_MAX_BYTES
                        else "binary job DataChannel messages are unsupported"
                    )
                    if not state.ready_event.is_set():
                        state.ready_error["detail"] = detail
                        state.ready_event.set()
                    log(f"job datachannel message rejected: {detail}; size={size}")
                    return
                if isinstance(raw_message, str):
                    if len(raw_message.encode("utf-8")) > JOB_DATA_CHANNEL_MESSAGE_MAX_BYTES:
                        raise ValueError(f"job DataChannel message exceeds {JOB_DATA_CHANNEL_MESSAGE_MAX_BYTES} bytes")
                    payload = json.loads(raw_message)
                    kind = payload.get("kind")
                    if kind == "job.ready":
                        if str(payload.get("id")) != job_id:
                            state.ready_error["detail"] = f"job.ready id mismatch: expected {job_id}, got {payload.get('id')}"
                        else:
                            log(f"job ready received: id={job_id} duration_ms={elapsed_ms(job_started_at)}")
                            if "input" in payload:
                                state.call_queue.put_nowait(
                                    {
                                        "id": job_id,
                                        "type": handler_type,
                                        "payload": payload.get("input"),
                                    }
                                )
                        state.ready_event.set()
                        return
                    if kind == "job.call":
                        call_id = str(payload.get("id") or "")
                        call_type = payload.get("type")
                        if not state.ready_event.is_set():
                            state.ready_error["detail"] = f"expected job.ready before {kind}"
                            state.ready_event.set()
                            return
                        if not call_id or not isinstance(call_type, str) or not call_type:
                            send_job_error(channel, call_id or job_id, "invalid_call", "job.call requires id and type")
                            return
                        if state.call_in_progress or not state.call_queue.empty():
                            send_job_error(channel, call_id, "worker_busy", "worker is already processing a job call")
                            return
                        state.call_queue.put_nowait(
                            {
                                "id": call_id,
                                "type": call_type,
                                "payload": payload.get("payload"),
                            }
                        )
                        return
                    if kind == "job.result.ack":
                        ack_event = state.result_ack_events.get(str(payload.get("id") or ""))
                        if ack_event is not None:
                            ack_event.set()
                        return
                    if kind == "job.finish":
                        if str(payload.get("id")) != job_id:
                            log(f"job finish id mismatch: expected {job_id}, got {payload.get('id')}")
                            return
                        state.finish_event.set()
                        return
                    if not state.ready_event.is_set():
                        state.ready_error["detail"] = f"expected job.ready before {kind or 'unknown message'}"
                        state.ready_event.set()
                        return
                log(f"unsupported worker job datachannel message type: {type(raw_message).__name__}")
            except Exception as exc:
                if not state.ready_event.is_set():
                    state.ready_error["detail"] = f"malformed job.ready frame: {exc}"
                    state.ready_event.set()
                    return
                log(f"job datachannel message error: {exc}")

        @channel.on("close")
        def on_close() -> None:
            log("job datachannel closed")
            state.closed_event.set()

        @channel.on("error")
        def on_error(error: Exception | None = None) -> None:
            log(f"job datachannel error: {error}")
            state.closed_event.set()

    @pc.on("connectionstatechange")
    async def on_connectionstatechange() -> None:
        log(f"job peer connection state: {pc.connectionState}")
        if pc.connectionState in {"closed", "failed", "disconnected"}:
            state.closed_event.set()

    return state


async def build_worker_job_answer(
    pc: Any,
    offer: dict[str, Any],
    rtc_session_description: Any,
    ice_servers: list[dict[str, Any]],
    job_id: str,
) -> str:
    log(f"job offer candidates: {format_candidate_summary(summarize_sdp_candidates(offer['sdp']))}")
    remote_started_at = time.perf_counter()
    await pc.setRemoteDescription(rtc_session_description(sdp=offer["sdp"], type="offer"))
    log(f"job remote offer set: id={job_id} duration_ms={elapsed_ms(remote_started_at)}")
    answer_started_at = time.perf_counter()
    answer = await pc.createAnswer()
    log(f"job answer created: id={job_id} duration_ms={elapsed_ms(answer_started_at)}")
    local_started_at = time.perf_counter()
    await pc.setLocalDescription(answer)
    log(f"job local answer set and ICE gathered: id={job_id} duration_ms={elapsed_ms(local_started_at)}")
    log(f"job post-setLocal ICE state: id={job_id} state={pc.iceGatheringState}")
    answer_summary = summarize_sdp_candidates(pc.localDescription.sdp)
    log(f"job answer candidates: {format_candidate_summary(answer_summary)}")
    has_stun_server = any(url.startswith(("stun:", "stuns:")) for url in iter_rtc_ice_server_urls(ice_servers))
    if answer_summary["srflx"] == 0 and has_stun_server:
        log(
            f"job {job_id} warning: no srflx ICE candidates gathered; "
            f"consider increasing {RTC_ICE_GATHER_TIMEOUT_ENV}"
        )
    return pc.localDescription.sdp


async def run_worker_job(
    *,
    app: SlaveApp,
    message: dict[str, Any],
    rtc_configuration: Any,
    rtc_peer_connection_cls: Any,
    rtc_session_description: Any,
    ice_servers: list[dict[str, Any]],
    prepared_peer: PreparedWorkerPeer | None = None,
) -> None:
    job_id = str(message["job_id"])
    handler_type = str(message["handler_type"])
    context = SlaveContext(session_id=job_id, ttl_seconds=0)
    pc = None
    state: WorkerJobPeerState | None = None
    try:
        job_started_at = time.perf_counter()
        pc, state, used_prepared_peer = create_worker_job_peer(
            rtc_peer_connection_cls,
            rtc_configuration,
            prepared_peer,
            job_id,
            handler_type,
            job_started_at,
        )
        try:
            answer_sdp = await build_worker_job_answer(
                pc,
                message["offer"],
                rtc_session_description,
                ice_servers,
                job_id,
            )
        except Exception as exc:
            if not used_prepared_peer:
                raise
            log(f"job prepared peer failed before answer: id={job_id} error={exc}; retrying cold peer")
            await maybe_await(pc.close())
            pc, state, _used_prepared_peer = create_worker_job_peer(
                rtc_peer_connection_cls,
                rtc_configuration,
                None,
                job_id,
                handler_type,
                job_started_at,
            )
            answer_sdp = await build_worker_job_answer(
                pc,
                message["offer"],
                rtc_session_description,
                ice_servers,
                job_id,
            )
        emit(
            {
                "type": "job.answer",
                "job_id": job_id,
                "answer": {"type": "answer", "sdp": answer_sdp},
            }
        )
        log(f"job answer emitted: id={job_id} duration_ms={elapsed_ms(job_started_at)}")

        ready_wait_started_at = time.perf_counter()
        ready_task = asyncio.create_task(state.ready_event.wait())
        closed_task = asyncio.create_task(state.closed_event.wait())
        done, pending = await asyncio.wait({ready_task, closed_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if closed_task in done and not state.ready_event.is_set():
            raise RuntimeError("peer connection closed before job ready")
        if state.ready_error:
            raise RuntimeError(state.ready_error["detail"])
        log(f"job ready wait complete: id={job_id} duration_ms={elapsed_ms(ready_wait_started_at)}")

        channel = state.channel_holder.get("channel")
        if channel is None:
            raise RuntimeError("datachannel was not opened")
        emit({"type": "job.running", "job_id": job_id})
        await run_worker_job_session(app, context, channel, state, job_id)
        channel.send(json.dumps({"kind": "job.finished", "id": job_id}, ensure_ascii=False))
        emit(
            {
                "type": "job.result",
                "job_id": job_id,
            }
        )
    except asyncio.CancelledError:
        log(f"job cancelled: id={job_id}")
        channel = state.channel_holder.get("channel") if state is not None else None
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
        channel = state.channel_holder.get("channel") if state is not None else None
        if channel is not None:
            try:
                channel.send(json.dumps({"kind": "job.error", "id": job_id, "detail": str(exc)}, ensure_ascii=False))
            except Exception:
                pass
        emit({"type": "job.error", "job_id": job_id, "code": "job_error", "detail": str(exc)})
    finally:
        if pc is not None:
            await pc.close()


async def run_worker_job_session(
    app: SlaveApp,
    base_context: SlaveContext,
    channel: Any,
    state: WorkerJobPeerState,
    job_id: str,
) -> None:
    while True:
        call_task = asyncio.create_task(state.call_queue.get())
        finish_task = asyncio.create_task(state.finish_event.wait())
        closed_task = asyncio.create_task(state.closed_event.wait())
        try:
            done, pending = await asyncio.wait(
                {call_task, finish_task, closed_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if closed_task in done and state.closed_event.is_set():
                raise RuntimeError(f"peer connection closed before job finish: {job_id}")
            if finish_task in done and state.finish_event.is_set():
                log(f"job finish received: id={job_id}")
                return
            if call_task in done:
                await run_worker_job_call(app, base_context, channel, state, call_task.result())
        finally:
            for task in (call_task, finish_task, closed_task):
                if not task.done():
                    task.cancel()


async def run_worker_job_call(
    app: SlaveApp,
    base_context: SlaveContext,
    channel: Any,
    state: WorkerJobPeerState,
    call: dict[str, Any],
) -> None:
    call_id = str(call["id"])
    call_type = str(call["type"])
    state.call_in_progress = True

    async def emit_event(event_type: str, payload: Any = None) -> None:
        channel.send(
            json.dumps(
                {
                    "kind": "job.event",
                    "id": call_id,
                    "type": event_type,
                    "payload": payload,
                },
                ensure_ascii=False,
            )
        )

    try:
        try:
            response = await app.dispatch(
                DataChannelMessage(
                    id=call_id,
                    type=call_type,
                    payload=call.get("payload"),
                    attachments=[],
                ),
                SlaveContext(
                    session_id=base_context.session_id,
                    ttl_seconds=base_context.ttl_seconds,
                    call_id=call_id,
                    _event_sender=emit_event,
                ),
            )
        except Exception as exc:
            log(f"job call failed: id={call_id} type={call_type} error={exc}")
            send_job_error(channel, call_id, "job_error", str(exc))
            return

        if response is None:
            response = DataChannelMessage(id=call_id, type=f"{call_type}.result", payload=None)
        ack_event = asyncio.Event()
        state.result_ack_events[call_id] = ack_event
        try:
            await send_job_result(channel, call_id, response)
            log(f"job call result sent: id={call_id} type={call_type}")
            log(f"job result ack wait: id={call_id} timeout_s={JOB_RESULT_ACK_TIMEOUT_SECONDS:g}")
            await wait_for_job_result_ack(call_id, ack_event, state.closed_event)
            log(f"job result ack received: id={call_id}")
        finally:
            state.result_ack_events.pop(call_id, None)
    finally:
        state.call_in_progress = False


def send_job_error(channel: Any, call_id: str, code: str, detail: str) -> None:
    channel.send(
        json.dumps(
            {
                "kind": "job.error",
                "id": call_id,
                "code": code,
                "detail": detail,
            },
            ensure_ascii=False,
        )
    )


def parse_job_ready_message(raw_message: str, job_id: str) -> tuple[bool, Any, str | None]:
    if len(raw_message.encode("utf-8")) > JOB_DATA_CHANNEL_MESSAGE_MAX_BYTES:
        return True, None, f"job.ready frame exceeds {JOB_DATA_CHANNEL_MESSAGE_MAX_BYTES} bytes"
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
