from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import timezone
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from sdk.protocol.messages import ClientSignalMessage, WorkerHello, parse_control_message
from app.auth import Principal, authenticate_authorization, authenticate_token, require_client
from app.models import SessionCreateRequest, SessionCreateResult, WorkerSessionView
from app.settings import get_settings
from app.state import ClientSession, RuntimeState, WorkerConnection, utcnow

runtime = RuntimeState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(cleanup_expired_sessions())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="GP Station v1 Server", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/workers", response_model=list[WorkerSessionView])
async def list_workers(principal: Principal = Depends(require_client)) -> list[WorkerSessionView]:
    workers = await runtime.list_workers_for_user(principal.user_id)
    return [worker_to_view(worker) for worker in workers]


@app.post("/v1/sessions", response_model=SessionCreateResult)
async def create_session(
    body: SessionCreateRequest,
    principal: Principal = Depends(require_client),
) -> SessionCreateResult:
    ttl_seconds = body.ttl_seconds or get_settings().session_ttl_seconds
    try:
        session = await runtime.create_session(
            user_id=principal.user_id,
            worker_session_id=body.worker_session_id,
            slave_app_id=body.slave_app_id,
            ttl_seconds=ttl_seconds,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not available") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slave app not available") from exc

    await send_to_worker(
        session.worker_session_id,
        {
            "type": "session.start",
            "session_id": session.id,
            "token": session.token,
            "slave_app_id": session.slave_app_id,
            "ttl_seconds": session.ttl_seconds,
        },
    )

    try:
        await asyncio.wait_for(
            session.ready_event.wait(),
            timeout=get_settings().session_ready_timeout_seconds,
        )
    except TimeoutError as exc:
        await close_session_and_worker(session.id, "ready timeout")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Worker session start timed out") from exc

    if session.status != "ready":
        detail = session.last_error or "Worker session failed"
        await close_session_and_worker(session.id, detail)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

    return SessionCreateResult(
        session_id=session.id,
        worker_session_id=session.worker_session_id,
        slave_app_id=session.slave_app_id,
        signaling_url=build_signaling_url(session),
        token=session.token,
        expires_at=session.expires_at,
    )


@app.websocket("/v1/workers/control")
async def worker_control(websocket: WebSocket) -> None:
    worker: WorkerConnection | None = None
    try:
        principal = authenticate_authorization(websocket.headers.get("authorization", ""))
        principal.require_scope("worker")
    except HTTPException:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        hello_payload = await websocket.receive_json()
        hello = parse_control_message(hello_payload)
        if not isinstance(hello, WorkerHello):
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return

        worker = await runtime.register_worker(
            user_id=principal.user_id,
            worker_name=hello.worker_name,
            slave_app_ids=hello.slave_app_ids,
            websocket=websocket,
        )
        await websocket.send_json(
            {
                "type": "worker.accepted",
                "worker_session_id": worker.id,
                "server_time": utcnow().isoformat(),
            }
        )

        while True:
            payload = await websocket.receive_json()
            await handle_worker_message(worker, payload)
    except WebSocketDisconnect:
        pass
    except ValidationError as exc:
        await safe_send_json(websocket, {"type": "error", "detail": str(exc)})
    finally:
        if worker is not None:
            affected = await runtime.remove_worker(worker.id)
            for session in affected:
                await safe_close_client(session, "worker disconnected")


@app.websocket("/v1/sessions/{session_id}/signal")
async def client_signal(websocket: WebSocket, session_id: str) -> None:
    token = websocket.query_params.get("token", "")
    await websocket.accept()
    try:
        session = await runtime.attach_client(session_id, websocket, token)
    except KeyError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    for pending in await runtime.take_pending_client_signals(session_id):
        await websocket.send_json(pending)

    try:
        while True:
            payload = await websocket.receive_json()
            message = ClientSignalMessage.model_validate(payload)
            await send_to_worker(
                session.worker_session_id,
                {
                    "type": "signal.to_worker",
                    "session_id": session.id,
                    "signal": message.signal.model_dump(exclude_none=True),
                },
            )
    except WebSocketDisconnect:
        pass
    except ValidationError as exc:
        await safe_send_json(websocket, {"type": "session.error", "detail": str(exc)})
    finally:
        await runtime.detach_client(session_id, websocket)
        await close_session_and_worker(session_id, "client disconnected")


