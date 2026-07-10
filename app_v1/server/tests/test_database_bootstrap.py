from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import inspect

from app import initserver
from app.db import Base, engine


@pytest.mark.asyncio
async def test_start_creates_schema_before_recovery_and_dispatcher(monkeypatch):
    events: list[str] = []

    class Connection:
        async def run_sync(self, operation):
            assert operation.__self__ is Base.metadata
            assert operation.__name__ == "create_all"
            events.append("create_all")

    class EngineContext:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *_args):
            return None

    class FakeEngine:
        def begin(self):
            return EngineContext()

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    def validate(_settings):
        events.append("validate")

    async def recover(_db):
        events.append("recover")

    async def start_dispatcher():
        events.append("dispatcher")

    monkeypatch.setattr(initserver, "engine", FakeEngine())
    monkeypatch.setattr(initserver, "SessionLocal", SessionContext)
    monkeypatch.setattr(initserver, "validate_runtime_settings", validate)
    monkeypatch.setattr(initserver.JobService, "recover_after_server_restart", recover)
    monkeypatch.setattr(initserver, "start_job_dispatcher", start_dispatcher)

    await initserver.start()

    assert events == ["validate", "create_all", "recover", "dispatcher"]


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("GPSTATION_V1_RUN_DB_INTEGRATION") != "1",
    reason="set GPSTATION_V1_RUN_DB_INTEGRATION=1 for the isolated PostgreSQL schema bootstrap test",
)
async def test_postgres_create_all_is_idempotent():
    schema = f"gpstation_bootstrap_test_{uuid.uuid4().hex[:12]}"

    def exercise(sync_connection):
        Base.metadata.create_all(sync_connection)
        Base.metadata.create_all(sync_connection)

        table_names = set(inspect(sync_connection).get_table_names())
        assert table_names == set(Base.metadata.tables)

        Base.metadata.drop_all(sync_connection)
        assert inspect(sync_connection).get_table_names() == []

    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            await connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            await connection.run_sync(exercise)
    finally:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
