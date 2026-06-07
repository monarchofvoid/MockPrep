"""
009_add_email_verification_otp

Adds the email_verification_otps table for the signup OTP flow, and
adds profile_picture column to users (stores Google profile photo URL
for OAuth users).

Revision: 009_email_otp
Down: drops email_verification_otps and profile_picture column

Notes:
  - email_verified already exists on users (added in 001). No change needed.
  - This migration is safe to run against a live DB — it only adds objects.
"""

from alembic import op
import sqlalchemy as sa

revision = "009_email_otp"
down_revision = "008_sync_mock_tests_ai_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Email Verification OTPs ────────────────────────────────────────────────
    # Stores pending OTPs for the two-step signup flow.
    # Rows are created when the user submits the signup form and
    # deleted (or expired) once the OTP is verified or times out.
    op.create_table(
        "email_verification_otps",
        sa.Column("id",         sa.Integer(),      primary_key=True, index=True),
        # We store the pending user data here, NOT in the users table.
        # The user record is only created AFTER OTP verification succeeds.
        sa.Column("email",      sa.String(200),    nullable=False,   index=True),
        sa.Column("name",       sa.String(100),    nullable=False),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        # 6-digit OTP — we store the bcrypt hash for the same reason we hash
        # passwords: if this table leaks, raw OTPs are not exposed.
        sa.Column("otp_hash",   sa.String(200),    nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts",   sa.Integer(),      nullable=False, server_default="0"),
        sa.Column("resend_count", sa.Integer(),    nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Unique on email so there's at most one pending OTP per address at a time.
    op.create_index(
        "ix_email_verification_otps_email",
        "email_verification_otps",
        ["email"],
        unique=True,
    )

    # ── profile_picture on users ───────────────────────────────────────────────
    # Stores the Google profile photo URL for OAuth users.
    # Nullable — traditional signup users won't have this.
    op.add_column(
        "users",
        sa.Column("profile_picture", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_otps_email", table_name="email_verification_otps")
    op.drop_table("email_verification_otps")
    op.drop_column("users", "profile_picture")
