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
        "slave_sessions",
    ]:
        assert table_name in Base.metadata.tables

    assert "slaves" not in Base.metadata.tables
    assert "v1_sessions" not in Base.metadata.tables
    legacy_launcher_table = "work" + "ers"
    legacy_launcher_id = "work" + "er_id"

    assert "launchers" in Base.metadata.tables
    assert legacy_launcher_table not in Base.metadata.tables
    assert "ip_address" in Base.metadata.tables["launchers"].columns
    assert "slave_app_ids" in Base.metadata.tables["launchers"].columns
    assert "launcher_name" in Base.metadata.tables["launchers"].columns
    assert "launcher_id" in Base.metadata.tables["slave_sessions"].columns
    assert legacy_launcher_id not in Base.metadata.tables["slave_sessions"].columns
    assert "master_ip_address" in Base.metadata.tables["slave_sessions"].columns
    assert "master_user_agent" in Base.metadata.tables["slave_sessions"].columns
