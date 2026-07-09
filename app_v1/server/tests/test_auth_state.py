import pytest

from app.state import RuntimeRegistry


class DummyWebSocket:
    async def send_json(self, message):
        self.last_message = message


@pytest.mark.asyncio
async def test_runtime_registry_tracks_live_launcher_and_worker_state():
    registry = RuntimeRegistry()
    websocket = DummyWebSocket()

    launcher = await registry.register_launcher("launcher-1", websocket, {"ai": 300})
    await registry.mark_heartbeat(
        launcher.id,
        current_job_id="job-1",
        loaded_slave_app_id="ai",
        worker_status="busy",
        metadata={"gpu": "RTX"},
    )

    assert (await registry.get_launcher(launcher.id)).websocket is websocket
    assert await registry.get_slave_startup_timeout(launcher.id, "ai") == 300
    assert await registry.get_slave_startup_timeout(launcher.id, "missing") is None
    assert await registry.idle_launcher_ids() == set()
    assert await registry.launcher_snapshots() == {
        "launcher-1": {
            "current_job_id": "job-1",
            "loaded_slave_app_id": "ai",
            "worker_status": "busy",
            "metadata": {"gpu": "RTX"},
        }
    }


@pytest.mark.asyncio
async def test_runtime_registry_launcher_disconnect_removes_launcher():
    registry = RuntimeRegistry()
    launcher = await registry.register_launcher("launcher-1", DummyWebSocket())

    await registry.remove_launcher(launcher.id)

    assert await registry.get_launcher(launcher.id) is None
    assert await registry.get_launcher_ids() == set()

