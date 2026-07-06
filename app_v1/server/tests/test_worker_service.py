from datetime import datetime, timezone
import uuid

import pytest

from app.db import Worker
from app.service.worker_service import WorkerService, worker_to_view


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


def make_worker():
    return Worker(
        id="worker-1",
        user_id="user-1",
        worker_name="desktop",
        ip_address="10.0.0.5",
        status="ready",
        slave_app_ids=["echo", "render"],
        active_session_ids=["session-1"],
        connected_at=datetime.now(timezone.utc),
        last_heartbeat_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_connected_worker_stores_ip_and_deduped_slave_app_ids():
    db = FakeDb()

    worker = await WorkerService.create_connected_worker(
        db,
        user_id="user-1",
        worker_name="desktop",
        slave_app_ids=["echo", "echo", "render"],
        ip_address="10.0.0.5",
    )

    assert worker.ip_address == "10.0.0.5"
    assert worker.slave_app_ids == ["echo", "render"]
    assert db.added == [worker]
    assert db.commits == 1


def test_worker_to_view_uses_worker_slave_app_ids():
    view = worker_to_view(make_worker())

    assert view.slave_app_ids == ["echo", "render"]
    assert view.active_session_count == 1
