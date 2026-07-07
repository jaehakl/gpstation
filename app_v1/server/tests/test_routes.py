import pytest

from app.main import app
from app.routers.v1 import launchers


def test_launcher_routes_replace_legacy_routes():
    paths = {route.path for route in app.routes}
    legacy_prefix = "/v1/" + "work" + "ers"

    for path in [
        "/web/crud/users/list",
        "/web/crud/users/{row_id}",
        "/web/crud/users/upsert",
        "/web/crud/users/delete",
        "/web/crud/access_keys/list",
        "/web/crud/access_keys/{row_id}",
        "/web/crud/access_keys/delete",
        "/web/crud/launchers/list",
        "/web/crud/launchers/{row_id}",
        "/web/crud/slave_sessions/list",
        "/web/crud/slave_sessions/{row_id}",
        "/web/crud/slave_sessions/delete",
        "/web/auth/google/start",
        "/web/auth/google/callback",
        "/web/auth/me",
        "/web/auth/refresh",
        "/web/auth/logout",
        "/web/users/me/access-tokens",
        "/web/users/{user_id}/access-tokens",
        "/web/slave-sessions/{session_id}/close",
    ]:
        assert path in paths
    assert "/v1/launchers" in paths
    assert "/v1/launchers/control" in paths
    assert "/v1/sessions" in paths
    assert "/crud/users/list" not in paths
    assert "/crud/access_keys/list" not in paths
    assert "/crud/launchers/list" not in paths
    assert "/crud/slave_sessions/list" not in paths
    assert "/crud/{table}/list" not in paths
    assert "/crud/identities/list" not in paths
    assert "/crud/auth_sessions/list" not in paths
    assert "/crud/oauth_states/list" not in paths
    assert "/crud/auth_audit/list" not in paths
    assert "/web/dashboard/summary" not in paths
    assert "/web/users/me" not in paths
    assert "/web/users" not in paths
    assert "/web/users/{user_id}" not in paths
    assert "/web/users/{user_id}/access-tokens/{access_key_id}" not in paths
    assert "/web/launchers" not in paths
    assert "/web/launchers/{launcher_id}" not in paths
    assert "/web/slave-sessions" not in paths
    assert "/web/slave-sessions/{session_id}" not in paths
    assert "/docs" not in paths
    assert "/openapi.json" not in paths
    assert "/redoc" not in paths
    assert legacy_prefix not in paths
    assert f"{legacy_prefix}/control" not in paths


@pytest.mark.asyncio
async def test_v1_cors_allows_any_browser_origin():
    status, headers = await call_asgi(
        "OPTIONS",
        "/v1/launchers",
        {
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert status == 200
    assert headers["access-control-allow-origin"] == "*"
    assert headers["access-control-allow-headers"] == "authorization,content-type"
    assert "access-control-allow-credentials" not in headers

    status, headers = await call_asgi("GET", "/v1/not-found", {"Origin": "https://master.example"})

    assert status == 404
    assert headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in headers


@pytest.mark.asyncio
async def test_cookie_backed_routes_do_not_allow_unknown_cors_origin():
    status, headers = await call_asgi(
        "OPTIONS",
        "/web/crud/users/list",
        {
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert status == 400
    assert headers.get("access-control-allow-origin") != "*"


@pytest.mark.asyncio
async def test_session_ready_commits_db_before_waking_runtime(monkeypatch):
    calls = []

    async def mark_db_ready(db, session_id):
        calls.append(("db", db, session_id))

    async def mark_runtime_ready(session_id):
        calls.append(("runtime", session_id))

    monkeypatch.setattr(launchers.SessionService, "mark_session_ready", mark_db_ready)
    monkeypatch.setattr(launchers.runtime, "mark_session_ready", mark_runtime_ready)

    db = object()

    await launchers.handle_launcher_message(
        db,
        "launcher-1",
        object(),
        {"type": "session.ready", "session_id": "session-1"},
    )

    assert calls == [
        ("db", db, "session-1"),
        ("runtime", "session-1"),
    ]


async def call_asgi(method: str, path: str, headers: dict[str, str]) -> tuple[int, dict[str, str]]:
    messages = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [(name.lower().encode("latin-1"), value.encode("latin-1")) for name, value in headers.items()],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    response_headers = {
        name.decode("latin-1").lower(): value.decode("latin-1")
        for name, value in start.get("headers", [])
    }
    return start["status"], response_headers
