from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.auth import authenticate_bearer_token
from app.db import AccessKey
from app.models import AccessKeyCreate
from app.service.access_key_service import AccessKeyService
from app.user_auth.db import User
from app.user_auth.utils.auth_utils import hash_token


class FakeAuthDb:
    def __init__(self, access_key=None, user=None):
        self.access_key = access_key
        self.user = user
        self.commits = 0

    async def scalar(self, _stmt):
        return self.access_key

    async def get(self, model, object_id):
        if model is User and self.user is not None and self.user.id == object_id:
            return self.user
        return None

    async def commit(self):
        self.commits += 1


class FakeAccessKeyDb(FakeAuthDb):
    def __init__(self, user):
        super().__init__(user=user)
        self.added = []

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = "access-key-1"
        self.added.append(obj)
        self.access_key = obj

    async def refresh(self, _obj):
        return None


def make_user(role="user"):
    return User(id="user-1", email="user@example.test", role=role, status="active")


@pytest.mark.asyncio
async def test_access_key_service_creates_scoped_token_once():
    db = FakeAccessKeyDb(make_user())

    result = await AccessKeyService.create_user_access_key(
        db,
        "user-1",
        AccessKeyCreate(name="desktop", scopes=["launcher", "client", "launcher"]),
    )

    assert result.secret.startswith("gpsk_")
    assert result.access_key.scopes == ["launcher", "client"]
    assert result.access_key.key_prefix == result.secret[:16]
    assert db.access_key.key_hash == hash_token(result.secret)
    assert db.commits == 1


@pytest.mark.asyncio
async def test_db_access_key_auth_updates_last_used_and_scopes():
    secret = "gpsk_secret"
    access_key = AccessKey(
        id="key-1",
        user_id="user-1",
        key_type="user_api",
        name="desktop",
        key_prefix=secret[:16],
        key_hash=hash_token(secret),
        scopes=["client", "launcher"],
        status="active",
    )
    db = FakeAuthDb(access_key=access_key, user=make_user())

    principal = await authenticate_bearer_token(db, secret)

    assert principal.user_id == "user-1"
    assert principal.scopes == frozenset({"client", "launcher"})
    assert access_key.last_used_at is not None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_db_access_key_auth_rejects_revoked_expired_or_unauthorized_user():
    secret = "gpsk_secret"
    access_key = AccessKey(
        id="key-1",
        user_id="user-1",
        key_type="user_api",
        name="desktop",
        key_prefix=secret[:16],
        key_hash=hash_token(secret),
        scopes=["client"],
        status="active",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    with pytest.raises(HTTPException):
        await authenticate_bearer_token(FakeAuthDb(access_key=access_key, user=make_user()), secret)

    access_key.expires_at = None
    access_key.status = "revoked"
    with pytest.raises(HTTPException):
        await authenticate_bearer_token(FakeAuthDb(access_key=access_key, user=make_user()), secret)

    access_key.status = "active"
    with pytest.raises(HTTPException):
        await authenticate_bearer_token(FakeAuthDb(access_key=access_key, user=make_user("unauthorized")), secret)
