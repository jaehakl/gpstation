from __future__ import annotations

from typing import Any

from gpstation_worker import __version__
from gpstation_worker.config import WorkerSettings
from gpstation_worker.gpu import GpuStatus


def make_hello(settings: WorkerSettings) -> dict[str, Any]:
    return {
        "type": "hello",
        "device_name": settings.worker_name,
        "client_version": __version__,
        "accepting_jobs": False,
    }


def make_gpu_status(gpu: GpuStatus) -> dict[str, Any]:
    return {
        "type": "gpu_status",
        "status": "ready",
        "gpu": gpu.to_dict(),
    }