async def handle_worker_message(worker: WorkerConnection, payload: dict[str, Any]) -> None:
    message = parse_control_message(payload)
    if message.type == "worker.heartbeat":
        await runtime.mark_heartbeat(worker.id, message.status, message.active_session_ids)
        return
    if message.type == "session.ready":
        await runtime.mark_session_ready(message.session_id)
        return
    if message.type == "signal.to_client":
        await relay_to_client(message.session_id, {"signal": message.signal.model_dump(exclude_none=True)})
        return
    if message.type == "session.closed":
        session = await runtime.close_session(message.session_id, message.reason)
        if session is not None:
            await safe_close_client(session, message.reason)
        return
    if message.type == "session.error":
        session = await runtime.mark_session_error(message.session_id, message.detail)
        if session is not None:
            await relay_to_client(
                message.session_id,
                {"type": "session.error", "code": message.code, "detail": message.detail},
            )
        return
    if message.type == "ping":
        await worker.websocket.send_json({"type": "pong", "server_time": utcnow().isoformat()})


async def relay_to_client(session_id: str, message: dict[str, Any]) -> None:
    websocket = await runtime.store_or_get_client_socket(session_id, message)
    if websocket is not None:
        await safe_send_json(websocket, message)


async def send_to_worker(worker_id: str, message: dict[str, Any]) -> None:
    worker = await runtime.get_worker(worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not available")
    await worker.websocket.send_json(message)


async def close_session_and_worker(session_id: str, reason: str) -> None:
    session = await runtime.close_session(session_id, reason)
    if session is None:
        return
    worker = await runtime.get_worker(session.worker_session_id)
    if worker is not None:
        await safe_send_json(worker.websocket, {"type": "session.stop", "session_id": session_id, "reason": reason})
    await safe_close_client(session, reason)


async def safe_send_json(websocket: WebSocket, message: dict[str, Any]) -> None:
    try:
        await websocket.send_json(message)
    except RuntimeError:
        return


async def safe_close_client(session: ClientSession, reason: str) -> None:
    if session.client_websocket is None:
        return
    await safe_send_json(session.client_websocket, {"type": "session.closed", "reason": reason})
    try:
        await session.client_websocket.close()
    except RuntimeError:
        return


async def cleanup_expired_sessions() -> None:
    while True:
        await asyncio.sleep(get_settings().cleanup_interval_seconds)
        for session in await runtime.collect_expired_sessions():
            worker = await runtime.get_worker(session.worker_session_id)
            if worker is not None:
                await safe_send_json(
                    worker.websocket,
                    {"type": "session.stop", "session_id": session.id, "reason": "expired"},
                )
            await safe_close_client(session, "expired")


def build_signaling_url(session: ClientSession) -> str:
    parsed = urlparse(get_settings().public_base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/v1/sessions/{session.id}/signal" if base_path else f"/v1/sessions/{session.id}/signal"
    return urlunparse((scheme, parsed.netloc, path, "", urlencode({"token": session.token}), ""))


def worker_to_view(worker: WorkerConnection) -> WorkerSessionView:
    return WorkerSessionView(
        id=worker.id,
        user_id=worker.user_id,
        worker_name=worker.worker_name,
        status=worker.status,
        slave_app_ids=worker.slave_app_ids,
        active_session_count=len(worker.active_session_ids),
        connected_at=worker.connected_at.astimezone(timezone.utc),
        last_heartbeat_at=worker.last_heartbeat_at.astimezone(timezone.utc),
    )
