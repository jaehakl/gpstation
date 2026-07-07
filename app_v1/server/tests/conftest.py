import os


TEST_ENV = {
    "GPSTATION_V1_DB_URL": "postgresql+asyncpg://gpstation:test-secret@127.0.0.1:5432/gpstation_v1_test",
    "GPSTATION_V1_HOST": "127.0.0.1",
    "GPSTATION_V1_PORT": "8000",
    "GPSTATION_V1_RELOAD": "false",
    "GPSTATION_V1_PUBLIC_BASE_URL": "http://127.0.0.1:8000",
    "GPSTATION_V1_APP_BASE_URL": "http://localhost:3000",
    "GPSTATION_V1_GOOGLE_CLIENT_ID": "local-client-id.apps.googleusercontent.com",
    "GPSTATION_V1_GOOGLE_CLIENT_SECRET": "local-google-client-secret",
    "GPSTATION_V1_GOOGLE_REDIRECT_URI": "http://localhost:8000/web/auth/google/callback",
    "GPSTATION_V1_GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS": "10",
    "GPSTATION_V1_OAUTH_STATE_TTL_SECONDS": "600",
    "GPSTATION_V1_JWT_SECRET": "local-test-jwt-secret-with-at-least-32-characters",
    "GPSTATION_V1_JWT_ALG": "HS256",
    "GPSTATION_V1_ACCESS_TTL_SEC": "1200",
    "GPSTATION_V1_REFRESH_TTL_SEC": "1209600",
    "GPSTATION_V1_COOKIE_DOMAIN": "",
    "GPSTATION_V1_SECURE_COOKIES": "false",
    "GPSTATION_V1_SESSION_TTL_SECONDS": "300",
    "GPSTATION_V1_SESSION_READY_TIMEOUT_SECONDS": "10",
    "GPSTATION_V1_CLEANUP_INTERVAL_SECONDS": "5",
    "GPSTATION_V1_CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
}

for name, value in TEST_ENV.items():
    os.environ.setdefault(name, value)
