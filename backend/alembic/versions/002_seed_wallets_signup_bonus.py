"""
002_seed_wallets_signup_bonus

Create wallets for all existing users and grant 5 free credits (signup bonus).

This migration:
1. Creates a wallet for every user who doesn't have one
2. Grants SIGNUP_BONUS (500 microcredits = 5 credits) to each new wallet
3. Creates ledger entries for the bonus grants
4. Safely skips if required tables don't exist

Revision: 002_seed_wallets_signup_bonus
"""

from alembic import op
from sqlalchemy.sql import text

revision = "002_seed_wallets_signup_bonus"
down_revision = "001_v2_initial"
branch_labels = None
depends_on = None

SIGNUP_BONUS_MICROCREDITS = 500  # 5 credits


def table_exists(conn, table_name: str) -> bool:
    return conn.execute(
        text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = :table
            )
        """),
        {"table": table_name}
    ).scalar()


def upgrade() -> None:
    conn = op.get_bind()

    # Verify required tables exist
    wallets_exists = table_exists(conn, "wallets")
    users_exists = table_exists(conn, "users")
    ledger_exists = table_exists(conn, "credit_ledger")

    if not users_exists:
        print("⚠ users table missing — skipping migration")
        return

    if not wallets_exists:
        print("⚠ wallets table missing — skipping migration")
        return

    # Create wallets for existing users
    conn.execute(text("""
        INSERT INTO wallets (
            user_id,
            balance_microcredits,
            lifetime_earned_microcredits,
            lifetime_spent_microcredits
        )
        SELECT
            u.id,
            0,
            0,
            0
        FROM users u
        LEFT JOIN wallets w
            ON w.user_id=u.id
        WHERE w.id IS NULL
    """))

    # Only run ledger logic if table exists
    if ledger_exists:

        conn.execute(
            text("""
                INSERT INTO credit_ledger(
                    wallet_id,
                    amount_microcredits,
                    balance_after_microcredits,
                    entry_type,
                    idempotency_key,
                    description,
                    created_at
                )
                SELECT
                    w.id,
                    :bonus,
                    :bonus,
                    'signup_bonus',
                    'signup_bonus:' || w.user_id,
                    '5 free credits — welcome to VYAS!',
                    NOW()
                FROM wallets w
                WHERE w.lifetime_earned_microcredits=0
                ON CONFLICT (idempotency_key)
                DO NOTHING
            """),
            {"bonus": SIGNUP_BONUS_MICROCREDITS}
        )

        conn.execute(
            text("""
                UPDATE wallets w
                SET
                    balance_microcredits=:bonus,
                    lifetime_earned_microcredits=:bonus,
                    updated_at=NOW()
                FROM credit_ledger cl
                WHERE cl.wallet_id=w.id
                AND cl.idempotency_key=
                    'signup_bonus:' || w.user_id
                AND w.balance_microcredits=0
            """),
            {"bonus": SIGNUP_BONUS_MICROCREDITS}
        )

    result = conn.execute(
        text("SELECT COUNT(*) FROM wallets")
    )

    count = result.scalar()

    print(
        f"✓ Wallet migration completed: "
        f"{count} wallets verified"
    )


def downgrade() -> None:
    conn = op.get_bind()

    if not table_exists(conn, "wallets"):
        return

    if table_exists(conn, "credit_ledger"):

        conn.execute(text("""
            UPDATE wallets w
            SET
                balance_microcredits=0,
                lifetime_earned_microcredits=0
            FROM credit_ledger cl
            WHERE cl.wallet_id=w.id
            AND cl.entry_type='signup_bonus'
        """))

        conn.execute(text("""
            DELETE FROM credit_ledger
            WHERE entry_type='signup_bonus'
        """))