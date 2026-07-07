from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


ModelKey = tuple[Any, ...]
ReleaseLoadedModel = Callable[[int], None]


@dataclass(frozen=True)
class LoadedGpuModel:
    role: str
    model_key: ModelKey
    release_loaded_model: ReleaseLoadedModel


_gpu_locks: dict[int, asyncio.Lock] = {}
_loaded_models_by_device: dict[int, LoadedGpuModel] = {}


def get_cuda_device_count() -> int:
    try:
        import torch

        if not torch.cuda.is_available():
            return 0
        return torch.cuda.device_count()
    except Exception:
        return 0


def get_llm_cuda_device_id(use_gpu: bool) -> int | None:
    if not use_gpu:
        return None
    return 0 if get_cuda_device_count() > 0 else None


def get_image_cuda_device_id() -> int:
    return 1 if get_cuda_device_count() >= 2 else 0


def reset_gpu_residency_for_tests() -> None:
    _gpu_locks.clear()
    _loaded_models_by_device.clear()


class GpuModelLease:
    def __init__(
        self,
        role: str,
        device_id: int | None,
        model_key: ModelKey,
        release_loaded_model: ReleaseLoadedModel,
    ) -> None:
        self.role = role
        self.device_id = device_id
        self.model_key = model_key
        self.release_loaded_model = release_loaded_model
        self._lock: asyncio.Lock | None = None

    async def __aenter__(self) -> GpuModelLease:
        if self.device_id is None or self.device_id >= get_cuda_device_count():
            return self

        self._lock = _get_gpu_lock(self.device_id)
        await self._lock.acquire()
        try:
            current = _loaded_models_by_device.get(self.device_id)
            if current is not None and (
                current.role != self.role or current.model_key != self.model_key
            ):
                await asyncio.to_thread(current.release_loaded_model, self.device_id)

            _loaded_models_by_device[self.device_id] = LoadedGpuModel(
                role=self.role,
                model_key=self.model_key,
                release_loaded_model=self.release_loaded_model,
            )
        except Exception:
            self._lock.release()
            self._lock = None
            raise
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        if self._lock is not None:
            self._lock.release()
            self._lock = None


def acquire_gpu_model(
    role: str,
    device_id: int | None,
    model_key: ModelKey,
    release_loaded_model: ReleaseLoadedModel,
) -> GpuModelLease:
    return GpuModelLease(role, device_id, model_key, release_loaded_model)


def _get_gpu_lock(device_id: int) -> asyncio.Lock:
    lock = _gpu_locks.get(device_id)
    if lock is None:
        lock = asyncio.Lock()
        _gpu_locks[device_id] = lock
    return lock
