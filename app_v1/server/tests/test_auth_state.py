import pytest

from app.state import RuntimeRegistry


class DummyWebSocket:
    def __init__(self):
        self.close_code = None

    async def send_json(self, message):
        self.last_message = message

    async def close(self, *, code):
        self.close_code = code


@pytest.mark.asyncio
async def test_runtime_registry_tracks_live_launcher_and_worker_state():
    registry = RuntimeRegistry()
    websocket = DummyWebSocket()

    launcher = await registry.register_launcher(
        "launcher-1",
        websocket,
        {"ai": 300},
        access_key_id="key-1",
    )
    await registry.mark_launcher_job(launcher.id, "job-1", worker_status="assigned")
    await registry.mark_heartbeat(
        launcher.id,
        current_job_id="untrusted-heartbeat-job",
        loaded_slave_app_id="ai",
        worker_status="busy",
        metadata={"gpu": "RTX"},
    )

    assert (await registry.get_launcher(launcher.id)).websocket is websocket
    assert await registry.get_slave_startup_timeout(launcher.id, "ai") == 300
    assert await registry.get_slave_startup_timeout(launcher.id, "missing") is None
    assert await registry.idle_launcher_ids() == set()
    assert (await registry.get_launcher(launcher.id)).access_key_id == "key-1"
    assert await registry.launcher_snapshots() == {
        "launcher-1": {
            "current_job_id": "job-1",
            "loaded_slave_app_id": "ai",
            "worker_status": "busy",
            "resetting": False,
            "metadata": {"gpu": "RTX"},
        }
    }

    assert await registry.close_launchers_for_access_key("key-1") == 1
    assert websocket.close_code == 1008
    assert await registry.get_launcher("launcher-1") is None


@pytest.mark.asyncio
async def test_runtime_registry_launcher_disconnect_removes_launcher():
    registry = RuntimeRegistry()
    launcher = await registry.register_launcher("launcher-1", DummyWebSocket())

    await registry.remove_launcher(launcher.id)

    assert await registry.get_launcher(launcher.id) is None
    assert await registry.get_launcher_ids() == set()


@pytest.mark.asyncio
async def test_resetting_launcher_is_not_idle_until_reset_done():
    registry = RuntimeRegistry()
    await registry.register_launcher("launcher-1", DummyWebSocket())

    assert await registry.mark_launcher_resetting("launcher-1") is not None
    assert await registry.mark_launcher_resetting("launcher-1") is None
    assert await registry.idle_launcher_ids() == set()

    await registry.clear_launcher_worker("launcher-1")
    assert await registry.idle_launcher_ids() == {"launcher-1"}


@pytest.mark.asyncio
async def test_runtime_registry_wakes_all_job_waiters_and_releases_event():
    registry = RuntimeRegistry()
    first = await registry.prepare_job_wait("job-1")
    second = await registry.prepare_job_wait("job-1")

    assert first is second
    await registry.set_job_event("job-1")
    await registry.wait_prepared_job_event("job-1", first, 1)
    await registry.wait_prepared_job_event("job-1", second, 1)

    assert registry.job_events == {}
    assert registry.job_event_waiters == {}


@pytest.mark.asyncio
async def test_runtime_registry_throttles_db_heartbeat_and_key_revalidation():
    registry = RuntimeRegistry()
    launcher = await registry.register_launcher("launcher-1", DummyWebSocket())

    assert await registry.heartbeat_actions(launcher.id, "ready") == (False, False)
    assert await registry.heartbeat_actions(launcher.id, "busy") == (True, False)

    launcher.last_db_heartbeat_at -= 31
    launcher.last_access_key_check_at -= 31
    assert await registry.heartbeat_actions(launcher.id, "busy") == (True, True)
