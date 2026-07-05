from __future__ import annotations

import asyncio
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import WebSocket


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class WorkerConnection:
    id: str
    user_id: str
    worker_name: str
    capabilities: list[str]
    websocket: WebSocket
    connected_at: datetime
    last_heartbeat_at: datetime
    status: str = "ready"
    active_session_ids: set[str] = field(default_factory=set)


@dataclass
class ClientSession:
    id: str
    user_id: str
    worker_session_id: str
    token: str
    created_at: datetime
    expires_at: datetime
    ttl_seconds: int
    ready_event: asyncio.Event = field(default_factory=asyncio.Event)
    status: str = "starting"
    client_websocket: WebSocket | None = None
    pending_client_signals: list[dict[str, Any]] = field(default_factory=list)
    last_error: str | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        return self.expires_at <= (now or utcnow())


class RuntimeState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.workers: dict[str, WorkerConnection] = {}
        self.sessions: dict[str, ClientSession] = {}

    async def register_worker(
        self,
        *,
        user_id: str,
        worker_name: str,
        capabilities: list[str],
        websocket: WebSocket,
    ) -> WorkerConnection:
        now = utcnow()
        worker = WorkerConnection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            worker_name=worker_name,
            capabilities=capabilities,
            websocket=websocket,
            connected_at=now,
            last_heartbeat_at=now,
        )
        async with self.lock:
            self.workers[worker.id] = worker
        return worker

    async def remove_worker(self, worker_id: str) -> list[ClientSession]:
        async with self.lock:
            worker = self.workers.pop(worker_id, None)
            if worker is None:
                return []
            affected = []
            for session_id in worker.active_session_ids:
                session = self.sessions.pop(session_id, None)
                if session is not None:
                    affected.append(session)
            for session in affected:
                session.status = "error"
                session.last_error = "worker disconnected"
                session.ready_event.set()
            return affected

    async def list_workers_for_user(self, user_id: str) -> list[WorkerConnection]:
        async with self.lock:
            return [worker for worker in self.workers.values() if worker.user_id == user_id]

    async def create_session(
        self,
        *,
        user_id: str,
        worker_session_id: str,
        ttl_seconds: int,
    ) -> ClientSession:
        async with self.lock:
            worker = self.workers.get(worker_session_id)
            if worker is None or worker.user_id != user_id or worker.status not in {"ready", "busy"}:
                raise KeyError("worker not available")

            now = utcnow()
            session = ClientSession(
                id=str(uuid.uuid4()),
                user_id=user_id,
                worker_session_id=worker_session_id,
                token=secrets.token_urlsafe(32),
                created_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
                ttl_seconds=ttl_seconds,
            )
            self.sessions[session.id] = session
            worker.active_session_ids.add(session.id)
            worker.status = "busy"
            return session

    async def get_session(self, session_id: str) -> ClientSession | None:
        async with self.lock:
            return self.sessions.get(session_id)

    async def get_worker(self, worker_id: str) -> WorkerConnection | None:
        async with self.lock:
            return self.workers.get(worker_id)

    async def mark_heartbeat(self, worker_id: str, status: str, active_session_ids: list[str]) -> None:
        async with self.lock:
            worker = self.workers.get(worker_id)
            if worker is None:
                return
            worker.last_heartbeat_at = utcnow()
            worker.status = status
            worker.active_session_ids = set(active_session_ids)

    async def mark_session_ready(self, session_id: str) -> None:
        async with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return
            session.status = "ready"
            session.ready_event.set()

    async def mark_session_error(self, session_id: str, detail: str) -> ClientSession | None:
        async with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return None
            session.status = "error"
            session.last_error = detail
            session.ready_event.set()
            return session

    async def attach_client(self, session_id: str, websocket: WebSocket, token: str) -> ClientSession:
        async with self.lock:
            session = self.sessions.get(session_id)
            if session is None or session.token != token or session.is_expired():
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

    async def close_session(self, session_id: str, reason: str) -> ClientSession | None:
        async with self.lock:
            session = self.sessions.pop(session_id, None)
            if session is None:
                return None
            worker = self.workers.get(session.worker_session_id)
            if worker is not None:
                worker.active_session_ids.discard(session_id)
                if not worker.active_session_ids:
                    worker.status = "ready"
            session.status = "closed"
            session.last_error = reason
            session.ready_event.set()
            return session

    async def collect_expired_sessions(self) -> list[ClientSession]:
        now = utcnow()
        async with self.lock:
            expired = [session for session in self.sessions.values() if session.is_expired(now)]
        closed: list[ClientSession] = []
        for session in expired:
            closed_session = await self.close_session(session.id, "expired")
            if closed_session is not None:
                closed.append(closed_session)
        return closed
