from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import Settings, validate_runtime_settings


REQUIRED_ENV_LINES = [
    "GPSTATION_V1_DB_URL=postgresql+asyncpg://gpstation:local-secret@127.0.0.1:5432/gpstation_v1",
    "GPSTATION_V1_HOST=127.0.0.1",
    "GPSTATION_V1_PORT=8000",
    "GPSTATION_V1_RELOAD=false",
    "GPSTATION_V1_PUBLIC_BASE_URL=http://127.0.0.1:8000",
    "GPSTATION_V1_APP_BASE_URL=http://localhost:3000",
    "GPSTATION_V1_GOOGLE_CLIENT_ID=local-client-id.apps.googleusercontent.com",
    "GPSTATION_V1_GOOGLE_CLIENT_SECRET=local-google-client-secret",
    "GPSTATION_V1_GOOGLE_REDIRECT_URI=http://localhost:8000/web/auth/google/callback",
    "GPSTATION_V1_GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS=10",
    "GPSTATION_V1_OAUTH_STATE_TTL_SECONDS=600",
    "GPSTATION_V1_JWT_SECRET=local-test-jwt-secret-with-at-least-32-characters",
    "GPSTATION_V1_JWT_ALG=HS256",
    "GPSTATION_V1_ACCESS_TTL_SEC=1200",
    "GPSTATION_V1_REFRESH_TTL_SEC=1209600",
    "GPSTATION_V1_COOKIE_DOMAIN=",
    "GPSTATION_V1_SECURE_COOKIES=false",
    "GPSTATION_V1_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000",
]


def test_settings_env_file_is_server_app_root_dotenv():
    assert Path(Settings.model_config["env_file"]) == Path(__file__).resolve().parents[1] / ".env"
    assert Settings.model_config["env_file_encoding"] == "utf-8"


def test_settings_reads_prefixed_values_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                *REQUIRED_ENV_LINES,
                "GPSTATION_V1_PORT=8001",
                "GPSTATION_V1_PUBLIC_BASE_URL=http://localhost:8000/base/",
                "GPSTATION_V1_GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS=12",
                "GPSTATION_V1_OAUTH_STATE_TTL_SECONDS=300",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("GPSTATION_V1_PORT", raising=False)
    monkeypatch.delenv("GPSTATION_V1_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("GPSTATION_V1_GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS", raising=False)
    monkeypatch.delenv("GPSTATION_V1_OAUTH_STATE_TTL_SECONDS", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", str(env_file))

    settings = Settings()

    assert settings.port == 8001
    assert settings.public_base_url == "http://localhost:8000/base"
    assert settings.google_id_token_clock_skew_seconds == 12
    assert settings.oauth_state_ttl_seconds == 300


def test_settings_requires_explicit_runtime_values(monkeypatch):
    required_env_names = [line.split("=", 1)[0] for line in REQUIRED_ENV_LINES]
    for name in required_env_names:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)

    assert "db_url" in str(exc.value)
    assert "public_base_url" in str(exc.value)


def strict_settings(**overrides):
    values = {
        "db_url": "postgresql+asyncpg://gpstation:local-secret@127.0.0.1:5432/gpstation_v1",
        "host": "127.0.0.1",
        "port": 8000,
        "reload": False,
        "public_base_url": "http://127.0.0.1:8000",
        "app_base_url": "http://localhost:3000",
        "google_client_id": "local-client-id.apps.googleusercontent.com",
        "google_client_secret": "local-google-client-secret",
        "google_redirect_uri": "http://localhost:8000/web/auth/google/callback",
        "google_id_token_clock_skew_seconds": 10,
        "oauth_state_ttl_seconds": 600,
        "jwt_secret": "local-test-jwt-secret-with-at-least-32-characters",
        "jwt_alg": "HS256",
        "access_ttl_sec": 1200,
        "refresh_ttl_sec": 1209600,
        "cookie_domain": "",
        "secure_cookies": False,
        "cors_origins": "http://localhost:3000,http://127.0.0.1:3000",
    }
    values.update(overrides)
    return Settings(**values)


def test_runtime_settings_validation_allows_localhost_http():
    validate_runtime_settings(strict_settings())


def test_runtime_settings_requires_verified_tls_for_remote_database():
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_settings(
            strict_settings(db_url="postgresql+asyncpg://gpstation:secret@203.0.113.10:5432/gpstation_v1")
        )

    assert "DNS hostname" in str(exc.value)
    assert "sslmode=verify-full" in str(exc.value)

    validate_runtime_settings(
        strict_settings(
            db_url="postgresql+asyncpg://gpstation:secret@db.gpstation.internal:5432/gpstation_v1?sslmode=verify-full"
        )
    )


def test_runtime_settings_requires_explicit_public_bind_opt_in():
    with pytest.raises(RuntimeError, match="GPSTATION_V1_ALLOW_PUBLIC_BIND"):
        validate_runtime_settings(strict_settings(host="0.0.0.0"))

    validate_runtime_settings(strict_settings(host="0.0.0.0", allow_public_bind=True))


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("google_client_id", "", "GPSTATION_V1_GOOGLE_CLIENT_ID is required"),
        ("jwt_secret", "change-this-to-a-long-random-secret", "GPSTATION_V1_JWT_SECRET"),
        ("db_url", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gpstation_v1", "GPSTATION_V1_DB_URL"),
        ("public_base_url", "http://gpstation.example.com", "GPSTATION_V1_PUBLIC_BASE_URL must use https"),
        ("cors_origins", "*", "GPSTATION_V1_CORS_ORIGINS must not include *"),
    ],
)
def test_runtime_settings_validation_rejects_missing_or_unsafe_values(field_name, value, message):
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_settings(strict_settings(**{field_name: value}))

    assert message in str(exc.value)
