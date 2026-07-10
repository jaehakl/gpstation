from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import Base, db_connect_args, make_async_db_url
from app.settings import settings, validate_database_transport
from app.user_auth import db as user_auth_db

_ = user_auth_db
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=make_async_db_url(settings.db_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_sync_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    transport_errors: list[str] = []
    validate_database_transport(transport_errors, settings.db_url)
    if transport_errors:
        raise RuntimeError("Unsafe database transport: " + "; ".join(transport_errors))
    engine = create_async_engine(
        make_async_db_url(settings.db_url),
        pool_pre_ping=True,
        connect_args=db_connect_args(settings.db_url),
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_sync_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
