"""008_sync_mock_tests_ai_columns

Add missing AI mock columns to existing mock_tests tables.

Some local databases were created before the v2.0 MockTest model added
AI mock metadata. SQLAlchemy create_all() does not alter existing tables,
so those databases can miss mock_tests.ai_job_id and make /mocks fail.
This migration is intentionally idempotent so it is safe for fresh v2.0
databases where the columns already exist.

Revision ID: 008
Revises: 007
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def _existing_columns(conn, table_name: str) -> set[str]:
    inspector = sa.inspect(conn)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    existing = _existing_columns(conn, "mock_tests")

    with op.batch_alter_table("mock_tests") as batch_op:
        if "is_ai_generated" not in existing:
            batch_op.add_column(
                sa.Column(
                    "is_ai_generated",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if "ai_generation_params" not in existing:
            batch_op.add_column(sa.Column("ai_generation_params", sa.JSON(), nullable=True))
        if "ai_job_id" not in existing:
            batch_op.add_column(sa.Column("ai_job_id", sa.String(36), nullable=True))


def downgrade() -> None:
    # Compatibility migration: do not drop columns that may already have existed
    # in fresh v2.0 databases, and do not risk deleting AI mock metadata.
    pass
