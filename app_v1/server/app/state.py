from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LauncherRuntime:
    id: str
    websocket: WebSocket
    slave_app_startup_timeouts: dict[str, float] = field(default_factory=dict)
    current_job_id: str | None = None
    loaded_slave_app_id: str | None = None
    worker_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class RuntimeRegistry:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.launchers: dict[str, LauncherRuntime] = {}
        self.job_events: dict[str, asyncio.Event] = {}

    async def register_launcher(
        self,
        launcher_id: str,
        websocket: WebSocket,
        slave_app_startup_timeouts: dict[str, float] | None = None,
    ) -> LauncherRuntime:
        launcher = LauncherRuntime(
            id=launcher_id,
            websocket=websocket,
            slave_app_startup_timeouts=slave_app_startup_timeouts or {},
        )
        async with self.lock:
            self.launchers[launcher_id] = launcher
        return launcher

    async def remove_launcher(self, launcher_id: str) -> None:
        async with self.lock:
            self.launchers.pop(launcher_id, None)

    async def get_launcher(self, launcher_id: str) -> LauncherRuntime | None:
        async with self.lock:
            return self.launchers.get(launcher_id)

    async def get_launcher_ids(self) -> set[str]:
        async with self.lock:
            return set(self.launchers.keys())

    async def mark_heartbeat(
        self,
        launcher_id: str,
        *,
        current_job_id: str | None = None,
        loaded_slave_app_id: str | None = None,
        worker_status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        async with self.lock:
            launcher = self.launchers.get(launcher_id)
            if launcher is not None:
                launcher.current_job_id = current_job_id
                launcher.loaded_slave_app_id = loaded_slave_app_id
                launcher.worker_status = worker_status
                launcher.metadata = metadata or {}

    async def mark_launcher_job(
        self,
        launcher_id: str,
        job_id: str | None,
        *,
        loaded_slave_app_id: str | None = None,
        worker_status: str | None = None,
    ) -> None:
        async with self.lock:
            launcher = self.launchers.get(launcher_id)
            if launcher is not None:
                launcher.current_job_id = job_id
                if loaded_slave_app_id is not None:
                    launcher.loaded_slave_app_id = loaded_slave_app_id
                if worker_status is not None:
                    launcher.worker_status = worker_status

    async def clear_launcher_worker(self, launcher_id: str) -> None:
        async with self.lock:
            launcher = self.launchers.get(launcher_id)
            if launcher is not None:
                launcher.current_job_id = None
                launcher.loaded_slave_app_id = None
                launcher.worker_status = "idle"
                launcher.metadata = {}

    async def launcher_snapshots(self) -> dict[str, dict[str, Any]]:
        async with self.lock:
            return {
                launcher_id: {
                    "current_job_id": launcher.current_job_id,
                    "loaded_slave_app_id": launcher.loaded_slave_app_id,
                    "worker_status": launcher.worker_status,
                    "metadata": dict(launcher.metadata),
                }
                for launcher_id, launcher in self.launchers.items()
            }

    async def idle_launcher_ids(self) -> set[str]:
        async with self.lock:
            return {
                launcher_id
                for launcher_id, launcher in self.launchers.items()
                if launcher.current_job_id is None
            }

    async def set_job_event(self, job_id: str) -> None:
        async with self.lock:
            current = self.job_events.get(job_id)
            if current is not None:
                current.set()

    async def wait_job_event(self, job_id: str, timeout: float) -> None:
        async with self.lock:
            event = self.job_events.setdefault(job_id, asyncio.Event())
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except TimeoutError:
            return

    async def get_slave_startup_timeout(self, launcher_id: str, slave_app_id: str) -> float | None:
        async with self.lock:
            launcher = self.launchers.get(launcher_id)
            if launcher is None:
                return None
            return launcher.slave_app_startup_timeouts.get(slave_app_id)


runtime = RuntimeRegistry()
