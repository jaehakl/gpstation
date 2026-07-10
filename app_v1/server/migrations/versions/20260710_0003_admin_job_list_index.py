"""Add the global job-list ordering index used by administrators."""

from alembic import op


revision = "20260710_0003"
down_revision = "20260710_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_jobs_created_desc ON jobs (created_at DESC, id)")


def downgrade() -> None:
    op.drop_index("ix_jobs_created_desc", table_name="jobs")
