from __future__ import annotations

from pathlib import Path
from socket import gethostname
from urllib.parse import urlparse, urlunparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = APP_ROOT / ".env"
DEFAULT_RTC_ICE_SERVERS_JSON = '[{"urls":"stun:stun.l.google.com:19302"}]'


class LauncherSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GPSTATION_V1_",
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_url: str
    access_token: str
    launcher_name: str = Field(default_factory=gethostname)
    heartbeat_interval_seconds: float = Field(default=5.0, gt=0)
    session_ready_timeout_seconds: float = Field(default=10.0, gt=0)
    rtc_ice_servers_json: str = DEFAULT_RTC_ICE_SERVERS_JSON

    @field_validator("api_url")
    @classmethod
    def strip_api_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("rtc_ice_servers_json")
    @classmethod
    def strip_rtc_ice_servers_json(cls, value: str) -> str:
        return value.strip() or DEFAULT_RTC_ICE_SERVERS_JSON

    @property
    def control_websocket_url(self) -> str:
        parsed = urlparse(self.api_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        base_path = parsed.path.rstrip("/")
        path = f"{base_path}/v1/launchers/control" if base_path else "/v1/launchers/control"
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))


def load_settings() -> LauncherSettings:
    return LauncherSettings()
