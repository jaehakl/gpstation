from datetime import datetime, timezone
import uuid

import pytest

from app.db import Launcher, SlaveSession
from app.service.launcher_service import LauncherService, launcher_to_view


class FakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = str(uuid.uuid4())
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        return None


class FakeScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeExecuteResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return FakeScalarRows(self.rows)


class FakeReconcileDb:
    def __init__(self, launchers, sessions):
        self.launchers = launchers
        self.sessions = sessions
        self.execute_count = 0
        self.commits = 0

    async def execute(self, _stmt):
        self.execute_count += 1
        if self.execute_count == 1:
            return FakeExecuteResult(self.launchers)
        return FakeExecuteResult(self.sessions)

    async def commit(self):
        self.commits += 1


def make_launcher():
    return Launcher(
        id="launcher-1",
        user_id="user-1",
        launcher_name="desktop",
        ip_address="10.0.0.5",
        status="ready",
        slave_app_ids=["echo", "render"],
        active_session_ids=["session-1"],
        connected_at=datetime.now(timezone.utc),
        last_heartbeat_at=datetime.now(timezone.utc),
    )


def make_session(session_id="session-1", launcher_id="launcher-1", status="ready"):
    return SlaveSession(
        id=session_id,
        user_id="user-1",
        launcher_id=launcher_id,
        slave_app_id="echo",
        session_token_hash="hash",
        status=status,
        ttl_seconds=300,
        expires_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_connected_launcher_stores_ip_and_deduped_slave_app_ids():
    db = FakeDb()

    launcher = await LauncherService.create_connected_launcher(
        db,
        user_id="user-1",
        launcher_name="desktop",
        slave_app_ids=["echo", "echo", "render"],
        ip_address="10.0.0.5",
    )

    assert launcher.ip_address == "10.0.0.5"
    assert launcher.slave_app_ids == ["echo", "render"]
    assert db.added == [launcher]
    assert db.commits == 1


def test_launcher_to_view_uses_launcher_slave_app_ids():
    view = launcher_to_view(make_launcher())

    assert view.slave_app_ids == ["echo", "render"]
    assert view.active_session_count == 1


@pytest.mark.asyncio
async def test_reconcile_disconnected_launchers_updates_only_missing_owned_runtime_launchers():
    stale = make_launcher()
    stale.id = "stale-launcher"
    stale.status = "busy"
    stale.active_session_ids = ["session-1"]
    connected = make_launcher()
    connected.id = "connected-launcher"
    other_user = make_launcher()
    other_user.id = "other-user-launcher"
    other_user.user_id = "user-2"
    already_closed = make_launcher()
    already_closed.id = "closed-launcher"
    already_closed.status = "disconnected"
    already_closed.disconnected_at = datetime.now(timezone.utc)

    active_session = make_session("session-1", "stale-launcher")
    connected_session = make_session("session-2", "connected-launcher")
    db = FakeReconcileDb(
        [stale, connected, other_user, already_closed],
        [active_session, connected_session],
    )

    launchers, sessions = await LauncherService.reconcile_disconnected_launchers(
        db,
        connected_launcher_ids={"connected-launcher"},
        user_id="user-1",
    )

    assert (launchers, sessions) == (1, 1)
    assert stale.status == "disconnected"
    assert stale.active_session_ids == []
    assert stale.disconnected_at is not None
    assert active_session.status == "error"
    assert active_session.closed_at is not None
    assert active_session.last_error == "launcher disconnected"
    assert connected.status == "ready"
    assert connected_session.status == "ready"
    assert other_user.status == "ready"
    assert db.commits == 1
