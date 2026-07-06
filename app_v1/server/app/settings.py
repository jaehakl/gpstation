from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import BaseModel


class TokenPrincipal(BaseModel):
    user_id: str
    scopes: list[str]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GPSTATION_V1_",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8100
    reload: bool = False
    public_base_url: str = "http://127.0.0.1:8100"
    session_ttl_seconds: int = Field(default=300, ge=10, le=3600)
    session_ready_timeout_seconds: float = Field(default=10.0, gt=0)
    cleanup_interval_seconds: float = Field(default=5.0, gt=0)
    cors_origins: str = "http://127.0.0.1:3001,http://localhost:3001"
    tokens: dict[str, TokenPrincipal] = Field(
        default_factory=lambda: {
            "demo-client-token": TokenPrincipal(user_id="demo-user", scopes=["client"]),
            "demo-worker-token": TokenPrincipal(user_id="demo-user", scopes=["worker"]),
        }
    )

    @field_validator("public_base_url")
    @classmethod
    def strip_public_base_url(cls, value: str) -> str:
        return value.rstrip("/") or "http://127.0.0.1:8100"

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
