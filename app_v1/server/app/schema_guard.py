from __future__ import annotations

import argparse
import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.db import engine
from app.settings import settings, validate_database_transport

BASELINE_REVISION = "20260710_0001"
HEAD_REVISION = "20260710_0004"
BASELINE_COLUMNS = {
    "users": {"id", "email", "username", "display_name", "password_hash", "role", "status", "created_at", "updated_at"},
    "identities": {"id", "user_id", "provider", "provider_user_id", "email", "email_verified", "raw_profile", "created_at", "updated_at"},
    "sessions": {"id", "user_id", "session_id_hash", "created_at", "last_seen_at", "ip", "user_agent", "revoked_at"},
    "oauth_states": {"id", "provider", "state", "nonce", "code_verifier", "redirect_uri", "created_at", "consumed_at"},
    "auth_audit": {"id", "user_id", "provider", "event", "ip", "user_agent", "details", "created_at"},
    "access_keys": {
        "id", "user_id", "key_type", "name", "key_prefix", "key_hash", "scopes", "status",
        "rate_limit_per_minute", "allowed_ips", "allowed_origins", "last_used_at", "expires_at", "created_at", "revoked_at",
    },
    "launchers": {
        "id", "user_id", "launcher_name", "ip_address", "status", "slave_app_ids", "connected_at",
        "last_heartbeat_at", "disconnected_at", "created_at", "updated_at",
    },
    "jobs": {
        "id", "user_id", "launcher_id", "handler_type", "slave_app_id", "input", "offer", "answer", "result",
        "progress", "state", "assigned_at", "answer_ready_at", "started_at", "finished_at", "cancel_requested_at",
        "last_error", "attempt_count", "created_at", "updated_at",
    },
}
BASELINE_CONSTRAINTS = {
    "users": {"pk_users", "ck_users_ck_users_role"},
    "identities": {"pk_identities", "fk_identities_user_id_users", "uq_identities_provider_provider_user_id"},
    "sessions": {"pk_sessions", "fk_sessions_user_id_users", "uq_sessions_session_id_hash"},
    "oauth_states": {"pk_oauth_states", "uq_oauth_states_state"},
    "auth_audit": {"pk_auth_audit", "fk_auth_audit_user_id_users", "ck_auth_audit_ck_auth_audit_event"},
    "access_keys": {"pk_access_keys", "fk_access_keys_user_id_users", "uq_access_keys_key_prefix", "uq_access_keys_key_hash"},
    "launchers": {"pk_launchers", "fk_launchers_user_id_users"},
    "jobs": {"pk_jobs", "fk_jobs_user_id_users", "fk_jobs_launcher_id_launchers"},
}
BASELINE_INDEXES = {
    "users": {"uq_users_email_lower": True, "uq_users_username_lower": True},
    "identities": {"idx_identities_user_id": False},
    "sessions": {"idx_sessions_user_id": False},
    "oauth_states": {"idx_oauth_states_created_at": False},
    "auth_audit": {"idx_auth_audit_user_id": False},
}


async def validate_baseline_schema() -> None:
    async with engine.connect() as connection:
        found_columns, found_constraints, found_indexes = await connection.run_sync(read_schema_snapshot)
    problems = []
    for table_name, required_columns in BASELINE_COLUMNS.items():
        missing = required_columns - found_columns.get(table_name, set())
        if missing:
            problems.append(f"{table_name}: missing {', '.join(sorted(missing))}")
        missing_constraints = BASELINE_CONSTRAINTS[table_name] - found_constraints.get(table_name, set())
        if missing_constraints:
            problems.append(f"{table_name}: missing constraints {', '.join(sorted(missing_constraints))}")
        for index_name, unique in BASELINE_INDEXES.get(table_name, {}).items():
            if found_indexes.get(table_name, {}).get(index_name) != unique:
                problems.append(f"{table_name}: missing or invalid index {index_name}")
    if problems:
        raise RuntimeError("Database does not match the GPStation v1 baseline: " + "; ".join(problems))


async def ensure_database_current() -> None:
    await validate_baseline_schema()
    async with engine.connect() as connection:
        tables = await connection.run_sync(lambda sync_connection: set(inspect(sync_connection).get_table_names()))
        if "alembic_version" not in tables:
            raise RuntimeError(
                "Database is not migration-managed. Validate and stamp the existing schema, then run `poetry run alembic upgrade head`."
            )
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    if revision != HEAD_REVISION:
        raise RuntimeError(f"Database revision is {revision or 'empty'}; expected {HEAD_REVISION}. Run `poetry run alembic upgrade head`.")


def read_schema_snapshot(
    sync_connection,
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, dict[str, bool]]]:
    inspector = inspect(sync_connection)
    table_names = set(inspector.get_table_names())
    columns = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in BASELINE_COLUMNS
        if table_name in table_names
    }
    constraints = {}
    for table_name in BASELINE_COLUMNS:
        if table_name not in table_names:
            continue
        names = {inspector.get_pk_constraint(table_name).get("name")}
        names.update(item.get("name") for item in inspector.get_unique_constraints(table_name))
        names.update(item.get("name") for item in inspector.get_check_constraints(table_name))
        names.update(item.get("name") for item in inspector.get_foreign_keys(table_name))
        constraints[table_name] = {name for name in names if name}
    indexes = {
        table_name: {item["name"]: bool(item.get("unique")) for item in inspector.get_indexes(table_name)}
        for table_name in BASELINE_INDEXES
        if table_name in table_names
    }
    return columns, constraints, indexes


async def run_validation() -> str | None:
    transport_errors: list[str] = []
    validate_database_transport(transport_errors, settings.db_url)
    if transport_errors:
        raise RuntimeError("Unsafe database transport: " + "; ".join(transport_errors))
    try:
        await validate_baseline_schema()
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda sync_connection: set(inspect(sync_connection).get_table_names()))
            if "alembic_version" in tables:
                return await connection.scalar(text("SELECT version_num FROM alembic_version"))
            return None
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an existing GPStation v1 database before Alembic adoption.")
    parser.add_argument("--stamp-baseline", action="store_true", help="Stamp a validated, unversioned database at the baseline revision.")
    args = parser.parse_args()
    revision = asyncio.run(run_validation())
    if args.stamp_baseline:
        if revision is not None:
            raise RuntimeError(f"Database is already migration-managed at revision {revision}; refusing to restamp it.")
        config = Config("alembic.ini")
        command.stamp(config, BASELINE_REVISION)
        print(f"Validated and stamped database at {BASELINE_REVISION}.")
    else:
        print("Database matches the pre-Alembic baseline schema.")


if __name__ == "__main__":
    main()
