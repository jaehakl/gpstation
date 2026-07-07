from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

SESSION_LOG_LINE_LIMIT = 500


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LauncherRuntime:
    id: str
    websocket: WebSocket
    active_session_ids: set[str] = field(default_factory=set)
    slave_app_startup_timeouts: dict[str, float] = field(default_factory=dict)
    current_job_id: str | None = None
    loaded_slave_app_id: str | None = None
    worker_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionRuntime:
    id: str
    launcher_id: str
    ready_event: asyncio.Event = field(default_factory=asyncio.Event)
    client_websocket: WebSocket | None = None
    pending_client_signals: list[dict[str, Any]] = field(default_factory=list)
    status: str = "starting"
    last_error: str | None = None


class RuntimeRegistry:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.launchers: dict[str, LauncherRuntime] = {}
        self.sessions: dict[str, SessionRuntime] = {}
        self.session_logs: dict[str, deque[dict[str, str]]] = {}
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

    async def remove_launcher(self, launcher_id: str) -> list[SessionRuntime]:
        async with self.lock:
            self.launchers.pop(launcher_id, None)
            affected = [session for session in self.sessions.values() if session.launcher_id == launcher_id]
            for session in affected:
                self.sessions.pop(session.id, None)
                session.status = "error"
                session.last_error = "launcher disconnected"
                session.ready_event.set()
            return affected

    async def get_launcher(self, launcher_id: str) -> LauncherRuntime | None:
        async with self.lock:
            return self.launchers.get(launcher_id)

    async def get_launcher_ids(self) -> set[str]:
        async with self.lock:
            return set(self.launchers.keys())

    async def mark_heartbeat(
        self,
        launcher_id: str,
        active_session_ids: list[str],
        *,
        current_job_id: str | None = None,
        loaded_slave_app_id: str | None = None,
        worker_status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        async with self.lock:
            launcher = self.launchers.get(launcher_id)
            if launcher is not None:
                launcher.active_session_ids = set(active_session_ids)
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
                    "active_session_ids": sorted(launcher.active_session_ids),
                }
                for launcher_id, launcher in self.launchers.items()
            }

    async def idle_launcher_ids(self) -> set[str]:
        async with self.lock:
            return {
                launcher_id
                for launcher_id, launcher in self.launchers.items()
                if launcher.current_job_id is None and not launcher.active_session_ids
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

    async def register_session(self, session_id: str, launcher_id: str) -> SessionRuntime:
        session = SessionRuntime(id=session_id, launcher_id=launcher_id)
        async with self.lock:
            self.sessions[session_id] = session
            self.session_logs.setdefault(session_id, deque(maxlen=SESSION_LOG_LINE_LIMIT))
            launcher = self.launchers.get(launcher_id)
            if launcher is not None:
                launcher.active_session_ids.add(session_id)
        return session

    async def get_session(self, session_id: str) -> SessionRuntime | None:
        async with self.lock:
            return self.sessions.get(session_id)

    async def mark_session_ready(self, session_id: str) -> SessionRuntime | None:
        async with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return None
            session.status = "ready"
            session.ready_event.set()
            return session

    async def mark_session_error(self, session_id: str, detail: str) -> SessionRuntime | None:
        async with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return None
            session.status = "error"
            session.last_error = detail
            session.ready_event.set()
            return session

    async def attach_client(self, session_id: str, websocket: WebSocket) -> SessionRuntime:
        async with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise KeyError("session not available")
            session.client_websocket = websocket
            return session

    async def detach_client(self, session_id: str, websocket: WebSocket) -> None:
        async with self.lock:
            session = self.sessions.get(session_id)
            if session is not None and session.client_websocket is websocket:
                session.client_websocket = None

    async def store_or_get_client_socket(
        self,
        session_id: str,
        signal: dict[str, Any],
    ) -> WebSocket | None:
        async with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return None
            if session.client_websocket is None:
                session.pending_client_signals.append(signal)
                return None
            return session.client_websocket

    async def take_pending_client_signals(self, session_id: str) -> list[dict[str, Any]]:
        async with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return []
            pending = session.pending_client_signals
            session.pending_client_signals = []
            return pending

    async def close_session(self, session_id: str) -> SessionRuntime | None:
        async with self.lock:
            session = self.sessions.pop(session_id, None)
            if session is None:
                return None
            launcher = self.launchers.get(session.launcher_id)
            if launcher is not None:
                launcher.active_session_ids.discard(session_id)
            session.status = "closed"
            session.ready_event.set()
            return session

    async def append_session_log(
        self,
        session_id: str,
        stream: str,
        line: str,
        logged_at: str | None = None,
    ) -> None:
        async with self.lock:
            items = self.session_logs.setdefault(session_id, deque(maxlen=SESSION_LOG_LINE_LIMIT))
            items.append(
                {
                    "time": logged_at or utcnow().isoformat(),
                    "stream": stream,
                    "line": line,
                }
            )

    async def get_session_logs(self, session_id: str, limit: int = 200) -> list[dict[str, str]]:
        async with self.lock:
            items = list(self.session_logs.get(session_id, ()))
        clamped_limit = max(1, min(limit, SESSION_LOG_LINE_LIMIT))
        return items[-clamped_limit:]


runtime = RuntimeRegistry()
