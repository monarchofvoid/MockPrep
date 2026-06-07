"""
001_v2_initial_schema

Create full VYAS v2.0 schema:
  - All v0.11 tables (users, user_profiles, mock_tests, etc.)
  - New v2.0 tables (wallets, credit_ledger, payment_orders, ai_jobs, etc.)
  - All indexes and constraints

Revision: 001_v2_initial
Down: drops all tables (destructive — only use in dev)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_v2_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Auth Tables ────────────────────────────────────────────────────────────

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("hashed_password", sa.String(200), nullable=True),  # v2.0: nullable
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("has_seen_premium_popup", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"])

    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_account_id", sa.String(100), nullable=False),
        sa.Column("provider_email", sa.String(200), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    )
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_attempts_email", "login_attempts", ["email"])

    op.create_table(
        "password_resets",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preparing_exam", sa.String(50), nullable=True),
        sa.Column("target_year", sa.Integer(), nullable=True),
        sa.Column("subject_focus", sa.String(200), nullable=True),
        sa.Column("avatar", sa.String(50), nullable=True),
        sa.Column("daily_goal_mins", sa.Integer(), nullable=True, server_default="60"),
        sa.Column("bio", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # ── Wallet Tables ──────────────────────────────────────────────────────────

    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance_microcredits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifetime_earned_microcredits", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lifetime_spent_microcredits", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_wallets_user_id"),
        sa.CheckConstraint("balance_microcredits >= 0", name="chk_wallet_balance_non_negative"),
    )
    op.create_index("ix_wallets_user_id", "wallets", ["user_id"])

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), sa.ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_microcredits", sa.Integer(), nullable=False),
        sa.Column("balance_after_microcredits", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("payment_order_id", sa.String(36), nullable=True),
        sa.Column("ai_job_id", sa.String(36), nullable=True),
        sa.Column("admin_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("refund_for_ledger_id", sa.Integer(), sa.ForeignKey("credit_ledger.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_ledger_idempotency_key"),
        sa.CheckConstraint("amount_microcredits != 0", name="chk_ledger_nonzero_amount"),
    )
    op.create_index("ix_ledger_wallet_id", "credit_ledger", ["wallet_id"])
    op.create_index("ix_ledger_created_at", "credit_ledger", ["created_at"])
    op.create_index("ix_ledger_entry_type", "credit_ledger", ["entry_type"])
    op.create_index("ix_ledger_ai_job_id", "credit_ledger", ["ai_job_id"])
    op.create_index("ix_ledger_payment_order_id", "credit_ledger", ["payment_order_id"])

    op.create_table(
        "feature_pricing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feature_key", sa.String(50), nullable=False),
        sa.Column("cost_microcredits", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_key", name="uq_feature_pricing_key"),
    )

    # ── Payment Tables ─────────────────────────────────────────────────────────

    op.create_table(
        "credit_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("credits_granted", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_popular", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("credit_plans.id"), nullable=False),
        sa.Column("razorpay_order_id", sa.String(50), nullable=False),
        sa.Column("razorpay_payment_id", sa.String(50), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("credits_to_grant", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(300), nullable=True),
        sa.Column("razorpay_notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("razorpay_order_id", name="uq_payment_orders_rzp_order_id"),
    )
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"])

    op.create_table(
        "payment_webhook_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("razorpay_event_id", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("razorpay_order_id", sa.String(50), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(50), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processing_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("razorpay_event_id", name="uq_webhook_logs_event_id"),
    )

    # ── AI Job Table ───────────────────────────────────────────────────────────

    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exam", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("use_proficiency", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("cost_microcredits", sa.Integer(), nullable=False),
        sa.Column("deduction_ledger_entry_id", sa.Integer(), sa.ForeignKey("credit_ledger.id"), nullable=True),
        sa.Column("refund_ledger_entry_id", sa.Integer(), sa.ForeignKey("credit_ledger.id"), nullable=True),
        sa.Column("celery_task_id", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("questions_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_mock_id", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proficiency_score", sa.Float(), nullable=True),
        sa.Column("weak_topics_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_jobs_user_id", "ai_jobs", ["user_id"])
    op.create_index("ix_ai_jobs_status", "ai_jobs", ["status"])
    op.create_index("ix_ai_jobs_celery_task_id", "ai_jobs", ["celery_task_id"])

    # ── Mock Test Tables ───────────────────────────────────────────────────────

    op.create_table(
        "mock_tests",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("exam", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("year", sa.String(20), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("total_marks", sa.Float(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("json_file_path", sa.String(300), nullable=True),
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ai_generation_params", sa.JSON(), nullable=True),
        sa.Column("ai_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ai_mock_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mock_id", sa.String(100), sa.ForeignKey("mock_tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_data", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mock_id", sa.String(100), sa.ForeignKey("mock_tests.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("total_marks", sa.Float(), nullable=True),
        sa.Column("correct_count", sa.Integer(), nullable=True),
        sa.Column("wrong_count", sa.Integer(), nullable=True),
        sa.Column("skipped_count", sa.Integer(), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("attempt_rate", sa.Float(), nullable=True),
        sa.Column("time_taken_seconds", sa.Integer(), nullable=True),
        sa.Column("avg_time_per_question", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("selected_option", sa.String(1), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("marks_awarded", sa.Float(), server_default="0"),
        sa.Column("time_spent_seconds", sa.Integer(), server_default="0"),
        sa.Column("visit_count", sa.Integer(), server_default="0"),
        sa.Column("answer_changed_count", sa.Integer(), server_default="0"),
        sa.Column("was_marked_for_review", sa.Boolean(), server_default="false"),
        sa.Column("topic", sa.String(100), nullable=True),
        sa.Column("difficulty", sa.String(20), nullable=True),
        sa.Column("subtopic", sa.String(100), nullable=True),
        sa.Column("question_category", sa.String(50), nullable=True),
        sa.Column("estimated_time_sec", sa.Integer(), nullable=True),
        sa.Column("time_efficiency_ratio", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_proficiency",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exam", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("subtopic", sa.String(100), nullable=True),
        sa.Column("proficiency", sa.Float(), nullable=False, server_default="400.0"),
        sa.Column("accuracy_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("attempt_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_time_efficiency", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("difficulty_easy_acc", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("difficulty_med_acc", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("difficulty_hard_acc", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tutor_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("exam", sa.String(50), nullable=True),
        sa.Column("proficiency_bucket", sa.String(20), nullable=False),
        sa.Column("user_answer", sa.String(1), nullable=True),
        sa.Column("correct_answer", sa.String(1), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cache_key"),
    )

    op.create_table(
        "tutor_interactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("proficiency_at_time", sa.Float(), nullable=True),
        sa.Column("was_cache_hit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("user_rating", sa.Integer(), nullable=True),
        sa.Column("credit_ledger_entry_id", sa.Integer(), sa.ForeignKey("credit_ledger.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Seed Data ─────────────────────────────────────────────────────────────

    # Seed credit plans
    op.bulk_insert(
        sa.table(
            "credit_plans",
            sa.column("name", sa.String),
            sa.column("description", sa.String),
            sa.column("amount_paise", sa.Integer),
            sa.column("credits_granted", sa.Integer),
            sa.column("is_active", sa.Boolean),
            sa.column("is_popular", sa.Boolean),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {"name": "Starter",  "description": "Perfect for trying out VYAS AI mocks",   "amount_paise": 4900,  "credits_granted": 10,  "is_active": True, "is_popular": False, "sort_order": 1},
            {"name": "Popular",  "description": "Most popular — 50 mocks worth of credits","amount_paise": 9900,  "credits_granted": 25,  "is_active": True, "is_popular": True,  "sort_order": 2},
            {"name": "Pro",      "description": "For serious exam prep — 100+ mocks",      "amount_paise": 19900, "credits_granted": 60,  "is_active": True, "is_popular": False, "sort_order": 3},
            {"name": "Ultimate", "description": "Full exam season preparation",             "amount_paise": 39900, "credits_granted": 150, "is_active": True, "is_popular": False, "sort_order": 4},
        ],
    )

    # Seed feature pricing
    op.bulk_insert(
        sa.table(
            "feature_pricing",
            sa.column("feature_key", sa.String),
            sa.column("cost_microcredits", sa.Integer),
            sa.column("description", sa.String),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {"feature_key": "ai_mock_per_question", "cost_microcredits": 15,  "description": "Cost per question in AI mock (microcredits)", "is_active": True},
            {"feature_key": "tutor_explain",        "cost_microcredits": 50,  "description": "Cost per VYAS Explain request (microcredits)", "is_active": True},
        ],
    )


def downgrade() -> None:
    """Drop all tables (destructive — dev only)."""
    tables = [
        "tutor_interactions", "tutor_cache", "user_proficiency", "responses",
        "attempts", "ai_mock_questions", "mock_tests", "ai_jobs",
        "payment_webhook_logs", "payment_orders", "credit_plans",
        "feature_pricing", "credit_ledger", "wallets",
        "user_profiles", "password_resets", "login_attempts",
        "refresh_tokens", "oauth_accounts", "users",
    ]
    for table in tables:
        op.drop_table(table)
