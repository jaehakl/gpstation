from __future__ import annotations

import asyncio
import json
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from app.settings import LauncherSettings
from app.slave_registry import SlaveAppRegistry, load_default_registry

SendControl = Callable[[dict[str, Any]], Awaitable[None]]
JOB_LOG_LINE_LIMIT = 500


@dataclass
class ManagedWorker:
    slave_app_id: str
    process: asyncio.subprocess.Process
    ready_event: asyncio.Event
    stdout_task: asyncio.Task[None]
    stderr_task: asyncio.Task[None]
    ready: bool = False
    stopping: bool = False


class WorkerManager:
    def __init__(
        self,
        settings: LauncherSettings,
        send_control: SendControl,
        registry: SlaveAppRegistry | None = None,
        forward_job_logs: bool = True,
    ) -> None:
        self.settings = settings
        self.send_control = send_control
        self.registry = registry or load_default_registry()
        self.forward_job_logs = forward_job_logs
        self.job_logs: dict[str, deque[dict[str, str]]] = {}
        self.worker: ManagedWorker | None = None
        self.current_job_id: str | None = None
        self.worker_status = "idle"

    def current_worker_slave_app_id(self) -> str | None:
        return self.worker.slave_app_id if self.worker is not None else None

    async def stop_all(self, reason: str) -> None:
        await self.reset_worker(reason)

    async def start_job(
        self,
        *,
        job_id: str,
        handler_type: str,
        slave_app_id: str,
        offer: dict[str, Any],
    ) -> None:
        if self.current_job_id is not None:
            await self.send_control(
                {
                    "type": "job.error",
                    "job_id": job_id,
                    "code": "launcher_busy",
                    "detail": f"launcher is busy with job {self.current_job_id}",
                }
            )
            return
        if self.registry.get(slave_app_id) is None:
            await self.send_control(
                {
                    "type": "job.error",
                    "job_id": job_id,
                    "code": "unknown_slave_app",
                    "detail": f"unknown slave app: {slave_app_id}",
                }
            )
            return

        self.current_job_id = job_id
        self.worker_status = "starting"
        try:
            await self.ensure_worker(slave_app_id)
        except Exception as exc:
            self.current_job_id = None
            self.worker_status = "idle"
            await self.send_control(
                {
                    "type": "job.error",
                    "job_id": job_id,
                    "code": "worker_start_failed",
                    "detail": str(exc),
                }
            )
            return

        if self.worker is None or self.worker.process.stdin is None:
            self.current_job_id = None
            self.worker_status = "idle"
            await self.send_control(
                {
                    "type": "job.error",
                    "job_id": job_id,
                    "code": "worker_missing",
                    "detail": "worker subprocess is not running",
                }
            )
            return

        self.worker_status = "busy"
        try:
            self.worker.process.stdin.write(
                json_line(
                    {
                        "type": "job.start",
                        "job_id": job_id,
                        "handler_type": handler_type,
                        "slave_app_id": slave_app_id,
                        "offer": offer,
                    }
                )
            )
            await self.worker.process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            self.current_job_id = None
            self.worker_status = "idle"
            await self.send_control(
                {
                    "type": "job.error",
                    "job_id": job_id,
                    "code": "worker_ipc_failed",
                    "detail": str(exc),
                }
            )

    async def ensure_worker(self, slave_app_id: str) -> None:
        if self.worker is not None and self.worker.process.returncode is None and self.worker.slave_app_id == slave_app_id:
            return
        if self.worker is not None:
            await self.reset_worker("switch slave app", cancel_current_job=False, notify_reset=False)

        slave_app = self.registry.require(slave_app_id)
        if not slave_app.python_executable.exists():
            raise RuntimeError(f"slave executable environment is missing; run `{slave_app.install_hint}`")

        process = await asyncio.create_subprocess_exec(
            *self.registry.worker_subprocess_args(slave_app_id),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=subprocess_env(self.settings),
            cwd=slave_app.project_dir,
        )
        ready_event = asyncio.Event()
        worker = ManagedWorker(
            slave_app_id=slave_app_id,
            process=process,
            ready_event=ready_event,
            stdout_task=asyncio.create_task(self.read_worker_stdout(process, ready_event)),
            stderr_task=asyncio.create_task(self.read_worker_stderr(process)),
        )
        self.worker = worker
        self.worker_status = "starting"
        ready_timeout_seconds = self.ready_timeout_seconds_for(slave_app_id)
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=ready_timeout_seconds)
        except TimeoutError as exc:
            await self.reset_worker("worker ready timeout", cancel_current_job=False, notify_reset=False)
            raise RuntimeError(f"worker did not become ready within {ready_timeout_seconds:g}s") from exc
        if not worker.ready:
            await self.reset_worker("worker startup failed", cancel_current_job=False, notify_reset=False)
            raise RuntimeError("worker exited before ready")
        self.worker_status = "idle"

    async def cancel_job(self, job_id: str, reason: str) -> None:
        if self.current_job_id != job_id:
            return
        if self.worker is None or self.worker.process.stdin is None or self.worker.process.returncode is not None:
            await self.send_control({"type": "job.cancelled", "job_id": job_id, "reason": reason})
            self.current_job_id = None
            self.worker_status = "idle"
            return
        self.worker_status = "cancelling"
        try:
            self.worker.process.stdin.write(json_line({"type": "job.cancel", "job_id": job_id, "reason": reason}))
            await self.worker.process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            await self.reset_worker(reason)

    async def reset_worker(self, reason: str, *, cancel_current_job: bool = True, notify_reset: bool = True) -> None:
        worker = self.worker
        current_job_id = self.current_job_id if cancel_current_job else None
        self.worker = None
        if cancel_current_job:
            self.current_job_id = None
        self.worker_status = "idle"
        if worker is None:
            return
        worker.stopping = True
        if worker.process.stdin is not None and worker.process.returncode is None:
            try:
                worker.process.stdin.write(json_line({"type": "stop", "reason": reason}))
                await worker.process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
        try:
            await asyncio.wait_for(worker.process.wait(), timeout=3)
        except TimeoutError:
            worker.process.terminate()
            await worker.process.wait()
        worker.stdout_task.cancel()
        worker.stderr_task.cancel()
        if current_job_id is not None:
            await self.send_control({"type": "job.cancelled", "job_id": current_job_id, "reason": reason})
        if notify_reset:
            await self.send_control({"type": "worker.reset.done"})

    async def read_worker_stdout(
        self,
        process: asyncio.subprocess.Process,
        ready_event: asyncio.Event,
    ) -> None:
        assert process.stdout is not None
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                await self.handle_worker_message(json.loads(line.decode("utf-8")))
        finally:
            worker = self.worker
            if worker is not None and worker.process is process and not worker.stopping:
                if not worker.ready:
                    ready_event.set()
                failed_job_id = self.current_job_id
                self.worker = None
                self.current_job_id = None
                self.worker_status = "error"
                if failed_job_id is not None:
                    await self.send_control(
                        {
                            "type": "job.error",
                            "job_id": failed_job_id,
                            "code": "worker_exit",
                            "detail": "worker subprocess exited",
                        }
                    )

    async def read_worker_stderr(self, process: asyncio.subprocess.Process) -> None:
        assert process.stderr is not None
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            job_id = self.current_job_id or "worker"
            await self.record_subprocess_log(
                job_id,
                "stderr",
                line.decode("utf-8", errors="replace").rstrip(),
            )

    async def record_subprocess_log(self, job_id: str, stream: str, line: str) -> None:
        logged_at = datetime.now(timezone.utc).isoformat()
        items = self.job_logs.setdefault(job_id, deque(maxlen=JOB_LOG_LINE_LIMIT))
        items.append({"time": logged_at, "stream": stream, "line": line})
        print(f"[{job_id}] {line}", flush=True)
        if not self.forward_job_logs:
            return
        await self.send_control(
            {
                "type": "job.log",
                "job_id": job_id,
                "time": logged_at,
                "stream": stream,
                "line": line,
            }
        )

    def get_job_logs(self, job_id: str, limit: int = 200) -> list[dict[str, str]]:
        items = list(self.job_logs.get(job_id, ()))
        clamped_limit = max(1, min(limit, JOB_LOG_LINE_LIMIT))
        return items[-clamped_limit:]

    def ready_timeout_seconds_for(self, slave_app_id: str) -> float:
        slave_app = self.registry.get(slave_app_id)
        startup_timeout_seconds = slave_app.startup_timeout_seconds if slave_app is not None else None
        return max(self.settings.worker_ready_timeout_seconds, startup_timeout_seconds or 0)

    async def handle_worker_message(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "worker.ready":
            if self.worker is not None:
                self.worker.ready = True
                self.worker.ready_event.set()
            return
        if message_type in {
            "job.answer",
            "job.running",
            "job.progress",
            "job.result",
            "job.error",
            "job.cancelled",
        }:
            await self.send_control(message)
            if message_type in {"job.result", "job.error", "job.cancelled"}:
                self.current_job_id = None
                self.worker_status = "idle"
            return
        if message_type == "error" and self.current_job_id is not None:
            await self.send_control(
                {
                    "type": "job.error",
                    "job_id": self.current_job_id,
                    "code": str(message.get("code") or "worker_error"),
                    "detail": str(message.get("detail") or "worker error"),
                }
            )
            self.current_job_id = None
            self.worker_status = "idle"


def json_line(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")


def subprocess_env(settings: LauncherSettings) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["GPSTATION_V1_RTC_ICE_SERVERS_JSON"] = settings.rtc_ice_servers_json
    if settings.rtc_ice_gather_timeout_seconds:
        env["GPSTATION_V1_RTC_ICE_GATHER_TIMEOUT_SECONDS"] = settings.rtc_ice_gather_timeout_seconds
    if settings.rtc_memory_cache_enabled:
        env["GPSTATION_V1_RTC_MEMORY_CACHE_ENABLED"] = settings.rtc_memory_cache_enabled
    return env
