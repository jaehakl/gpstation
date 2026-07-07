from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from sdk.protocol.messages import LauncherHello, parse_control_message
from app.auth import Principal, authenticate_db_authorization, require_client
from app.db import SessionLocal, get_db
from app.models import LauncherSessionView
from app.service.realtime_service import safe_close_client, safe_send_json
from app.service.session_service import SessionService
from app.service.launcher_service import LauncherService
from app.state import runtime, utcnow

router = APIRouter(prefix="/launchers", tags=["v1-launchers"])


@router.get("", response_model=list[LauncherSessionView])
async def list_launchers(
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> list[LauncherSessionView]:
    return await LauncherService.list_launchers_for_user(db, principal.user_id)


@router.websocket("/control")
async def launcher_control(websocket: WebSocket) -> None:
    launcher_id: str | None = None
    async with SessionLocal() as db:
        try:
            principal = await authenticate_db_authorization(db, websocket.headers.get("authorization", ""))
            principal.require_scope("launcher")
        except HTTPException:
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        try:
            hello_payload = await websocket.receive_json()
            hello = parse_control_message(hello_payload)
            if not isinstance(hello, LauncherHello):
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return

            launcher = await LauncherService.create_connected_launcher(
                db,
                user_id=principal.user_id,
                launcher_name=hello.launcher_name,
                slave_app_ids=hello.slave_app_ids,
                ip_address=websocket.client.host if websocket.client else None,
            )
            launcher_id = str(launcher.id)
            await runtime.register_launcher(launcher_id, websocket)
            await websocket.send_json(
                {
                    "type": "launcher.accepted",
                    "launcher_session_id": launcher_id,
                    "server_time": utcnow().isoformat(),
                }
            )

            while True:
                payload = await websocket.receive_json()
                await handle_launcher_message(db, launcher_id, websocket, payload)
        except WebSocketDisconnect:
            pass
        except ValidationError as exc:
            await safe_send_json(websocket, {"type": "error", "detail": str(exc)})
        finally:
            if launcher_id is not None:
                affected = await runtime.remove_launcher(launcher_id)
                await LauncherService.mark_disconnected(db, launcher_id)
                for session in affected:
                    await SessionService.close_session(db, session.id, "launcher disconnected", status="error")
                    await safe_close_client(session, "launcher disconnected")


async def handle_launcher_message(
    db: AsyncSession,
    launcher_id: str,
    websocket: WebSocket,
    payload: dict[str, Any],
) -> None:
    message = parse_control_message(payload)
    if message.type == "launcher.heartbeat":
        await runtime.mark_heartbeat(launcher_id, message.active_session_ids)
        await LauncherService.mark_heartbeat(db, launcher_id, message.status, message.active_session_ids)
        return
    if message.type == "session.ready":
        await SessionService.mark_session_ready(db, message.session_id)
        await runtime.mark_session_ready(message.session_id)
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
    if message.type == "session.log":
        await runtime.append_session_log(message.session_id, message.stream, message.line, message.time)
        return
    if message.type == "ping":
        await websocket.send_json({"type": "pong", "server_time": utcnow().isoformat()})


async def relay_to_client(session_id: str, message: dict[str, Any]) -> None:
    websocket = await runtime.store_or_get_client_socket(session_id, message)
    if websocket is not None:
        await safe_send_json(websocket, message)
