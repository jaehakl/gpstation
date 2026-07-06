from datetime import datetime, timedelta, timezone
import uuid

import pytest

from app.db import SlaveSession, Launcher
from app.service.session_service import SessionService
from app.user_auth.utils.auth_utils import hash_token


class FakeDb:
    def __init__(self, launcher=None, session=None):
        self.launcher = launcher
        self.session = session
        self.added = []
        self.commits = 0

    async def get(self, model, object_id):
        if model is Launcher and self.launcher is not None and self.launcher.id == object_id:
            return self.launcher
        if model is SlaveSession and self.session is not None and self.session.id == object_id:
            return self.session
        return None

    def add(self, obj):
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = str(uuid.uuid4())
        self.added.append(obj)
        if isinstance(obj, SlaveSession):
            self.session = obj

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        return None


def make_launcher(user_id="user-1", status="ready"):
    return Launcher(
        id="launcher-1",
        user_id=user_id,
        launcher_name="desktop",
        ip_address="127.0.0.1",
        status=status,
        slave_app_ids=["echo"],
        active_session_ids=[],
        connected_at=datetime.now(timezone.utc),
        last_heartbeat_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_session_requires_owned_launcher():
    db = FakeDb(launcher=make_launcher(user_id="other-user"))

    with pytest.raises(KeyError):
        await SessionService.create_session(
            db,
            user_id="user-1",
            launcher_id="launcher-1",
            slave_app_id="echo",
            ttl_seconds=60,
            master_ip_address=None,
            master_user_agent=None,
        )


@pytest.mark.asyncio
async def test_create_session_requires_advertised_slave():
    db = FakeDb(launcher=make_launcher())

    with pytest.raises(ValueError):
        await SessionService.create_session(
            db,
            user_id="user-1",
            launcher_id="launcher-1",
            slave_app_id="missing",
            ttl_seconds=60,
            master_ip_address=None,
            master_user_agent=None,
        )


@pytest.mark.asyncio
async def test_create_session_hashes_token_and_marks_launcher_busy():
    launcher = make_launcher()
    db = FakeDb(launcher=launcher)

    session, token = await SessionService.create_session(
        db,
        user_id="user-1",
        launcher_id="launcher-1",
        slave_app_id="echo",
        ttl_seconds=60,
        master_ip_address="127.0.0.1",
        master_user_agent="pytest",
    )

    assert session.session_token_hash == hash_token(token)
    assert session.master_ip_address == "127.0.0.1"
    assert session.master_user_agent == "pytest"
    assert launcher.status == "busy"
    assert launcher.active_session_ids == [session.id]
    assert any(isinstance(item, SlaveSession) for item in db.added)


@pytest.mark.asyncio
async def test_verify_session_token_checks_hash_and_status():
    session = SlaveSession(
        id="session-1",
        user_id="user-1",
        launcher_id="launcher-1",
        slave_app_id="echo",
        session_token_hash=hash_token("secret"),
        status="ready",
        ttl_seconds=60,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    db = FakeDb(session=session)

    assert await SessionService.verify_session_token(db, "session-1", "wrong") is None
    assert await SessionService.verify_session_token(db, "session-1", "secret") is session


@pytest.mark.asyncio
async def test_close_session_clears_launcher_active_session():
    launcher = make_launcher(status="busy")
    launcher.active_session_ids = ["session-1"]
    session = SlaveSession(
        id="session-1",
        user_id="user-1",
        launcher_id="launcher-1",
        slave_app_id="echo",
        session_token_hash=hash_token("secret"),
        status="ready",
        ttl_seconds=60,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    db = FakeDb(launcher=launcher, session=session)

    await SessionService.close_session(db, "session-1", "done")

    assert session.status == "closed"
    assert launcher.active_session_ids == []
    assert launcher.status == "ready"
