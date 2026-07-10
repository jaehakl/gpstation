"""Add queue indexes, refresh rotation, and security audit events."""

from alembic import op
import sqlalchemy as sa

revision = "20260710_0002"
down_revision = "20260710_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("refresh_jti_hash", sa.LargeBinary(), nullable=True))
    # Existing sessions predate refresh-token rotation and cannot be adopted
    # safely because the current refresh JTI was never persisted.
    op.execute("UPDATE sessions SET revoked_at = now() WHERE revoked_at IS NULL")
    op.drop_constraint("ck_auth_audit_ck_auth_audit_event", "auth_audit", type_="check")
    op.create_check_constraint(
        "ck_auth_audit_ck_auth_audit_event",
        "auth_audit",
        "event IN ('login_success','login_failure','logout','link_success','unlink','token_created','token_revoked','refresh_reuse','launcher_connected','launcher_rejected')",
    )
    op.execute("CREATE INDEX ix_jobs_queued_created ON jobs (created_at, id) WHERE state = 'queued'")
    op.execute("CREATE INDEX ix_jobs_user_queued_created ON jobs (user_id, created_at, id) WHERE state = 'queued'")
    op.execute("CREATE INDEX ix_jobs_user_created_desc ON jobs (user_id, created_at DESC, id)")
    op.create_index("ix_jobs_launcher_state", "jobs", ["launcher_id", "state"])
    op.create_index("ix_access_keys_user_id", "access_keys", ["user_id"])
    op.create_index("ix_launchers_user_id", "launchers", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_launchers_user_id", table_name="launchers")
    op.drop_index("ix_access_keys_user_id", table_name="access_keys")
    op.drop_index("ix_jobs_launcher_state", table_name="jobs")
    op.drop_index("ix_jobs_user_created_desc", table_name="jobs")
    op.drop_index("ix_jobs_user_queued_created", table_name="jobs")
    op.drop_index("ix_jobs_queued_created", table_name="jobs")
    op.drop_constraint("ck_auth_audit_ck_auth_audit_event", "auth_audit", type_="check")
    op.create_check_constraint(
        "ck_auth_audit_ck_auth_audit_event",
        "auth_audit",
        "event IN ('login_success','login_failure','logout','link_success','unlink')",
    )
    op.drop_column("sessions", "refresh_jti_hash")
