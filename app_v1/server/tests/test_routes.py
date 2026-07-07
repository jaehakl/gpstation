from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import Principal
from app.main import app
from app.models import UserData
from app.routers.v1 import jobs, launchers, sessions
from app.routers.web import launchers as web_launchers, slave_sessions
from app.state import RuntimeRegistry


class FakeDb:
    def __init__(self, session):
        self.session = session

    async def scalar(self, stmt):
        self.last_stmt = stmt
        return self.session


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
        "/web/launchers/reconcile-disconnected",
        "/web/launchers/runtime",
        "/web/launchers/{launcher_id}/cancel-current-job",
        "/web/launchers/{launcher_id}/reset-worker",
        "/web/jobs",
        "/web/jobs/{job_id}/kill",
        "/web/auth/google/start",
        "/web/auth/google/callback",
        "/web/auth/me",
        "/web/auth/refresh",
        "/web/auth/logout",
        "/web/users/me/access-tokens",
        "/web/users/{user_id}/access-tokens",
        "/web/slave-sessions/{session_id}/close",
        "/web/slave-sessions/{session_id}/logs",
    ]:
        assert path in paths
    assert "/v1/launchers" in paths
    assert "/v1/launchers/control" in paths
    assert "/v1/sessions" in paths
    assert "/v1/sessions/{session_id}/logs" in paths
    assert "/v1/jobs" in paths
    assert "/v1/jobs/{job_id}" in paths
    assert "/v1/jobs/{job_id}/logs" in paths
    assert "/v1/jobs/{job_id}/wait-answer" in paths
    assert "/v1/jobs/{job_id}/kill" in paths
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
async def test_dispatch_queued_jobs_sends_job_start_without_input(monkeypatch):
    job = SimpleNamespace(
        id="job-1",
        user_id="user-1",
        handler_type="ai.llm",
        slave_app_id="ai",
        offer={"type": "offer", "sdp": "v=0\r\n"},
    )
    launcher = SimpleNamespace(id="launcher-1")
    sent_messages = []
    marked_jobs = []
    selected = {"count": 0}

    async def select_next_queued_job(db, *, user_id=None):
        selected["count"] += 1
        return job if selected["count"] == 1 else None

    async def select_idle_launcher_for_job(db, *, job, idle_launcher_ids):
        return launcher

    async def assign_job(db, *, job, launcher):
        return job

    async def idle_launcher_ids():
        return {"launcher-1"}

    async def mark_launcher_job(*args, **kwargs):
        marked_jobs.append((args, kwargs))

    async def send_to_launcher(launcher_id, message):
        sent_messages.append((launcher_id, message))

    monkeypatch.setattr(jobs.JobService, "select_next_queued_job", select_next_queued_job)
    monkeypatch.setattr(jobs.JobService, "select_idle_launcher_for_job", select_idle_launcher_for_job)
    monkeypatch.setattr(jobs.JobService, "assign_job", assign_job)
    monkeypatch.setattr(jobs.runtime, "idle_launcher_ids", idle_launcher_ids)
    monkeypatch.setattr(jobs.runtime, "mark_launcher_job", mark_launcher_job)
    monkeypatch.setattr(jobs, "send_to_launcher", send_to_launcher)

    await jobs.dispatch_queued_jobs(object(), user_id="user-1")

    assert sent_messages == [
        (
            "launcher-1",
            {
                "type": "job.start",
                "job_id": "job-1",
                "handler_type": "ai.llm",
                "slave_app_id": "ai",
                "offer": {"type": "offer", "sdp": "v=0\r\n"},
            },
        )
    ]
    assert "input" not in sent_messages[0][1]
    assert marked_jobs


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


@pytest.mark.asyncio
async def test_launcher_session_log_message_is_stored(monkeypatch):
    registry = RuntimeRegistry()
    monkeypatch.setattr(launchers, "runtime", registry)

    await launchers.handle_launcher_message(
        object(),
        "launcher-1",
        object(),
        {
            "type": "session.log",
            "session_id": "session-1",
            "time": "2026-07-07T00:00:00+00:00",
            "stream": "stderr",
            "line": "loading model",
        },
    )

    assert await registry.get_session_logs("session-1") == [
        {
            "time": "2026-07-07T00:00:00+00:00",
            "stream": "stderr",
            "line": "loading model",
        }
    ]


