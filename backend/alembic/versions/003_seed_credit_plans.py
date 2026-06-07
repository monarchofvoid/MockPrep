"""003_seed_credit_plans

Revision ID: 003_seed_credit_plans
Revises: 002_seed_wallets_signup_bonus
Create Date: 2025-01-10 12:00:00.000000

Seeds the initial credit plan offerings.

Plans:
  - Starter: 50 credits for ₹99
  - Pro: 150 credits for ₹249 (marked as popular)
  - Premium: 300 credits for ₹449

All amounts stored in paise (1 INR = 100 paise).
Credits granted are in credits (not microcredits).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision = '003_seed_credit_plans'
down_revision = '002_seed_wallets_signup_bonus'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create a table reference for bulk insert
    credit_plans = table(
        'credit_plans',
        column('name', sa.String),
        column('description', sa.String),
        column('amount_paise', sa.Integer),
        column('credits_granted', sa.Integer),
        column('is_active', sa.Boolean),
        column('is_popular', sa.Boolean),
        column('sort_order', sa.Integer),
    )

    # Insert initial credit plans
    op.bulk_insert(
        credit_plans,
        [
            {
                'name': 'Starter',
                'description': 'Perfect for getting started with AI-powered practice',
                'amount_paise': 9900,  # ₹99
                'credits_granted': 50,
                'is_active': True,
                'is_popular': False,
                'sort_order': 1,
            },
            {
                'name': 'Pro',
                'description': 'Most popular — ideal for regular practice sessions',
                'amount_paise': 24900,  # ₹249
                'credits_granted': 150,
                'is_active': True,
                'is_popular': True,  # Highlighted in UI
                'sort_order': 2,
            },
            {
                'name': 'Premium',
                'description': 'Best value for intensive exam preparation',
                'amount_paise': 44900,  # ₹449
                'credits_granted': 300,
                'is_active': True,
                'is_popular': False,
                'sort_order': 3,
            },
        ]
    )


def downgrade() -> None:
    # Delete seeded credit plans
    op.execute(
        "DELETE FROM credit_plans WHERE name IN ('Starter', 'Pro', 'Premium')"
    )