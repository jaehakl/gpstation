import pytest

from app.main import app
from app.routers.v1 import launchers


def test_launcher_routes_replace_legacy_routes():
    paths = {route.path for route in app.routes}
    legacy_prefix = "/v1/" + "work" + "ers"

    for path in [
        "/crud/users/list",
        "/crud/users/{row_id}",
        "/crud/users/upsert",
        "/crud/users/delete",
        "/crud/access_keys/list",
        "/crud/access_keys/{row_id}",
        "/crud/access_keys/delete",
        "/crud/launchers/list",
        "/crud/launchers/{row_id}",
        "/crud/slave_sessions/list",
        "/crud/slave_sessions/{row_id}",
        "/crud/slave_sessions/delete",
        "/web/auth/google/start",
        "/web/auth/google/callback",
        "/web/auth/me",
        "/web/auth/refresh",
        "/web/auth/logout",
        "/web/dashboard/summary",
        "/web/users/me",
        "/web/users",
        "/web/users/me/access-tokens",
        "/web/launchers",
        "/web/slave-sessions",
    ]:
        assert path in paths
    assert "/v1/launchers" in paths
    assert "/v1/launchers/control" in paths
    assert "/v1/sessions" in paths
    assert "/crud/{table}/list" not in paths
    assert "/crud/identities/list" not in paths
    assert "/crud/auth_sessions/list" not in paths
    assert "/crud/oauth_states/list" not in paths
    assert "/crud/auth_audit/list" not in paths
    assert "/docs" not in paths
    assert "/openapi.json" not in paths
    assert "/redoc" not in paths
    assert legacy_prefix not in paths
    assert f"{legacy_prefix}/control" not in paths


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
