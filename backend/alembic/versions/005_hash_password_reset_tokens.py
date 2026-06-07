"""005_hash_password_reset_tokens

Revision ID: 005_hash_password_reset_tokens
Revises: 004_add_login_attempts_index
Create Date: 2025-01-10 14:00:00.000000

Replaces the plaintext `token` field with `token_hash` in password_resets table.

Security fix: password reset tokens should never be stored in plaintext.
They are now hashed with SHA-256 before storage, matching the pattern
used for refresh tokens.

Note: This migration deletes all existing password reset tokens, as they
cannot be migrated from plaintext to hashed format. Users with pending
resets will need to request a new reset link.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005_hash_password_reset_tokens'
down_revision = '004_add_login_attempts_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop all existing password reset tokens (cannot migrate plaintext to hash)
    op.execute("DELETE FROM password_resets")
    
    # Drop old token column
    op.drop_column('password_resets', 'token')
    
    # Add new token_hash column
    op.add_column(
        'password_resets',
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True)
    )
    
    # Add index on token_hash for fast lookups
    op.create_index(
        'ix_password_resets_token_hash',
        'password_resets',
        ['token_hash'],
        unique=True
    )


def downgrade() -> None:
    # Drop token_hash column and index
    op.drop_index('ix_password_resets_token_hash', table_name='password_resets')
    op.drop_column('password_resets', 'token_hash')
    
    # Restore old token column
    op.add_column(
        'password_resets',
        sa.Column('token', sa.Text(), nullable=False)
    )