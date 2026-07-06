from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from gpstation_slave_launcher_v1.settings import WorkerSettings
from gpstation_slave_launcher_v1.slave_registry import SlaveAppRegistry, load_default_registry

SendControl = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class ManagedSession:
    session_id: str
    slave_app_id: str
    process: asyncio.subprocess.Process
    ready_event: asyncio.Event
    stdout_task: asyncio.Task[None]
    stderr_task: asyncio.Task[None]
    ready: bool = False
    startup_failed: bool = False
    stopping: bool = False


class SessionManager:
    def __init__(
        self,
        settings: WorkerSettings,
        send_control: SendControl,
        registry: SlaveAppRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.send_control = send_control
        self.registry = registry or load_default_registry()
        self.sessions: dict[str, ManagedSession] = {}

    def active_session_ids(self) -> list[str]:
        return sorted(self.sessions.keys())

    async def start_session(self, session_id: str, slave_app_id: str, ttl_seconds: int) -> None:
        if session_id in self.sessions:
            await self.send_control(
                {
                    "type": "session.error",
                    "session_id": session_id,
                    "code": "duplicate_session",
                    "detail": "session already exists",
                }
            )
            return
        if self.registry.get(slave_app_id) is None:
            await self.send_control(
                {
                    "type": "session.error",
                    "session_id": session_id,
                    "code": "unknown_slave_app",
                    "detail": f"unknown slave app: {slave_app_id}",
                }
            )
            return

        process = await asyncio.create_subprocess_exec(
            *self.registry.subprocess_args(
                self.settings.subprocess_python,
                session_id,
                slave_app_id,
                ttl_seconds,
            ),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=subprocess_env(),
        )
        ready_event = asyncio.Event()
        session = ManagedSession(
            session_id=session_id,
            slave_app_id=slave_app_id,
            process=process,
            ready_event=ready_event,
            stdout_task=asyncio.create_task(self.read_stdout(session_id, process, ready_event)),
            stderr_task=asyncio.create_task(self.read_stderr(session_id, process)),
        )
        self.sessions[session_id] = session

        try:
            await asyncio.wait_for(ready_event.wait(), timeout=self.settings.session_ready_timeout_seconds)
        except TimeoutError:
            await self.stop_session(session_id, "ready timeout")
            await self.send_control(
                {
                    "type": "session.error",
                    "session_id": session_id,
                    "code": "ready_timeout",
                    "detail": "slave subprocess did not become ready",
                }
            )
            return

        if not session.ready:
            await self.stop_session(session_id, "startup failed")
            if not session.startup_failed:
                await self.send_control(
                    {
                        "type": "session.error",
                        "session_id": session_id,
                        "code": "startup_failed",
                        "detail": "slave subprocess exited before ready",
                    }
                )
            return

        await self.send_control({"type": "session.ready", "session_id": session_id})

    async def forward_signal(self, session_id: str, signal: dict[str, Any]) -> None:
        session = self.sessions.get(session_id)
        if session is None or session.process.stdin is None:
            await self.send_control(
                {
                    "type": "session.error",
                    "session_id": session_id,
                    "code": "missing_session",
                    "detail": "slave subprocess is not running",
                }
            )
            return

        session.process.stdin.write(json_line({"type": "signal", "signal": signal}))
        await session.process.stdin.drain()

    async def stop_session(self, session_id: str, reason: str) -> None:
        session = self.sessions.pop(session_id, None)
        if session is None:
            return
        session.stopping = True
        if session.process.stdin is not None and session.process.returncode is None:
            session.process.stdin.write(json_line({"type": "stop", "reason": reason}))
            await session.process.stdin.drain()
        try:
            await asyncio.wait_for(session.process.wait(), timeout=3)
        except TimeoutError:
            session.process.terminate()
            await session.process.wait()
        session.stdout_task.cancel()
        session.stderr_task.cancel()

    async def stop_all(self, reason: str) -> None:
        for session_id in list(self.sessions):
            await self.stop_session(session_id, reason)

    async def read_stdout(
        self,
        session_id: str,
        process: asyncio.subprocess.Process,
        ready_event: asyncio.Event,
    ) -> None:
        assert process.stdout is not None
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                await self.handle_subprocess_message(session_id, json.loads(line.decode("utf-8")))
        finally:
            session = self.sessions.get(session_id)
            if session is not None and not session.stopping:
                if not session.ready:
                    session.startup_failed = True
                    ready_event.set()
                self.sessions.pop(session_id, None)
                await self.send_control(
                    {
                        "type": "session.error",
                        "session_id": session_id,
                        "code": "subprocess_exit",
                        "detail": "slave subprocess exited",
                    }
                )

    async def read_stderr(self, session_id: str, process: asyncio.subprocess.Process) -> None:
        assert process.stderr is not None
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            print(f"[{session_id}] {line.decode('utf-8', errors='replace').rstrip()}", flush=True)

    async def handle_subprocess_message(self, session_id: str, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "ready":
            session = self.sessions.get(session_id)
            if session is not None:
                session.ready = True
                session.ready_event.set()
            return
        if message_type == "signal":
            await self.send_control(
                {
                    "type": "signal.to_client",
                    "session_id": session_id,
                    "signal": message["signal"],
                }
            )
            return
        if message_type == "closed":
            session = self.sessions.pop(session_id, None)
            if session is not None and not session.ready:
                session.startup_failed = True
                session.ready_event.set()
            await self.send_control({"type": "session.closed", "session_id": session_id, "reason": "closed"})
            return
        if message_type == "error":
            session = self.sessions.pop(session_id, None)
            if session is not None and not session.ready:
                session.startup_failed = True
                session.ready_event.set()
            await self.send_control(
                {
                    "type": "session.error",
                    "session_id": session_id,
                    "code": str(message.get("code") or "subprocess_error"),
                    "detail": str(message.get("detail") or "slave subprocess error"),
                }
            )


def json_line(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")


def subprocess_env() -> dict[str, str]:
    return os.environ.copy()
