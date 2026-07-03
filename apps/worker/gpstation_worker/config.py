from socket import gethostname
from urllib.parse import urlparse, urlunparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GPSTATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_url: str = "http://localhost:8000"
    access_key: str = ""
    worker_name: str = Field(default_factory=gethostname)
    gpu_interval_sec: float = 5.0

    @field_validator("api_url")
    @classmethod
    def strip_api_url(cls, value: str) -> str:
        return value.rstrip("/") or "http://localhost:8000"

    @field_validator("gpu_interval_sec")
    @classmethod
    def validate_gpu_interval_sec(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("GPSTATION_GPU_INTERVAL_SEC must be greater than 0")
        return value

    @property
    def websocket_url(self) -> str:
        parsed = urlparse(self.api_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        base_path = parsed.path.rstrip("/")
        path = f"{base_path}/app/v1/workers/ws" if base_path else "/app/v1/workers/ws"
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))


def load_settings() -> WorkerSettings:
    return WorkerSettings()
