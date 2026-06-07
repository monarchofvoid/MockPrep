"""006_fix_credit_ledger_fk

Add proper ForeignKey constraint from credit_ledger.payment_order_id
to payment_orders.id.

The column previously existed as a plain String(36) with a comment
"links to PaymentOrder.id" but no DB-level enforcement. This migration
adds the FK so referential integrity is enforced at the database level.

ondelete=SET NULL: if a payment order is deleted (e.g., cleanup),
the ledger entry is preserved (ledger is immutable) with payment_order_id
set to NULL. This is safe — the ledger entry retains its idempotency_key
and amount, which are the critical audit fields.

Revision ID: 006
Revises: 005
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "006"
down_revision = "005_hash_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # First ensure the column exists (it should from migration 001)
    # Add the FK constraint
    with op.batch_alter_table("credit_ledger") as batch_op:
        batch_op.create_foreign_key(
            "fk_credit_ledger_payment_order_id",
            "payment_orders",
            ["payment_order_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("credit_ledger") as batch_op:
        batch_op.drop_constraint(
            "fk_credit_ledger_payment_order_id",
            type_="foreignkey",
        )