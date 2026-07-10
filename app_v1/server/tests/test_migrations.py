from __future__ import annotations

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from app.db import Base, engine


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("GPSTATION_V1_RUN_DB_INTEGRATION") != "1",
    reason="set GPSTATION_V1_RUN_DB_INTEGRATION=1 for the isolated PostgreSQL migration test",
)
async def test_postgres_migrations_upgrade_and_rollback():
    versions = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    baseline = load_revision(versions / "20260710_0001_baseline.py", "baseline_revision")
    hardening = load_revision(versions / "20260710_0002_hardening.py", "hardening_revision")
    admin_index = load_revision(versions / "20260710_0003_admin_job_list_index.py", "admin_index_revision")
    refresh_grace = load_revision(versions / "20260710_0004_refresh_rotation_grace.py", "refresh_grace_revision")
    schema = f"gpstation_migration_test_{uuid.uuid4().hex[:12]}"

    def exercise(sync_connection):
        operations = Operations(MigrationContext.configure(sync_connection))
        baseline.op = operations
        hardening.op = operations
        admin_index.op = operations
        refresh_grace.op = operations
        baseline.upgrade()
        hardening.upgrade()
        admin_index.upgrade()
        refresh_grace.upgrade()
        inspector = inspect(sync_connection)
        assert set(inspector.get_table_names()) >= {
            "users",
            "identities",
            "sessions",
            "oauth_states",
            "auth_audit",
            "access_keys",
            "launchers",
            "jobs",
        }
        assert "refresh_jti_hash" in {column["name"] for column in inspector.get_columns("sessions")}
        assert "refresh_grace_jti_hashes" in {column["name"] for column in inspector.get_columns("sessions")}
        assert compare_metadata(
            MigrationContext.configure(sync_connection, opts={"compare_type": True}),
            Base.metadata,
        ) == []
        refresh_grace.downgrade()
        admin_index.downgrade()
        hardening.downgrade()
        baseline.downgrade()
        assert not inspect(sync_connection).get_table_names()

    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            await connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            await connection.run_sync(exercise)
    finally:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def load_revision(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
