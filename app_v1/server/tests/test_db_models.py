from sqlalchemy.orm import configure_mappers

from app.db import Base
from app.user_auth import db as user_auth_db

_ = user_auth_db


def test_db_mappers_configure():
    configure_mappers()

    for table_name in [
        "users",
        "identities",
        "sessions",
        "oauth_states",
        "auth_audit",
        "access_keys",
        "launchers",
        "jobs",
    ]:
        assert table_name in Base.metadata.tables

    assert "slaves" not in Base.metadata.tables
    assert "v1_sessions" not in Base.metadata.tables
    assert "slave_sessions" not in Base.metadata.tables
    legacy_launcher_table = "work" + "ers"
    legacy_launcher_id = "work" + "er_id"

    assert "launchers" in Base.metadata.tables
    assert legacy_launcher_table not in Base.metadata.tables
    assert "ip_address" in Base.metadata.tables["launchers"].columns
    assert "slave_app_ids" in Base.metadata.tables["launchers"].columns
    assert "launcher_name" in Base.metadata.tables["launchers"].columns
    assert "active_session_ids" not in Base.metadata.tables["launchers"].columns
    assert legacy_launcher_id not in Base.metadata.tables["jobs"].columns
    assert "handler_type" in Base.metadata.tables["jobs"].columns
    assert "slave_app_id" in Base.metadata.tables["jobs"].columns
    assert "offer" in Base.metadata.tables["jobs"].columns
    assert "answer" in Base.metadata.tables["jobs"].columns
    assert "state" in Base.metadata.tables["jobs"].columns
    assert "launcher_id" in Base.metadata.tables["jobs"].columns
