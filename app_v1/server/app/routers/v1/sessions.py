from __future__ import annotations

import asyncio
from urllib.parse import urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from sdk.protocol.messages import ClientSignalMessage
from app.auth import Principal, require_client
from app.db import SessionLocal, get_db
from app.models import SessionCreateRequest, SessionCreateResult
from app.service.realtime_service import safe_close_client, safe_send_json, send_to_worker, stop_worker_session
from app.service.session_service import SessionService
from app.settings import settings
from app.state import runtime

router = APIRouter(prefix="/sessions", tags=["v1-sessions"])


@router.post("", response_model=SessionCreateResult)
async def create_session(
    body: SessionCreateRequest,
    request: Request,
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> SessionCreateResult:
    ttl_seconds = body.ttl_seconds or settings.session_ttl_seconds
    client = request.client
    try:
        session, token = await SessionService.create_session(
            db,
            user_id=principal.user_id,
            worker_id=body.worker_session_id,
            slave_app_id=body.slave_app_id,
            ttl_seconds=ttl_seconds,
            master_ip_address=client.host if client else None,
            master_user_agent=request.headers.get("user-agent"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not available") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slave app not available") from exc

    runtime_session = await runtime.register_session(str(session.id), str(session.worker_id))
    try:
        await send_to_worker(
            str(session.worker_id),
            {
                "type": "session.start",
                "session_id": str(session.id),
                "token": token,
                "slave_app_id": session.slave_app_id,
                "ttl_seconds": session.ttl_seconds,
            },
        )
    except HTTPException:
        await close_session_and_worker(db, str(session.id), "worker unavailable", status="error")
        raise

    try:
        await asyncio.wait_for(
            runtime_session.ready_event.wait(),
            timeout=settings.session_ready_timeout_seconds,
        )
    except TimeoutError as exc:
        await close_session_and_worker(db, str(session.id), "ready timeout", status="error")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Worker session start timed out") from exc

    await db.refresh(session)
    if session.status != "ready":
        detail = session.last_error or runtime_session.last_error or "Worker session failed"
        await close_session_and_worker(db, str(session.id), detail, status="error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

    return SessionCreateResult(
        session_id=str(session.id),
        worker_session_id=str(session.worker_id),
        slave_app_id=session.slave_app_id,
        signaling_url=build_signaling_url(str(session.id), token),
        token=token,
        expires_at=session.expires_at,
    )


@router.websocket("/{session_id}/signal")
async def client_signal(websocket: WebSocket, session_id: str) -> None:
    token = websocket.query_params.get("token", "")
    await websocket.accept()
    async with SessionLocal() as db:
        session = await SessionService.verify_session_token(db, session_id, token)
        if session is None or session.worker_id is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        try:
            await runtime.attach_client(session_id, websocket)
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
                    str(session.worker_id),
                    {
                        "type": "signal.to_worker",
                        "session_id": session_id,
                        "signal": message.signal.model_dump(exclude_none=True),
                    },
                )
        except WebSocketDisconnect:
            pass
        except ValidationError as exc:
            await safe_send_json(websocket, {"type": "session.error", "detail": str(exc)})
        finally:
            await runtime.detach_client(session_id, websocket)
            await close_session_and_worker(db, session_id, "client disconnected")


async def close_session_and_worker(
    db: AsyncSession,
    session_id: str,
    reason: str,
    *,
    status: str = "closed",
) -> None:
    db_session = await SessionService.close_session(db, session_id, reason, status=status)
    runtime_session = await runtime.close_session(session_id)
    worker_id = runtime_session.worker_id if runtime_session else str(db_session.worker_id) if db_session and db_session.worker_id else None
    if worker_id is not None:
        await stop_worker_session(worker_id, session_id, reason)
    if runtime_session is not None:
        await safe_close_client(runtime_session, reason)


def build_signaling_url(session_id: str, token: str) -> str:
    parsed = urlparse(settings.public_base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/v1/sessions/{session_id}/signal" if base_path else f"/v1/sessions/{session_id}/signal"
    return urlunparse((scheme, parsed.netloc, path, "", urlencode({"token": token}), ""))
