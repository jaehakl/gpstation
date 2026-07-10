"""Baseline the pre-migration GPStation v1 schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260710_0001"
down_revision = None
branch_labels = None
depends_on = None

provider_enum = postgresql.ENUM("google", "github", "kakao", "naver", "apple", name="oauth_provider", create_type=False)


def upgrade() -> None:
    provider_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "oauth_states",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("nonce", sa.Text()),
        sa.Column("code_verifier", sa.Text()),
        sa.Column("redirect_uri", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name="pk_oauth_states"),
        sa.UniqueConstraint("state", name="uq_oauth_states_state"),
    )
    op.create_index("idx_oauth_states_created_at", "oauth_states", ["created_at"])
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("email", sa.Text()),
        sa.Column("username", sa.Text()),
        sa.Column("display_name", sa.Text()),
        sa.Column("password_hash", sa.Text()),
        sa.Column("role", sa.Text(), server_default=sa.text("'unauthorized'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('admin','user','unauthorized')", name="ck_users_ck_users_role"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)
    op.create_table(
        "access_keys",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("key_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.LargeBinary(), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer()),
        sa.Column("allowed_ips", postgresql.JSONB()),
        sa.Column("allowed_origins", postgresql.JSONB()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_access_keys_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_access_keys"),
        sa.UniqueConstraint("key_hash", name="uq_access_keys_key_hash"),
        sa.UniqueConstraint("key_prefix", name="uq_access_keys_key_prefix"),
    )
    op.create_table(
        "auth_audit",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False)),
        sa.Column("provider", provider_enum),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("ip", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event IN ('login_success','login_failure','logout','link_success','unlink')",
            name="ck_auth_audit_ck_auth_audit_event",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_auth_audit_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_auth_audit"),
    )
    op.create_index("idx_auth_audit_user_id", "auth_audit", ["user_id"])
    op.create_table(
        "identities",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("provider_user_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text()),
        sa.Column("email_verified", sa.Boolean()),
        sa.Column("raw_profile", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_identities_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_identities"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_identities_provider_provider_user_id"),
    )
    op.create_index("idx_identities_user_id", "identities", ["user_id"])
    op.create_table(
        "launchers",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("launcher_name", sa.Text(), nullable=False),
        sa.Column("ip_address", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("slave_app_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_launchers_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_launchers"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("session_id_hash", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sessions_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.UniqueConstraint("session_id_hash", name="uq_sessions_session_id_hash"),
    )
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("launcher_id", postgresql.UUID(as_uuid=False)),
        sa.Column("handler_type", sa.Text(), nullable=False),
        sa.Column("slave_app_id", sa.Text(), nullable=False),
        sa.Column("input", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("offer", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("answer", postgresql.JSONB()),
        sa.Column("result", postgresql.JSONB()),
        sa.Column("progress", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("state", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("answer_ready_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["launcher_id"], ["launchers.id"], name="fk_jobs_launcher_id_launchers", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_jobs_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_jobs"),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_index("idx_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("launchers")
    op.drop_index("idx_identities_user_id", table_name="identities")
    op.drop_table("identities")
    op.drop_index("idx_auth_audit_user_id", table_name="auth_audit")
    op.drop_table("auth_audit")
    op.drop_table("access_keys")
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_index("idx_oauth_states_created_at", table_name="oauth_states")
    op.drop_table("oauth_states")
    provider_enum.drop(op.get_bind(), checkfirst=True)
