from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from db import SessionLocal
from service.worker_session_service import WorkerSessionService
from user_auth.utils.access_key_auth import authenticate_access_key_secret, get_access_key_secret_from_authorization

router = APIRouter(prefix="/workers", tags=["app-v1-workers"])


@router.websocket("/ws")
async def worker_websocket(websocket: WebSocket):
    session_id: str | None = None
    async with SessionLocal() as db:
        try:
            auth = websocket.headers.get("authorization", "")
            current_user = await authenticate_access_key_secret(
                db,
                get_access_key_secret_from_authorization(auth),
            )
            if not any(role in {"admin", "user"} for role in current_user.roles):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        except HTTPException:
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        try:
            hello = await websocket.receive_json()
            if not isinstance(hello, dict) or hello.get("type") != "hello":
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return

            client = websocket.client
            session = await WorkerSessionService.create_connected_session(
                db=db,
                user_id=current_user.id,
                hello=hello,
                ip_address=client.host if client else None,
                user_agent=websocket.headers.get("user-agent"),
            )
            session_id = str(session.id)
            await websocket.send_json(
                {
                    "type": "server_hello",
                    "session_id": session_id,
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "user": {
                        "id": current_user.id,
                        "email": current_user.email,
                        "display_name": current_user.display_name,
                        "role": current_user.role,
                    },
                }
            )

            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    await websocket.send_json({"type": "error", "detail": "message must be an object"})
                    continue

                message_type = message.get("type")
                if message_type in {"gpu_status", "heartbeat"}:
                    await WorkerSessionService.update_gpu_status(db, session_id, message)
                elif message_type == "ping":
                    await websocket.send_json({"type": "pong", "server_time": datetime.now(timezone.utc).isoformat()})
                else:
                    await websocket.send_json({"type": "error", "detail": f"unsupported message type: {message_type}"})
        except WebSocketDisconnect:
            pass
        finally:
            if session_id is not None:
                await WorkerSessionService.mark_disconnected(db, session_id)
