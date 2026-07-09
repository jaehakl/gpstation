from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets

from app.settings import LauncherSettings
from app.slave_registry import SlaveAppRegistry, load_default_registry
from app.subprocess_manager import WorkerManager

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
        manager: WorkerManager | None = None
        heartbeat_task: asyncio.Task[None] | None = None
        try:
            await send_json(
                websocket,
                send_lock,
                launcher_hello_payload(settings, registry),
            )
            accepted = json.loads(await websocket.recv())
            if accepted.get("type") != "launcher.accepted":
                raise RuntimeError(f"Expected launcher.accepted, received {accepted.get('type')}")
            print(f"Launcher connection: {accepted.get('launcher_id')}", flush=True)
            manager = WorkerManager(
                settings,
                lambda message: send_json(websocket, send_lock, message),
                registry,
            )
            heartbeat_task = asyncio.create_task(send_heartbeats(websocket, send_lock, manager, settings))

            async for raw_message in websocket:
                await handle_server_message(manager, json.loads(raw_message))
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
            if manager is not None:
                await manager.stop_all("launcher shutdown")
            if heartbeat_task is not None:
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
    manager: WorkerManager,
    settings: LauncherSettings,
) -> None:
    while True:
        await asyncio.sleep(settings.heartbeat_interval_seconds)
        await send_json(
            websocket,
            send_lock,
            {
                "type": "launcher.heartbeat",
                "status": "busy" if manager.current_job_id else "ready",
                "current_job_id": manager.current_job_id,
                "loaded_slave_app_id": manager.current_worker_slave_app_id(),
                "worker_status": manager.worker_status,
                "metadata": {},
            },
        )


async def handle_server_message(manager: WorkerManager, message: dict[str, Any]) -> None:
    message_type = message.get("type")
    if message_type == "job.start":
        await manager.start_job(
            job_id=str(message["job_id"]),
            handler_type=str(message["handler_type"]),
            slave_app_id=str(message["slave_app_id"]),
            offer=message["offer"],
        )
        return
    if message_type == "job.cancel":
        await manager.cancel_job(str(message["job_id"]), str(message.get("reason") or "cancelled"))
        return
    if message_type == "worker.reset":
        await manager.reset_worker(str(message.get("reason") or "reset requested"))
        return
    if message_type == "error":
        print(f"Server control error: {message.get('detail') or message}", flush=True)
        return
    print(f"Unsupported server message: {message_type}", flush=True)


def launcher_hello_payload(settings: LauncherSettings, registry: SlaveAppRegistry) -> dict[str, Any]:
    return {
        "type": "launcher.hello",
        "launcher_name": settings.launcher_name,
        "slave_app_ids": registry.ids(),
        "metadata": registry.metadata(),
    }
