import pytest
from fastapi import HTTPException

from app.auth import authenticate_token
from app.settings import DEMO_USER_ID
from app.state import RuntimeRegistry


class DummyWebSocket:
    async def send_json(self, message):
        self.last_message = message


def test_authenticate_demo_client_token():
    principal = authenticate_token("demo-client-token")

    assert principal.user_id == DEMO_USER_ID
    assert "client" in principal.scopes


def test_authenticate_rejects_unknown_token():
    with pytest.raises(HTTPException):
        authenticate_token("missing")


@pytest.mark.asyncio
async def test_runtime_registry_tracks_live_launcher_and_session():
    registry = RuntimeRegistry()
    websocket = DummyWebSocket()

    launcher = await registry.register_launcher("launcher-1", websocket)
    session = await registry.register_session("session-1", launcher.id)
    await registry.mark_session_ready(session.id)

    assert (await registry.get_launcher(launcher.id)).websocket is websocket
    assert (await registry.get_session(session.id)).status == "ready"


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
