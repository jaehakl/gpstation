import pytest

from app.state import RuntimeRegistry, SESSION_LOG_LINE_LIMIT


class DummyWebSocket:
    async def send_json(self, message):
        self.last_message = message


@pytest.mark.asyncio
async def test_runtime_registry_tracks_live_launcher_and_session():
    registry = RuntimeRegistry()
    websocket = DummyWebSocket()

    launcher = await registry.register_launcher("launcher-1", websocket, {"ai": 300})
    session = await registry.register_session("session-1", launcher.id)
    await registry.mark_session_ready(session.id)

    assert (await registry.get_launcher(launcher.id)).websocket is websocket
    assert (await registry.get_session(session.id)).status == "ready"
    assert await registry.get_slave_startup_timeout(launcher.id, "ai") == 300
    assert await registry.get_slave_startup_timeout(launcher.id, "echo") is None


@pytest.mark.asyncio
async def test_runtime_registry_launcher_disconnect_releases_sessions():
    registry = RuntimeRegistry()
    launcher = await registry.register_launcher("launcher-1", DummyWebSocket())
    session = await registry.register_session("session-1", launcher.id)

    affected = await registry.remove_launcher(launcher.id)

    assert [item.id for item in affected] == [session.id]
    assert await registry.get_launcher(launcher.id) is None
    assert await registry.get_session(session.id) is None
    assert session.ready_event.is_set()
    assert session.status == "error"


@pytest.mark.asyncio
async def test_runtime_registry_stores_session_logs_with_limit():
    registry = RuntimeRegistry()

    for index in range(SESSION_LOG_LINE_LIMIT + 2):
        await registry.append_session_log(
            "session-1",
            "stderr",
            f"line-{index}",
            f"2026-07-07T00:00:{index:02d}+00:00",
        )

    items = await registry.get_session_logs("session-1", limit=SESSION_LOG_LINE_LIMIT)

    assert len(items) == SESSION_LOG_LINE_LIMIT
    assert items[0]["line"] == "line-2"
    assert items[-1]["line"] == f"line-{SESSION_LOG_LINE_LIMIT + 1}"


@pytest.mark.asyncio
async def test_runtime_registry_returns_requested_tail_of_session_logs():
    registry = RuntimeRegistry()

    await registry.append_session_log("session-1", "stderr", "first", "2026-07-07T00:00:00+00:00")
    await registry.append_session_log("session-1", "stderr", "second", "2026-07-07T00:00:01+00:00")

    assert await registry.get_session_logs("session-1", limit=1) == [
        {
            "time": "2026-07-07T00:00:01+00:00",
            "stream": "stderr",
            "line": "second",
        }
    ]
