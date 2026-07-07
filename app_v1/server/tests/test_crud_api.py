from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import Principal
from app.db import AccessKey
from app.models import UserData
from app.routers.crud import access_keys, launchers, slave_sessions, users
from app.routers.crud.auth import require_crud_user
from app.routers.crud.models import CrudDeleteRequest, CrudUpsertRequest
from app.user_auth.db import User
from app.user_auth.utils.auth_utils import hash_token
from app.utils import crud


class FakeCrudAuthDb:
    def __init__(self, user):
        self.user = user

    async def get(self, model, object_id):
        if model is User and self.user is not None and self.user.id == object_id:
            return self.user
        return None


class FakeScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeExecuteResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return FakeScalarRows(self.rows)


class FakeDeleteDb:
    def __init__(self, rows):
        self.rows = rows
        self.commits = 0

    async def execute(self, _stmt):
        return FakeExecuteResult(self.rows)

    async def commit(self):
        self.commits += 1


class FakeUpsertDb:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def make_user_data(role="user", user_id="user-1") -> UserData:
    return UserData(id=user_id, role=role, status="active", is_active=True, roles=[role])


def test_crud_specs_do_not_expose_sensitive_fields():
    sensitive_fields = {
        "password_hash",
        "key_hash",
        "session_id_hash",
        "session_token_hash",
        "state",
        "nonce",
        "code_verifier",
    }

    for spec in [users.CRUD_SPEC, access_keys.CRUD_SPEC, launchers.CRUD_SPEC, slave_sessions.CRUD_SPEC]:
        assert sensitive_fields.isdisjoint(spec.public_fields)
        assert sensitive_fields.isdisjoint(spec.writable_fields)


def test_crud_relationship_fields_are_id_only():
    user_row = SimpleNamespace(
        id="user-1",
        email="user@example.test",
        username=None,
        display_name="User",
        role="user",
        status="active",
        created_at=None,
        updated_at=None,
        access_keys=[SimpleNamespace(id="key-1", name="desktop")],
        launchers=[SimpleNamespace(id="launcher-1", ip_address="127.0.0.1")],
        slave_sessions=[SimpleNamespace(id="session-1", slave_app_id="echo")],
    )
    launcher_row = SimpleNamespace(
        id="launcher-1",
        user_id="user-1",
        launcher_name="local",
        ip_address="127.0.0.1",
        status="online",
        slave_app_ids=["echo"],
        active_session_ids=[],
        connected_at=None,
        last_heartbeat_at=None,
        disconnected_at=None,
        created_at=None,
        updated_at=None,
        slave_sessions=[SimpleNamespace(id="session-1", slave_app_id="echo")],
    )

    serialized_user = crud.serialize_entity(user_row, users.CRUD_SPEC)
    serialized_launcher = crud.serialize_entity(launcher_row, launchers.CRUD_SPEC)

    assert serialized_user["access_key_ids"] == ["key-1"]
    assert serialized_user["launcher_ids"] == ["launcher-1"]
    assert serialized_user["slave_session_ids"] == ["session-1"]
    assert serialized_launcher["slave_session_ids"] == ["session-1"]
    assert "access_key_names" not in serialized_user
    assert "launcher_labels" not in serialized_user
    assert "slave_session_labels" not in serialized_launcher


def test_crud_relationship_fields_are_eager_loaded():
    assert users.CRUD_SPEC.relationship_loads == ("access_keys", "launchers", "slave_sessions")
    assert launchers.CRUD_SPEC.relationship_loads == ("slave_sessions",)


def test_crud_visibility_scopes_user_owned_tables_and_blocks_unowned_tables():
    user = make_user_data()
    admin = make_user_data("admin")

    assert crud.visibility_clause(users.CRUD_SPEC, user) is not None
    assert crud.visibility_clause(access_keys.CRUD_SPEC, user) is not None
    assert crud.visibility_clause(users.CRUD_SPEC, admin) is None


@pytest.mark.asyncio
async def test_crud_write_rejects_non_admin():
    user = make_user_data()

    with pytest.raises(HTTPException) as upsert_exc:
        await crud.upsert_rows(
            object(),
            users.CRUD_SPEC,
            CrudUpsertRequest(items=[{"email": "user@example.test"}]),
            user,
        )
    assert upsert_exc.value.status_code == 403

    with pytest.raises(HTTPException) as delete_exc:
        await crud.delete_rows(object(), slave_sessions.CRUD_SPEC, CrudDeleteRequest(ids=["session-1"]), user)
    assert delete_exc.value.status_code == 403


@pytest.mark.asyncio
async def test_crud_user_upsert_rejects_invalid_role_before_db_write():
    with pytest.raises(HTTPException) as exc:
        await crud.upsert_rows(
            FakeUpsertDb(),
            users.CRUD_SPEC,
            CrudUpsertRequest(items=[{"role": "owner"}]),
            make_user_data("admin"),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_crud_bearer_auth_requires_client_scope(monkeypatch):
    user = User(id="user-1", email="user@example.test", role="user", status="active")

    async def authenticate_launcher_only(_db, _authorization):
        return Principal(token="token", user_id="user-1", scopes=frozenset({"launcher"}))

    monkeypatch.setattr("app.routers.crud.auth.authenticate_db_authorization", authenticate_launcher_only)

    with pytest.raises(HTTPException) as exc:
        await require_crud_user(object(), "Bearer token", FakeCrudAuthDb(user))
    assert exc.value.status_code == 403

    async def authenticate_client(_db, _authorization):
        return Principal(token="token", user_id="user-1", scopes=frozenset({"client"}))

    monkeypatch.setattr("app.routers.crud.auth.authenticate_db_authorization", authenticate_client)

    current_user = await require_crud_user(object(), "Bearer token", FakeCrudAuthDb(user))

    assert current_user.id == "user-1"
    assert current_user.role == "user"


@pytest.mark.asyncio
async def test_crud_access_key_delete_revokes_without_exposing_hash():
    access_key = AccessKey(
        id="key-1",
        user_id="user-1",
        key_type="user_api",
        name="desktop",
        key_prefix="gpsk_secret",
        key_hash=hash_token("gpsk_secret"),
        scopes=["client"],
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db = FakeDeleteDb([access_key])
    spec = access_keys.CRUD_SPEC

    row = crud.serialize_entity(access_key, spec)
    result = await crud.delete_rows(db, spec, CrudDeleteRequest(ids=["key-1"]), make_user_data("admin"))

    assert "key_hash" not in row
    assert result.deleted == 1
    assert access_key.status == "revoked"
    assert access_key.revoked_at is not None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_crud_slave_session_delete_uses_session_service(monkeypatch):
    calls = []

    async def close_session(db, session_id, reason):
        calls.append((db, session_id, reason))
        return object() if session_id == "session-1" else None

    monkeypatch.setattr(slave_sessions.SessionService, "close_session", close_session)

    db = object()
    result = await crud.delete_rows(
        db,
        slave_sessions.CRUD_SPEC,
        CrudDeleteRequest(ids=["session-1", "missing"]),
        make_user_data("admin"),
    )

    assert result.deleted == 1
    assert calls == [(db, "session-1", "closed by CRUD"), (db, "missing", "closed by CRUD")]
