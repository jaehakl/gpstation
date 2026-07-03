from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets

from gpstation_worker.config import WorkerSettings
from gpstation_worker.gpu import get_gpu_status
from gpstation_worker.protocol import make_gpu_status, make_hello

BACKOFF_SECONDS = [1, 2, 5, 10, 30, 60]


async def run_worker(settings: WorkerSettings) -> None:
    if not settings.access_key:
        raise RuntimeError("GPSTATION_ACCESS_KEY is required")

    attempt = 0
    while True:
        delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
        try:
            await run_worker_connection(settings)
            attempt = 0
        except asyncio.CancelledError:
            raise
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            attempt += 1
            print(f"WebSocket connection failed: {exc}")
            print(f"Reconnecting in {delay}s...")
            await asyncio.sleep(delay)


async def run_worker_connection(settings: WorkerSettings) -> None:
    print(f"Connecting to {settings.websocket_url}")
    async with websockets.connect(
        settings.websocket_url,
        extra_headers={"Authorization": f"Bearer {settings.access_key}"},
    ) as websocket:
        await websocket.send(json.dumps(make_hello(settings)))
        server_hello = await receive_json(websocket)
        if server_hello.get("type") != "server_hello":
            raise RuntimeError(f"Expected server_hello, received {server_hello.get('type')}")

        print_server_hello(server_hello)

        while True:
            gpu = get_gpu_status()
            await websocket.send(json.dumps(make_gpu_status(gpu)))
            print_gpu_status(gpu.to_dict())
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=settings.gpu_interval_sec)
                handle_server_message(json.loads(message))
            except TimeoutError:
                continue


async def receive_json(websocket: Any) -> dict[str, Any]:
    message = await websocket.recv()
    payload = json.loads(message)
    if not isinstance(payload, dict):
        raise RuntimeError("Server message must be a JSON object")
    return payload


def handle_server_message(message: dict[str, Any]) -> None:
    message_type = message.get("type")
    if message_type == "pong":
        return
    if message_type == "error":
        print(f"Server error: {message.get('detail')}")
        return
    print(f"Server message: {message_type}")


def print_server_hello(message: dict[str, Any]) -> None:
    user = message.get("user") if isinstance(message.get("user"), dict) else {}
    display_name = user.get("display_name") or user.get("email") or user.get("id") or "unknown"
    print("Connected.")
    print(f"Session: {message.get('session_id')}")
    print(f"User: {display_name} ({user.get('role') or '-'})")
    print(f"User ID: {user.get('id') or '-'}")


def print_gpu_status(gpu: dict[str, Any]) -> None:
    name = gpu.get("name") or "No GPU detected"
    total = gpu.get("vram_total_mb")
    available = gpu.get("vram_available_mb")
    temperature = gpu.get("temperature_c")
    utilization = gpu.get("utilization_pct")
    print(
        "GPU:",
        name,
        f"vram={available}/{total}MB",
        f"temp={temperature}C",
        f"util={utilization}%",
    )
