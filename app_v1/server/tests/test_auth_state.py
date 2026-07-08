import pytest

from app.state import JOB_LOG_LINE_LIMIT, RuntimeRegistry


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


@pytest.mark.asyncio
async def test_runtime_registry_stores_job_logs_with_limit():
    registry = RuntimeRegistry()

    for index in range(JOB_LOG_LINE_LIMIT + 2):
        await registry.append_job_log(
            "job-1",
            "stderr",
            f"line-{index}",
            f"2026-07-07T00:00:{index:02d}+00:00",
        )

    items = await registry.get_job_logs("job-1", limit=JOB_LOG_LINE_LIMIT)

    assert len(items) == JOB_LOG_LINE_LIMIT
    assert items[0]["line"] == "line-2"
    assert items[-1]["line"] == f"line-{JOB_LOG_LINE_LIMIT + 1}"


@pytest.mark.asyncio
async def test_runtime_registry_returns_requested_tail_of_job_logs():
    registry = RuntimeRegistry()

    await registry.append_job_log("job-1", "stderr", "first", "2026-07-07T00:00:00+00:00")
    await registry.append_job_log("job-1", "stderr", "second", "2026-07-07T00:00:01+00:00")

    assert await registry.get_job_logs("job-1", limit=1) == [
        {
            "time": "2026-07-07T00:00:01+00:00",
            "stream": "stderr",
            "line": "second",
        }
    ]
