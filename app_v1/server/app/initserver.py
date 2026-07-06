from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, SessionLocal, engine
from app.service.realtime_service import safe_close_client, stop_launcher_session
from app.service.session_service import SessionService
from app.service.user_service import ensure_static_token_users
from app.service.launcher_service import LauncherService
from app.settings import settings
from app.state import runtime
from app.user_auth import db as user_auth_db

_ = user_auth_db


def server() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await start()
        cleanup_task = asyncio.create_task(cleanup_expired_sessions())
        try:
            yield
        finally:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            print("service is stopped.")

    app = FastAPI(title="GP Station v1 Server", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


async def start() -> None:
    async with engine.begin() as conn:
        try:
            await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        except Exception:
            pass
        await cleanup_legacy_schema(conn)
        await conn.run_sync(Base.metadata.create_all)
        await migrate_legacy_schema(conn)

    async with SessionLocal() as db:
        await ensure_static_token_users(db)
        await SessionService.mark_stale_sessions_error(db)
        await LauncherService.mark_stale_launchers_disconnected(db)

    print("service is started.")


async def cleanup_legacy_schema(conn) -> None:
    await conn.exec_driver_sql("DROP TABLE IF EXISTS v1_session_events;")
    await conn.exec_driver_sql("ALTER TABLE IF EXISTS v1_sessions DROP COLUMN IF EXISTS master_id;")
    await conn.exec_driver_sql("DROP TABLE IF EXISTS masters;")
    await migrate_launcher_schema_names(conn)

    await conn.exec_driver_sql("ALTER TABLE IF EXISTS launchers ADD COLUMN IF NOT EXISTS ip_address TEXT;")
    await conn.exec_driver_sql(
        "ALTER TABLE IF EXISTS launchers ADD COLUMN IF NOT EXISTS slave_app_ids JSONB NOT NULL DEFAULT '[]'::jsonb;"
    )
    await conn.exec_driver_sql("ALTER TABLE IF EXISTS launchers ALTER COLUMN slave_app_ids SET DEFAULT '[]'::jsonb;")
    await conn.exec_driver_sql(
        """
        DO $$
        BEGIN
            IF to_regclass('launchers') IS NOT NULL THEN
                UPDATE launchers SET slave_app_ids = '[]'::jsonb WHERE slave_app_ids IS NULL;
            END IF;
        END $$;
        """
    )
    await conn.exec_driver_sql("ALTER TABLE IF EXISTS launchers ALTER COLUMN slave_app_ids SET NOT NULL;")

    await conn.exec_driver_sql("ALTER TABLE IF EXISTS v1_sessions ADD COLUMN IF NOT EXISTS ip_address TEXT;")
    await conn.exec_driver_sql("ALTER TABLE IF EXISTS v1_sessions ADD COLUMN IF NOT EXISTS user_agent TEXT;")

    for table_name in ("access_keys", "launchers", "slaves", "v1_sessions", "slave_sessions"):
        await conn.exec_driver_sql(f"ALTER TABLE IF EXISTS {table_name} DROP COLUMN IF EXISTS metadata_json;")

    for column_name in (
        "credit_balance",
        "credit_pending",
        "credit_withdrawable",
        "trust_score",
        "trust_tier",
        "success_job_count",
        "failed_job_count",
        "disputed_job_count",
        "last_login_at",
        "metadata_json",
    ):
        await conn.exec_driver_sql(f"ALTER TABLE IF EXISTS users DROP COLUMN IF EXISTS {column_name};")


async def migrate_launcher_schema_names(conn) -> None:
    await conn.exec_driver_sql(
        """
        DO $$
        DECLARE
            old_launcher_table regclass := to_regclass('work' || 'ers');
        BEGIN
            IF old_launcher_table IS NOT NULL AND to_regclass('launchers') IS NULL THEN
                EXECUTE 'ALTER TABLE ' || old_launcher_table || ' RENAME TO launchers';
            END IF;
        END $$;
        """
    )
    await conn.exec_driver_sql(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'launchers'
                  AND column_name = ('work' || 'er_name')
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'launchers'
                  AND column_name = 'launcher_name'
            ) THEN
                EXECUTE 'ALTER TABLE launchers RENAME COLUMN ' || 'work' || 'er_name TO launcher_name';
            END IF;
        END $$;
        """
    )
    for table_name in ("slave_sessions", "v1_sessions", "slaves"):
        await conn.exec_driver_sql(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                      AND column_name = ('work' || 'er_id')
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                      AND column_name = 'launcher_id'
                ) THEN
                    EXECUTE 'ALTER TABLE {table_name} RENAME COLUMN ' || 'work' || 'er_id TO launcher_id';
                END IF;
            END $$;
            """
        )


async def migrate_legacy_schema(conn) -> None:
    await conn.exec_driver_sql(
        """
        DO $$
        BEGIN
            IF to_regclass('slaves') IS NOT NULL THEN
                UPDATE launchers AS w
                SET slave_app_ids = COALESCE(s.slave_app_ids, '[]'::jsonb)
                FROM (
                    SELECT launcher_id, jsonb_agg(slave_app_id ORDER BY slave_app_id) AS slave_app_ids
                    FROM (
                        SELECT DISTINCT launcher_id, slave_app_id
                        FROM slaves
                        WHERE slave_app_id IS NOT NULL
                    ) AS distinct_slaves
                    GROUP BY launcher_id
                ) AS s
                WHERE w.id = s.launcher_id;
            END IF;
        END $$;
        """
    )
    await conn.exec_driver_sql(
        """
        DO $$
        BEGIN
            IF to_regclass('v1_sessions') IS NOT NULL THEN
                INSERT INTO slave_sessions (
                    id,
                    user_id,
                    launcher_id,
                    slave_app_id,
                    master_ip_address,
                    master_user_agent,
                    session_token_hash,
                    status,
                    ttl_seconds,
                    expires_at,
                    ready_at,
                    closed_at,
                    last_error,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    user_id,
                    launcher_id,
                    slave_app_id,
                    ip_address,
                    user_agent,
                    session_token_hash,
                    status,
                    ttl_seconds,
                    expires_at,
                    ready_at,
                    closed_at,
                    last_error,
                    created_at,
                    updated_at
                FROM v1_sessions
                ON CONFLICT (id) DO NOTHING;
            END IF;
        END $$;
        """
    )
    await conn.exec_driver_sql("DROP TABLE IF EXISTS v1_sessions;")
    await conn.exec_driver_sql("DROP TABLE IF EXISTS slaves;")


async def cleanup_expired_sessions() -> None:
    while True:
        await asyncio.sleep(settings.cleanup_interval_seconds)
        async with SessionLocal() as db:
            expired_sessions = await SessionService.collect_expired_sessions(db)
        for db_session in expired_sessions:
            session = await runtime.close_session(str(db_session.id))
            launcher_id = session.launcher_id if session else str(db_session.launcher_id) if db_session.launcher_id else None
            if launcher_id is not None:
                await stop_launcher_session(launcher_id, str(db_session.id), "expired")
            if session is not None:
                await safe_close_client(session, "expired")
