from __future__ import annotations

from typing import Any

from fastapi import HTTPException, WebSocket, status

from app.state import SessionRuntime, runtime


async def safe_send_json(websocket: WebSocket, message: dict[str, Any]) -> None:
    try:
        await websocket.send_json(message)
    except RuntimeError:
        return


async def safe_close_client(session: SessionRuntime, reason: str) -> None:
    if session.client_websocket is None:
        return
    await safe_send_json(session.client_websocket, {"type": "session.closed", "reason": reason})
    try:
        await session.client_websocket.close()
    except RuntimeError:
        return


async def send_to_worker(worker_id: str, message: dict[str, Any]) -> None:
    worker = await runtime.get_worker(worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not available")
    await worker.websocket.send_json(message)


async def stop_worker_session(worker_id: str, session_id: str, reason: str) -> None:
    worker = await runtime.get_worker(worker_id)
    if worker is not None:
        await safe_send_json(worker.websocket, {"type": "session.stop", "session_id": session_id, "reason": reason})
