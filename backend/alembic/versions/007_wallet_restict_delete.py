"""007_wallet_restrict_delete

Change wallets.user_id FK ondelete from CASCADE to RESTRICT.

CASCADE means deleting a user would silently delete their wallet and all
ledger entries — destroying financial audit records permanently with no
warning. For a fintech system processing real money this is dangerous.

RESTRICT means a user with an active wallet cannot be deleted. The deletion
will fail with a FK constraint violation, forcing the caller to explicitly
handle the wallet (archive, zero it out, or transfer) before deleting the user.

FIX (v2.0.3): Migration 007 originally assumed the FK was named
'fk_wallets_user_id'. However, when the wallets table is created via
CREATE TABLE ... REFERENCES (inline syntax, no explicit constraint name),
PostgreSQL auto-assigns the name 'wallets_user_id_fkey'. The migration now
dynamically discovers the actual FK name from pg_constraint, making it
robust regardless of how the wallets table was originally created.

Revision ID: 007
Revises: 006
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def _get_wallets_user_fk_name(conn) -> str | None:
    """
    Dynamically discover the name of the FK constraint on wallets.user_id.

    This handles two naming conventions:
      - 'fk_wallets_user_id'       (created by Alembic op.create_table with explicit name)
      - 'wallets_user_id_fkey'     (PostgreSQL auto-name when using inline REFERENCES)

    Returns the constraint name if found, None otherwise.
    """
    result = conn.execute(text("""
        SELECT conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
        WHERE t.relname = 'wallets'
          AND c.contype = 'f'
          AND a.attname = 'user_id'
        LIMIT 1
    """))
    row = result.fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()

    # Discover the actual FK constraint name (robust to both naming conventions)
    fk_name = _get_wallets_user_fk_name(conn)

    if fk_name is None:
        # No FK on wallets.user_id at all — just create the RESTRICT one
        print("  wallets.user_id FK not found — creating RESTRICT FK directly")
        op.create_foreign_key(
            "fk_wallets_user_id_restrict",
            "wallets",
            "users",
            ["user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        return

    if fk_name == "fk_wallets_user_id_restrict":
        # Already the correct RESTRICT FK — migration was already applied manually
        print("  RESTRICT FK already exists — skipping")
        return

    # Drop the existing FK (whatever it's named) and recreate with RESTRICT
    print(f"  Dropping FK '{fk_name}' and recreating with RESTRICT")
    conn.execute(text(f'ALTER TABLE wallets DROP CONSTRAINT "{fk_name}"'))
    op.create_foreign_key(
        "fk_wallets_user_id_restrict",
        "wallets",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Check if the RESTRICT FK exists before trying to drop it
    result = conn.execute(text("""
        SELECT conname FROM pg_constraint
        WHERE conname = 'fk_wallets_user_id_restrict'
    """))
    if result.fetchone():
        conn.execute(text('ALTER TABLE wallets DROP CONSTRAINT "fk_wallets_user_id_restrict"'))

    # Recreate with CASCADE (original but dangerous behaviour)
    op.create_foreign_key(
        "fk_wallets_user_id",
        "wallets",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )