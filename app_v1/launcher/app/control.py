from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets

from app.settings import LauncherSettings
from app.slave_registry import load_default_registry
from app.subprocess_manager import SessionManager

BACKOFF_SECONDS = [1, 2, 5, 10, 30]


async def run_slave_launcher(settings: LauncherSettings) -> None:
    attempt = 0
    while True:
        delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
        try:
            await run_connection(settings)
            attempt = 0
        except asyncio.CancelledError:
            raise
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            attempt += 1
            print(f"Control connection failed: {exc}")
            print(f"Reconnecting in {delay}s...")
            await asyncio.sleep(delay)


async def run_connection(settings: LauncherSettings) -> None:
    headers = {"Authorization": f"Bearer {settings.access_token}"}
    async with await open_websocket(settings.control_websocket_url, headers) as websocket:
        send_lock = asyncio.Lock()
        registry = load_default_registry()
        manager = SessionManager(settings, lambda message: send_json(websocket, send_lock, message), registry)
        heartbeat_task = asyncio.create_task(send_heartbeats(websocket, send_lock, manager, settings))
        try:
            await send_json(
                websocket,
                send_lock,
                {
                    "type": "launcher.hello",
                    "launcher_name": settings.launcher_name,
                    "slave_app_ids": registry.ids(),
                    "metadata": {},
                },
            )
            accepted = json.loads(await websocket.recv())
            if accepted.get("type") != "launcher.accepted":
                raise RuntimeError(f"Expected launcher.accepted, received {accepted.get('type')}")
            print(f"Launcher session: {accepted.get('launcher_session_id')}", flush=True)

            async for raw_message in websocket:
                await handle_server_message(manager, json.loads(raw_message))
        finally:
            heartbeat_task.cancel()
            await manager.stop_all("launcher shutdown")
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass


async def open_websocket(url: str, headers: dict[str, str]) -> Any:
    try:
        return websockets.connect(url, additional_headers=headers)
    except TypeError:
        return websockets.connect(url, extra_headers=headers)


async def send_json(websocket: Any, send_lock: asyncio.Lock, message: dict[str, Any]) -> None:
    async with send_lock:
        await websocket.send(json.dumps(message, ensure_ascii=False))


async def send_heartbeats(
    websocket: Any,
    send_lock: asyncio.Lock,
    manager: SessionManager,
    settings: LauncherSettings,
) -> None:
    while True:
        await asyncio.sleep(settings.heartbeat_interval_seconds)
        await send_json(
            websocket,
            send_lock,
            {
                "type": "launcher.heartbeat",
                "status": "busy" if manager.active_session_ids() else "ready",
                "active_session_ids": manager.active_session_ids(),
            },
        )


async def handle_server_message(manager: SessionManager, message: dict[str, Any]) -> None:
    message_type = message.get("type")
    if message_type == "session.start":
        await manager.start_session(
            str(message["session_id"]),
            str(message.get("slave_app_id") or "echo"),
            int(message["ttl_seconds"]),
        )
        return
    if message_type == "signal.to_launcher":
        await manager.forward_signal(str(message["session_id"]), message["signal"])
        return
    if message_type == "session.stop":
        await manager.stop_session(str(message["session_id"]), str(message.get("reason") or "closed"))
        return
    if message_type == "pong":
        return
    print(f"Unsupported server message: {message_type}", flush=True)
