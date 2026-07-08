from __future__ import annotations

from typing import Any

from fastapi import HTTPException, WebSocket, status

from app.state import runtime


async def safe_send_json(websocket: WebSocket, message: dict[str, Any]) -> None:
    try:
        await websocket.send_json(message)
    except RuntimeError:
        return


async def send_to_launcher(launcher_id: str, message: dict[str, Any]) -> None:
    launcher = await runtime.get_launcher(launcher_id)
    if launcher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Launcher not available")
    await launcher.websocket.send_json(message)
