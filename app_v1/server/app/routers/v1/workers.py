from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from sdk.protocol.messages import WorkerHello, parse_control_message
from app.auth import Principal, authenticate_authorization, require_client
from app.db import SessionLocal, get_db
from app.models import WorkerSessionView
from app.service.realtime_service import safe_close_client, safe_send_json
from app.service.session_service import SessionService
from app.service.worker_service import WorkerService
from app.state import runtime, utcnow

router = APIRouter(prefix="/workers", tags=["v1-workers"])


@router.get("", response_model=list[WorkerSessionView])
async def list_workers(
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> list[WorkerSessionView]:
    return await WorkerService.list_workers_for_user(db, principal.user_id)


@router.websocket("/control")
async def worker_control(websocket: WebSocket) -> None:
    worker_id: str | None = None
    try:
        principal = authenticate_authorization(websocket.headers.get("authorization", ""))
        principal.require_scope("worker")
    except HTTPException:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    async with SessionLocal() as db:
        try:
            hello_payload = await websocket.receive_json()
            hello = parse_control_message(hello_payload)
            if not isinstance(hello, WorkerHello):
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return

            worker = await WorkerService.create_connected_worker(
                db,
                user_id=principal.user_id,
                worker_name=hello.worker_name,
                slave_app_ids=hello.slave_app_ids,
                ip_address=websocket.client.host if websocket.client else None,
            )
            worker_id = str(worker.id)
            await runtime.register_worker(worker_id, websocket)
            await websocket.send_json(
                {
                    "type": "worker.accepted",
                    "worker_session_id": worker_id,
                    "server_time": utcnow().isoformat(),
                }
            )

            while True:
                payload = await websocket.receive_json()
                await handle_worker_message(db, worker_id, websocket, payload)
        except WebSocketDisconnect:
            pass
        except ValidationError as exc:
            await safe_send_json(websocket, {"type": "error", "detail": str(exc)})
        finally:
            if worker_id is not None:
                affected = await runtime.remove_worker(worker_id)
                await WorkerService.mark_disconnected(db, worker_id)
                for session in affected:
                    await SessionService.close_session(db, session.id, "worker disconnected", status="error")
                    await safe_close_client(session, "worker disconnected")


async def handle_worker_message(
    db: AsyncSession,
    worker_id: str,
    websocket: WebSocket,
    payload: dict[str, Any],
) -> None:
    message = parse_control_message(payload)
    if message.type == "worker.heartbeat":
        await runtime.mark_heartbeat(worker_id, message.active_session_ids)
        await WorkerService.mark_heartbeat(db, worker_id, message.status, message.active_session_ids)
        return
    if message.type == "session.ready":
        await runtime.mark_session_ready(message.session_id)
        await SessionService.mark_session_ready(db, message.session_id)
        return
    if message.type == "signal.to_client":
        await relay_to_client(message.session_id, {"signal": message.signal.model_dump(exclude_none=True)})
        return
    if message.type == "session.closed":
        await SessionService.close_session(db, message.session_id, message.reason)
        session = await runtime.close_session(message.session_id)
        if session is not None:
            await safe_close_client(session, message.reason)
        return
    if message.type == "session.error":
        await SessionService.mark_session_error(db, message.session_id, message.detail, message.code)
        session = await runtime.mark_session_error(message.session_id, message.detail)
        if session is not None:
            await relay_to_client(
                message.session_id,
                {"type": "session.error", "code": message.code, "detail": message.detail},
            )
        return
    if message.type == "ping":
        await websocket.send_json({"type": "pong", "server_time": utcnow().isoformat()})


async def relay_to_client(session_id: str, message: dict[str, Any]) -> None:
    websocket = await runtime.store_or_get_client_socket(session_id, message)
    if websocket is not None:
        await safe_send_json(websocket, message)
