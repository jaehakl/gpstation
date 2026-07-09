from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers.web import auth as web_auth
from app.routers.web.auth import can_authenticate_user, get_active_auth_session, resolve_oauth_user, validate_oauth_state_values
from app.user_auth.db import Identity, OAuthProvider, OAuthState, Session as AuthSession, User
from app.user_auth.utils.auth_utils import hash_token
from app.user_auth.utils.jwt import make_access, make_refresh, verify_token


class FakeOAuthDb:
    def __init__(self, scalar_result=None):
        self.scalar_result = scalar_result
        self.added = []
        self.flushes = 0

    async def scalar(self, _stmt):
        return self.scalar_result

    async def get(self, model, object_id):
        if isinstance(self.scalar_result, Identity) and model is User:
            return User(id=object_id, email="linked@example.test", role="user", status="active")
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1
        for obj in self.added:
            if isinstance(obj, User) and obj.id is None:
                obj.id = "oauth-user-1"


class FakeSessionDb:
    def __init__(self, session):
        self.session = session

    async def scalar(self, _stmt):
        return self.session


class FakeRefreshDb:
    def __init__(self, session, user):
        self.session = session
        self.user = user
        self.commits = 0

    async def scalar(self, _stmt):
        return self.session

    async def get(self, model, _object_id):
        if model is User:
            return self.user
        return None

    async def commit(self):
        self.commits += 1


def test_jwt_access_and_refresh_round_trip():
    user = User(id="user-1", email="user@example.test", role="admin", status="active")

    access = verify_token(make_access(user))
    refresh = verify_token(make_refresh("user-1", "session-1"))

    assert access["sub"] == "user-1"
    assert access["role"] == "admin"
    assert refresh["typ"] == "refresh"
    assert refresh["sid"] == "session-1"


@pytest.mark.asyncio
async def test_oauth_signup_creates_unauthorized_user_and_identity():
    db = FakeOAuthDb()

    user = await resolve_oauth_user(
        db,
        {
            "sub": "google-user-1",
            "email": "new@example.test",
            "email_verified": True,
            "name": "New User",
        },
    )

    assert user.role == "unauthorized"
    assert user.status == "active"
    assert user.email == "new@example.test"
    assert any(isinstance(item, Identity) for item in db.added)


def test_unauthorized_oauth_user_cannot_authenticate():
    user = User(id="user-1", email="user@example.test", role="unauthorized", status="active")

    assert can_authenticate_user(user) is False


def test_oauth_state_requires_matching_cookie_and_unconsumed_state():
    oauth_state = OAuthState(
        provider=OAuthProvider.google,
        state="state-1",
        created_at=datetime.now(timezone.utc),
    )

    validate_oauth_state_values("state-1", "state-1", oauth_state)

    with pytest.raises(HTTPException) as mismatch:
        validate_oauth_state_values("state-1", "other", oauth_state)
    assert mismatch.value.status_code == 400

    oauth_state.consumed_at = datetime.now(timezone.utc)
    with pytest.raises(HTTPException) as reused:
        validate_oauth_state_values("state-1", "state-1", oauth_state)
    assert reused.value.status_code == 400


def test_oauth_state_expires(monkeypatch):
    monkeypatch.setattr(web_auth.settings, "oauth_state_ttl_seconds", 60)
    oauth_state = OAuthState(
        provider=OAuthProvider.google,
        state="state-1",
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(HTTPException) as expired:
        validate_oauth_state_values("state-1", "state-1", oauth_state)
    assert expired.value.status_code == 400


def test_return_to_is_limited_to_app_origin(monkeypatch):
    monkeypatch.setattr(web_auth.settings, "app_base_url", "http://localhost:3000")

    assert web_auth.sanitize_return_to("/users") == "http://localhost:3000/users"
    assert web_auth.sanitize_return_to("http://localhost:3000/users") == "http://localhost:3000/users"
    assert web_auth.sanitize_return_to("https://evil.example/users") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_revoked_refresh_session_is_not_active():
    active = AuthSession(
        id="session-row-1",
        user_id="user-1",
        session_id_hash=hash_token("session-1"),
        created_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    revoked = AuthSession(
        id="session-row-2",
        user_id="user-1",
        session_id_hash=hash_token("session-2"),
        created_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        revoked_at=datetime.now(timezone.utc),
    )

    assert await get_active_auth_session(FakeSessionDb(active), "session-1") is active
    assert await get_active_auth_session(FakeSessionDb(revoked), "session-2") is None


@pytest.mark.asyncio
async def test_csrf_token_is_bound_to_refresh_session():
    user = User(id="user-1", email="user@example.test", role="user", status="active")
    auth_session = AuthSession(
        id="session-row-1",
        user_id="user-1",
        session_id_hash=hash_token("session-1"),
        created_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    refresh = make_refresh("user-1", "session-1")

    response = await web_auth.csrf_token(make_request({"refresh_token": refresh}), FakeRefreshDb(auth_session, user))
    csrf_token = response["csrf_token"]

    web_auth.validate_csrf_request(
        make_request(
            {"refresh_token": refresh},
            {"x-csrf-token": csrf_token},
        )
    )

    with pytest.raises(HTTPException) as mismatch:
        web_auth.validate_csrf_request(
            make_request(
                {"refresh_token": make_refresh("user-1", "session-2")},
                {"x-csrf-token": csrf_token},
            )
        )
    assert mismatch.value.status_code == 403


def test_expired_csrf_token_is_rejected():
    refresh = make_refresh("user-1", "session-1")
    csrf_token = web_auth.make_csrf_token("session-1", expires_at=1)

    with pytest.raises(HTTPException) as expired:
        web_auth.validate_csrf_request(
            make_request(
                {"refresh_token": refresh},
                {"x-csrf-token": csrf_token},
            )
        )
    assert expired.value.status_code == 403


def make_request(cookies: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> Request:
    raw_headers: list[tuple[bytes, bytes]] = []
    if cookies:
        cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())
        raw_headers.append((b"cookie", cookie_header.encode("latin-1")))
    for name, value in (headers or {}).items():
        raw_headers.append((name.lower().encode("latin-1"), value.encode("latin-1")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/web/auth/logout",
            "headers": raw_headers,
        }
    )
