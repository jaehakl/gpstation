from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from sdk.protocol.messages import LauncherHello, parse_launcher_message
from app.auth import Principal, authenticate_db_authorization, require_client
from app.db import SessionLocal, get_db
from app.models import LauncherView
from app.service.access_key_service import AccessKeyService
from app.service.auth_audit_service import add_auth_audit
from app.service.job_orchestrator import LauncherPolicyViolation, job_orchestrator
from app.service.launcher_service import LauncherService
from app.service.realtime_service import safe_send_json
from app.state import runtime, utcnow

router = APIRouter(prefix="/launchers", tags=["v1-launchers"])
LAUNCHER_HELLO_TIMEOUT_SECONDS = 10


@router.get("", response_model=list[LauncherView])
async def list_launchers(
    principal: Principal = Depends(require_client),
    db: AsyncSession = Depends(get_db),
) -> list[LauncherView]:
    return await LauncherService.list_launchers_for_user(db, principal.user_id)


@router.websocket("/control")
async def launcher_control(websocket: WebSocket) -> None:
    launcher_id: str | None = None
    principal: Principal | None = None
    async with SessionLocal() as db:
        try:
            principal = await authenticate_db_authorization(
                db,
                websocket.headers.get("authorization", ""),
                client_ip=websocket.client.host if websocket.client else None,
                origin=websocket.headers.get("origin"),
            )
            principal.require_scope("launcher")
        except HTTPException as exc:
            add_auth_audit(
                db,
                "launcher_rejected",
                user_id=principal.user_id if principal else None,
                details={
                    "reason": "missing_launcher_scope" if principal else "authentication_failed",
                    "status_code": exc.status_code,
                    "access_key_id": principal.access_key_id if principal else None,
                },
                client_ip=websocket.client.host if websocket.client else None,
                user_agent=websocket.headers.get("user-agent"),
            )
            await db.commit()
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Authentication SELECTs open a transaction. Do not keep its pooled
        # connection while an unauthenticated peer stalls before hello.
        await db.rollback()
        await websocket.accept()
        try:
            hello_payload = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=LAUNCHER_HELLO_TIMEOUT_SECONDS,
            )
            hello = parse_launcher_message(hello_payload)
            if not isinstance(hello, LauncherHello):
                add_auth_audit(
                    db,
                    "launcher_rejected",
                    user_id=principal.user_id,
                    details={"reason": "invalid_hello", "access_key_id": principal.access_key_id},
                    client_ip=websocket.client.host if websocket.client else None,
                    user_agent=websocket.headers.get("user-agent"),
                )
                await db.commit()
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
            await runtime.register_launcher(
                launcher_id,
                websocket,
                extract_slave_startup_timeouts(hello.metadata),
                access_key_id=principal.access_key_id,
            )
            add_auth_audit(
                db,
                "launcher_connected",
                user_id=principal.user_id,
                details={"launcher_id": launcher_id, "access_key_id": principal.access_key_id},
            )
            await db.commit()
            await websocket.send_json(
                {
                    "type": "launcher.accepted",
                    "launcher_id": launcher_id,
                    "server_time": utcnow().isoformat(),
                }
            )
            job_orchestrator.wake_dispatcher()

            while True:
                payload = await websocket.receive_json()
                await handle_launcher_message(
                    db,
                    launcher_id,
                    principal.user_id,
                    payload,
                )
        except WebSocketDisconnect:
            pass
        except TimeoutError:
            add_auth_audit(
                db,
                "launcher_rejected",
                user_id=principal.user_id,
                details={"reason": "hello_timeout", "access_key_id": principal.access_key_id},
                client_ip=websocket.client.host if websocket.client else None,
                user_agent=websocket.headers.get("user-agent"),
            )
            await db.commit()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except ValidationError as exc:
            add_auth_audit(
                db,
                "launcher_rejected",
                user_id=principal.user_id,
                details={
                    "reason": "invalid_message",
                    "launcher_id": launcher_id,
                    "detail": str(exc)[:512],
                },
                client_ip=websocket.client.host if websocket.client else None,
                user_agent=websocket.headers.get("user-agent"),
            )
            await db.commit()
            await safe_send_json(websocket, {"type": "error", "detail": str(exc)})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except LauncherPolicyViolation as exc:
            add_auth_audit(
                db,
                "launcher_rejected",
                user_id=principal.user_id,
                details={
                    "reason": "policy_violation",
                    "launcher_id": launcher_id,
                    "detail": str(exc)[:512],
                },
                client_ip=websocket.client.host if websocket.client else None,
                user_agent=websocket.headers.get("user-agent"),
            )
            await db.commit()
            await safe_send_json(websocket, {"type": "error", "detail": str(exc)})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        finally:
            if launcher_id is not None:
                await db.rollback()
                await job_orchestrator.launcher_disconnected(db, launcher_id=launcher_id)


async def handle_launcher_message(
    db: AsyncSession,
    launcher_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> None:
    message = parse_launcher_message(payload)
    if message.type == "launcher.heartbeat":
        persist_heartbeat, revalidate_key = await runtime.heartbeat_actions(
            launcher_id,
            message.status,
        )
        if revalidate_key:
            launcher = await runtime.get_launcher(launcher_id)
            access_key_id = launcher.access_key_id if launcher is not None else None
            key_is_active = access_key_id is not None and await AccessKeyService.is_active_launcher_key(
                db,
                access_key_id,
                user_id,
            )
            if not key_is_active:
                add_auth_audit(
                    db,
                    "launcher_rejected",
                    user_id=user_id,
                    details={"launcher_id": launcher_id, "reason": "access_key_inactive"},
                )
                await db.commit()
                raise LauncherPolicyViolation("launcher access key is no longer active")
            await db.rollback()
        await runtime.mark_heartbeat(
            launcher_id,
            current_job_id=message.current_job_id,
            loaded_slave_app_id=message.loaded_slave_app_id,
            worker_status=message.worker_status,
            metadata=message.metadata,
        )
        if persist_heartbeat:
            await LauncherService.mark_heartbeat(db, launcher_id, message.status)
        return
    await job_orchestrator.handle_launcher_job_event(
        db,
        launcher_id=launcher_id,
        user_id=user_id,
        message=message,
    )


def extract_slave_startup_timeouts(metadata: dict[str, Any]) -> dict[str, float]:
    slave_apps = metadata.get("slave_apps")
    if not isinstance(slave_apps, dict):
        return {}
    timeouts: dict[str, float] = {}
    for slave_app_id, raw_config in slave_apps.items():
        if not isinstance(raw_config, dict):
            continue
        raw_timeout = raw_config.get("startup_timeout_seconds")
        if raw_timeout is None:
            continue
        if isinstance(raw_timeout, bool):
            continue
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError):
            continue
        if timeout > 0:
            timeouts[str(slave_app_id)] = timeout
    return timeouts
