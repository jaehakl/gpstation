from __future__ import annotations

from socket import gethostname
from urllib.parse import urlparse, urlunparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GPSTATION_V1_",
        extra="ignore",
    )

    api_url: str = "http://127.0.0.1:8100"
    access_token: str = "demo-worker-token"
    worker_name: str = Field(default_factory=gethostname)
    heartbeat_interval_seconds: float = Field(default=5.0, gt=0)
    session_ready_timeout_seconds: float = Field(default=10.0, gt=0)

    @field_validator("api_url")
    @classmethod
    def strip_api_url(cls, value: str) -> str:
        return value.rstrip("/") or "http://127.0.0.1:8100"

    @property
    def control_websocket_url(self) -> str:
        parsed = urlparse(self.api_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        base_path = parsed.path.rstrip("/")
        path = f"{base_path}/v1/workers/control" if base_path else "/v1/workers/control"
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))


def load_settings() -> WorkerSettings:
    return WorkerSettings()
