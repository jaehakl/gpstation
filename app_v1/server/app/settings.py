from __future__ import annotations

import json
import os
import uuid
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import BaseModel


DEMO_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "gpstation-v1:demo-user"))
APP_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = APP_ROOT / ".env"


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_local_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def default_secure_cookies() -> bool:
    env_name = "GPSTATION_V1_SECURE_COOKIES"
    if os.getenv(env_name):
        return env_bool(env_name, True)
    return not any(
        is_local_http_url(value)
        for value in (
            os.getenv("GPSTATION_V1_APP_BASE_URL", "http://127.0.0.1:3002"),
            os.getenv("GPSTATION_V1_GOOGLE_REDIRECT_URI", ""),
        )
    )


class TokenPrincipal(BaseModel):
    user_id: str
    scopes: list[str]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GPSTATION_V1_",
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gpstation_v1"
    host: str = "127.0.0.1"
    port: int = 8100
    reload: bool = False
    public_base_url: str = "http://127.0.0.1:8100"
    app_base_url: str = "http://127.0.0.1:3002"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    google_id_token_clock_skew_seconds: int = Field(default=10, ge=0, le=300)
    jwt_secret: str = "dev-gpstation-v1-secret-change-me-32"
    jwt_alg: str = "HS256"
    access_ttl_sec: int = Field(default=1200, gt=0)
    refresh_ttl_sec: int = Field(default=60 * 60 * 24 * 14, gt=0)
    cookie_domain: str = ""
    secure_cookies: bool = Field(default_factory=default_secure_cookies)
    session_ttl_seconds: int = Field(default=300, ge=10, le=3600)
    session_ready_timeout_seconds: float = Field(default=10.0, gt=0)
    cleanup_interval_seconds: float = Field(default=5.0, gt=0)
    cors_origins: str = "http://127.0.0.1:3001,http://localhost:3001,http://127.0.0.1:3002,http://localhost:3002"
    tokens: dict[str, TokenPrincipal] = Field(
        default_factory=lambda: {
            "demo-client-token": TokenPrincipal(user_id=DEMO_USER_ID, scopes=["client"]),
            "demo-launcher-token": TokenPrincipal(user_id=DEMO_USER_ID, scopes=["launcher"]),
        }
    )

    @field_validator("public_base_url")
    @classmethod
    def strip_public_base_url(cls, value: str) -> str:
        return value.rstrip("/") or "http://127.0.0.1:8100"

    @field_validator("app_base_url")
    @classmethod
    def strip_app_base_url(cls, value: str) -> str:
        return value.rstrip("/") or "http://127.0.0.1:3002"

    @field_validator("tokens", mode="before")
    @classmethod
    def parse_tokens(cls, value: object) -> object:
        if isinstance(value, str):
            return json.loads(value)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
