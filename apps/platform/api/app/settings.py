import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_local_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def default_secure_cookies() -> bool:
    value = os.getenv("SECURE_COOKIES")
    if value is not None and value != "":
        return env_bool("SECURE_COOKIES", True)
    return not any(
        is_local_http_url(url)
        for url in (
            os.getenv("APP_BASE_URL", "http://localhost:3000"),
            os.getenv("GOOGLE_REDIRECT_URI", ""),
        )
    )


class Settings(BaseModel):
    db_url: str = os.getenv("DB_URL", "")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "")

    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:3000")
    app_timezone: str = os.getenv("APP_TIMEZONE", "Asia/Seoul")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALG: str = "HS256"
    ACCESS_TTL_SEC: int = 1200
    REFRESH_TTL_SEC: int = 60 * 60 * 24 * 14
    COOKIE_DOMAIN: str = os.getenv("COOKIE_DOMAIN", "")
    SECURE_COOKIES: bool = default_secure_cookies()


settings = Settings()
