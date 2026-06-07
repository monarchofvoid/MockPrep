"""004_add_login_attempts_index

Revision ID: 004_add_login_attempts_index
Revises: 003_seed_credit_plans
Create Date: 2025-01-10 13:00:00.000000

Adds composite index on (email, attempted_at) for the login_attempts table.

This index optimizes the brute-force protection query that checks for
recent failed login attempts per email address:

    SELECT COUNT(*) FROM login_attempts
    WHERE email = ? AND attempted_at > ?

Without this index, the query performs a sequential scan.
With this index, it's an efficient index lookup.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_add_login_attempts_index'
down_revision = '003_seed_credit_plans'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create composite index on (email, attempted_at)
    # This index supports queries filtering by email and ordering/filtering by attempted_at
    op.create_index(
        'idx_login_attempts_email_attempted_at',
        'login_attempts',
        ['email', 'attempted_at'],
        unique=False
    )


def downgrade() -> None:
    # Drop the composite index
    op.drop_index('idx_login_attempts_email_attempted_at', table_name='login_attempts')