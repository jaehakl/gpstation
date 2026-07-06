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
        "workers",
        "slave_sessions",
    ]:
        assert table_name in Base.metadata.tables

    assert "slaves" not in Base.metadata.tables
    assert "v1_sessions" not in Base.metadata.tables
    assert "ip_address" in Base.metadata.tables["workers"].columns
    assert "slave_app_ids" in Base.metadata.tables["workers"].columns
    assert "master_ip_address" in Base.metadata.tables["slave_sessions"].columns
    assert "master_user_agent" in Base.metadata.tables["slave_sessions"].columns