def test_extract_slave_startup_timeouts_ignores_invalid_values():
    assert launchers.extract_slave_startup_timeouts(
        {
            "slave_apps": {
                "ai": {"startup_timeout_seconds": 300},
                "echo": {},
                "bad": {"startup_timeout_seconds": "not-a-number"},
                "zero": {"startup_timeout_seconds": 0},
            }
        }
    ) == {"ai": 300}


@pytest.mark.asyncio
async def test_session_ready_timeout_uses_runtime_slave_timeout(monkeypatch):
    registry = RuntimeRegistry()
    await registry.register_launcher("launcher-1", object(), {"ai": 300})
    monkeypatch.setattr(sessions, "runtime", registry)
    monkeypatch.setattr(sessions.settings, "session_ready_timeout_seconds", 10)

    assert await sessions.resolve_session_ready_timeout_seconds("launcher-1", "ai") == 300
    assert await sessions.resolve_session_ready_timeout_seconds("launcher-1", "echo") == 10


@pytest.mark.asyncio
async def test_v1_session_logs_requires_session_owner(monkeypatch):
    registry = RuntimeRegistry()
    await registry.append_session_log("session-1", "stderr", "owned log", "2026-07-07T00:00:00+00:00")
    monkeypatch.setattr(sessions, "runtime", registry)

    response = await sessions.get_session_logs(
        "session-1",
        limit=10,
        principal=Principal(token="token", user_id="user-1", scopes=frozenset({"client"})),
        db=FakeDb(object()),
    )

    assert response.items[0].line == "owned log"

    with pytest.raises(HTTPException) as error:
        await sessions.get_session_logs(
            "session-1",
            limit=10,
            principal=Principal(token="token", user_id="other-user", scopes=frozenset({"client"})),
            db=FakeDb(None),
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_v1_job_logs_requires_job_owner(monkeypatch):
    registry = RuntimeRegistry()
    await registry.append_session_log("job-1", "stderr", "job log", "2026-07-07T00:00:00+00:00")
    monkeypatch.setattr(jobs, "runtime", registry)

    response = await jobs.get_job_logs(
        "job-1",
        limit=10,
        principal=Principal(token="token", user_id="user-1", scopes=frozenset({"client"})),
        db=FakeDb(object()),
    )

    assert response.items[0].line == "job log"

    with pytest.raises(HTTPException) as error:
        await jobs.get_job_logs(
            "job-1",
            limit=10,
            principal=Principal(token="token", user_id="other-user", scopes=frozenset({"client"})),
            db=FakeDb(None),
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_web_session_logs_allows_admin_or_owner(monkeypatch):
    registry = RuntimeRegistry()
    await registry.append_session_log("session-1", "stderr", "web log", "2026-07-07T00:00:00+00:00")
    monkeypatch.setattr(slave_sessions, "runtime", registry)

    response = await slave_sessions.api_get_slave_session_logs(
        "session-1",
        limit=10,
        db=FakeDb(object()),
        current_user=UserData(id="user-1", role="user"),
    )

    assert response.items[0].line == "web log"

    admin_response = await slave_sessions.api_get_slave_session_logs(
        "session-1",
        limit=10,
        db=FakeDb(object()),
        current_user=UserData(id="admin-1", role="admin"),
    )

    assert admin_response.items[0].line == "web log"

    with pytest.raises(HTTPException) as error:
        await slave_sessions.api_get_slave_session_logs(
            "session-1",
            limit=10,
            db=FakeDb(None),
            current_user=UserData(id="other-user", role="user"),
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_web_reconcile_disconnected_launchers_uses_runtime_and_user_scope(monkeypatch):
    registry = RuntimeRegistry()
    await registry.register_launcher("connected-launcher", object())
    monkeypatch.setattr(web_launchers, "runtime", registry)

    calls = []

    async def reconcile(db, *, connected_launcher_ids, user_id):
        calls.append((db, connected_launcher_ids, user_id))
        return 2, 3

    monkeypatch.setattr(web_launchers.LauncherService, "reconcile_disconnected_launchers", reconcile)
    db = object()

    user_response = await web_launchers.api_reconcile_disconnected_launchers(
        db=db,
        current_user=UserData(id="user-1", role="user", roles=["user"]),
    )
    admin_response = await web_launchers.api_reconcile_disconnected_launchers(
        db=db,
        current_user=UserData(id="admin-1", role="admin", roles=["admin"]),
    )

    assert user_response.launchers == 2
    assert user_response.slave_sessions == 3
    assert admin_response.launchers == 2
    assert admin_response.slave_sessions == 3
    assert calls == [
        (db, {"connected-launcher"}, "user-1"),
        (db, {"connected-launcher"}, None),
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
