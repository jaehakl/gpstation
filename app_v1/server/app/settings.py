from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = APP_ROOT / ".env"
PLACEHOLDER_PARTS = ("change-this", "change-me", "dev-", "placeholder", "example", "replace-with")


def is_local_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GPSTATION_V1_",
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = Field(...)
    host: str = Field(...)
    port: int = Field(...)
    reload: bool = Field(...)
    public_base_url: str = Field(...)
    app_base_url: str = Field(...)
    google_client_id: str = Field(...)
    google_client_secret: str = Field(...)
    google_redirect_uri: str = Field(...)
    google_id_token_clock_skew_seconds: int = Field(..., ge=0, le=300)
    oauth_state_ttl_seconds: int = Field(..., ge=60, le=3600)
    jwt_secret: str = Field(...)
    jwt_alg: str = Field(...)
    access_ttl_sec: int = Field(..., gt=0)
    refresh_ttl_sec: int = Field(..., gt=0)
    cookie_domain: str = Field(...)
    secure_cookies: bool = Field(...)
    cors_origins: str = Field(...)

    @field_validator("public_base_url")
    @classmethod
    def strip_public_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("app_base_url")
    @classmethod
    def strip_app_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("google_redirect_uri")
    @classmethod
    def strip_google_redirect_uri(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


def validate_runtime_settings(config: Settings) -> None:
    errors: list[str] = []

    require_value(errors, "GPSTATION_V1_DB_URL", config.db_url)
    require_value(errors, "GPSTATION_V1_GOOGLE_CLIENT_ID", config.google_client_id)
    require_value(errors, "GPSTATION_V1_GOOGLE_CLIENT_SECRET", config.google_client_secret)
    require_value(errors, "GPSTATION_V1_GOOGLE_REDIRECT_URI", config.google_redirect_uri)
    require_value(errors, "GPSTATION_V1_JWT_SECRET", config.jwt_secret)
    require_value(errors, "GPSTATION_V1_PUBLIC_BASE_URL", config.public_base_url)
    require_value(errors, "GPSTATION_V1_APP_BASE_URL", config.app_base_url)

    if is_placeholder(config.db_url) or "postgres:postgres@" in config.db_url:
        errors.append("GPSTATION_V1_DB_URL must not use placeholder credentials")
    if is_placeholder(config.jwt_secret) or len(config.jwt_secret) < 32:
        errors.append("GPSTATION_V1_JWT_SECRET must be a non-placeholder secret with at least 32 characters")

    redirect_uri = google_redirect_uri_for(config)
    validate_http_url(errors, "GPSTATION_V1_PUBLIC_BASE_URL", config.public_base_url, allow_local_http=True)
    validate_http_url(errors, "GPSTATION_V1_APP_BASE_URL", config.app_base_url, allow_local_http=True)
    validate_http_url(errors, "GPSTATION_V1_GOOGLE_REDIRECT_URI", redirect_uri, allow_local_http=True)

    origins = config.cors_origin_list
    if not origins:
        errors.append("GPSTATION_V1_CORS_ORIGINS must include at least one explicit origin")
    for origin in origins:
        if origin == "*":
            errors.append("GPSTATION_V1_CORS_ORIGINS must not include *")
        else:
            validate_http_url(errors, "GPSTATION_V1_CORS_ORIGINS", origin, allow_local_http=True)

    if errors:
        raise RuntimeError("Invalid GPStation v1 settings: " + "; ".join(errors))


def google_redirect_uri_for(config: Settings) -> str:
    return config.google_redirect_uri.strip()


def require_value(errors: list[str], name: str, value: str) -> None:
    if not value or not value.strip():
        errors.append(f"{name} is required")


def is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return any(part in lowered for part in PLACEHOLDER_PARTS)


def validate_http_url(errors: list[str], name: str, value: str, *, allow_local_http: bool) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{name} must be an absolute http(s) URL")
        return
    if parsed.scheme == "http" and not (allow_local_http and is_local_http_url(value)):
        errors.append(f"{name} must use https unless it is localhost")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
