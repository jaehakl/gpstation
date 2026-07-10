from datetime import datetime, timezone
import uuid

import pytest

from app.db import Launcher
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
    def __init__(self, launchers):
        self.launchers = launchers
        self.commits = 0

    async def execute(self, _stmt):
        return FakeExecuteResult(self.launchers)

    async def commit(self):
        self.commits += 1


def make_launcher():
    return Launcher(
        id="launcher-1",
        user_id="user-1",
        launcher_name="desktop",
        ip_address="10.0.0.5",
        status="ready",
        slave_app_ids=["ai", "render"],
        connected_at=datetime.now(timezone.utc),
        last_heartbeat_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_connected_launcher_stores_ip_and_deduped_slave_app_ids():
    db = FakeDb()

    launcher = await LauncherService.create_connected_launcher(
        db,
        user_id="user-1",
        launcher_name="desktop",
        slave_app_ids=["ai", "ai", "render"],
        ip_address="10.0.0.5",
    )

    assert launcher.ip_address == "10.0.0.5"
    assert launcher.slave_app_ids == ["ai", "render"]
    assert db.added == [launcher]
    assert db.commits == 1


def test_launcher_to_view_uses_launcher_slave_app_ids():
    view = launcher_to_view(make_launcher())

    assert view.slave_app_ids == ["ai", "render"]


@pytest.mark.asyncio
async def test_find_disconnected_launcher_ids_scopes_missing_runtime_launchers():
    stale = make_launcher()
    stale.id = "stale-launcher"
    stale.status = "busy"
    connected = make_launcher()
    connected.id = "connected-launcher"
    other_user = make_launcher()
    other_user.id = "other-user-launcher"
    other_user.user_id = "user-2"
    already_closed = make_launcher()
    already_closed.id = "closed-launcher"
    already_closed.status = "disconnected"
    already_closed.disconnected_at = datetime.now(timezone.utc)

    db = FakeReconcileDb([stale.id])

    launcher_ids = await LauncherService.find_disconnected_launcher_ids(
        db,
        connected_launcher_ids={"connected-launcher"},
        user_id="user-1",
    )

    assert launcher_ids == ["stale-launcher"]
    assert db.commits == 0
