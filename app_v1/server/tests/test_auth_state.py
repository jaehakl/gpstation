import asyncio

import pytest
from fastapi import HTTPException

from gpstation_server.auth import authenticate_token
from gpstation_server.state import RuntimeState


class DummyWebSocket:
    async def send_json(self, message):
        self.last_message = message


def test_authenticate_demo_client_token():
    principal = authenticate_token("demo-client-token")

    assert principal.user_id == "demo-user"
    assert "client" in principal.scopes


def test_authenticate_rejects_unknown_token():
    with pytest.raises(HTTPException):
        authenticate_token("missing")


@pytest.mark.asyncio
async def test_session_requires_owned_worker():
    state = RuntimeState()
    worker = await state.register_worker(
        user_id="user-a",
        worker_name="test",
        capabilities=["echo"],
        websocket=DummyWebSocket(),
    )

    session = await state.create_session(
        user_id="user-a",
        worker_session_id=worker.id,
        ttl_seconds=60,
    )

    assert session.worker_session_id == worker.id
    with pytest.raises(KeyError):
        await state.create_session(
            user_id="user-b",
            worker_session_id=worker.id,
            ttl_seconds=60,
        )


@pytest.mark.asyncio
async def test_expired_session_cleanup_closes_session():
    state = RuntimeState()
    worker = await state.register_worker(
        user_id="user-a",
        worker_name="test",
        capabilities=["echo"],
        websocket=DummyWebSocket(),
    )
    session = await state.create_session(
        user_id="user-a",
        worker_session_id=worker.id,
        ttl_seconds=10,
    )
    session.expires_at = session.created_at

    closed = await state.collect_expired_sessions()

    assert [item.id for item in closed] == [session.id]
    assert await state.get_session(session.id) is None
