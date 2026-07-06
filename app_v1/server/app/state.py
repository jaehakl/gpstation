from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class WorkerRuntime:
    id: str
    websocket: WebSocket
    active_session_ids: set[str] = field(default_factory=set)


@dataclass
class SessionRuntime:
    id: str
    worker_id: str
    ready_event: asyncio.Event = field(default_factory=asyncio.Event)
    client_websocket: WebSocket | None = None
    pending_client_signals: list[dict[str, Any]] = field(default_factory=list)
    status: str = "starting"
    last_error: str | None = None


class RuntimeRegistry:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.workers: dict[str, WorkerRuntime] = {}
        self.sessions: dict[str, SessionRuntime] = {}

    async def register_worker(self, worker_id: str, websocket: WebSocket) -> WorkerRuntime:
        worker = WorkerRuntime(id=worker_id, websocket=websocket)
        async with self.lock:
            self.workers[worker_id] = worker
        return worker

    async def remove_worker(self, worker_id: str) -> list[SessionRuntime]:
        async with self.lock:
            self.workers.pop(worker_id, None)
            affected = [session for session in self.sessions.values() if session.worker_id == worker_id]
            for session in affected:
                self.sessions.pop(session.id, None)
                session.status = "error"
                session.last_error = "worker disconnected"
                session.ready_event.set()
            return affected

    async def get_worker(self, worker_id: str) -> WorkerRuntime | None:
        async with self.lock:
            return self.workers.get(worker_id)

    async def mark_heartbeat(self, worker_id: str, active_session_ids: list[str]) -> None:
        async with self.lock:
            worker = self.workers.get(worker_id)
            if worker is not None:
                worker.active_session_ids = set(active_session_ids)

    async def register_session(self, session_id: str, worker_id: str) -> SessionRuntime:
        session = SessionRuntime(id=session_id, worker_id=worker_id)
        async with self.lock:
            self.sessions[session_id] = session
            worker = self.workers.get(worker_id)
            if worker is not None:
                worker.active_session_ids.add(session_id)
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
            worker = self.workers.get(session.worker_id)
            if worker is not None:
                worker.active_session_ids.discard(session_id)
            session.status = "closed"
            session.ready_event.set()
            return session


runtime = RuntimeRegistry()
