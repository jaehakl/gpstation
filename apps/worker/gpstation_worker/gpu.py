from __future__ import annotations

import csv
import subprocess
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any


@dataclass
class GpuStatus:
    name: str | None
    vendor: str | None
    vram_total_mb: int | None
    vram_available_mb: int | None
    temperature_c: float | None
    utilization_pct: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_gpu_status() -> GpuStatus:
    return get_gpu_status_from_pynvml() or get_gpu_status_from_nvidia_smi() or GpuStatus(
        name=None,
        vendor="none",
        vram_total_mb=None,
        vram_available_mb=None,
        temperature_c=None,
        utilization_pct=None,
    )


def get_gpu_status_from_pynvml() -> GpuStatus | None:
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8", errors="replace")
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
        try:
            temperature = float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
        except Exception:
            temperature = None

        return GpuStatus(
            name=str(name),
            vendor="nvidia",
            vram_total_mb=int(memory.total / 1024 / 1024),
            vram_available_mb=int(memory.free / 1024 / 1024),
            temperature_c=temperature,
            utilization_pct=float(utilization.gpu),
        )
    except Exception:
        return None
    finally:
        try:
            import pynvml

            pynvml.nvmlShutdown()
        except Exception:
            pass


def get_gpu_status_from_nvidia_smi() -> GpuStatus | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,temperature.gpu,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None

    first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if not first_line:
        return None

    row = next(csv.reader(StringIO(first_line)))
    if len(row) < 5:
        return None

    return GpuStatus(
        name=row[0].strip() or None,
        vendor="nvidia",
        vram_total_mb=parse_int(row[1]),
        vram_available_mb=parse_int(row[2]),
        temperature_c=parse_float(row[3]),
        utilization_pct=parse_float(row[4]),
    )


def parse_int(value: str) -> int | None:
    try:
        return int(float(value.strip()))
    except ValueError:
        return None


def parse_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except ValueError:
        return None
