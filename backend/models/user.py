"""
VYAS v2.0 — User Models
=========================
v2.0 changes:
  - hashed_password nullable (required for Google OAuth users)
  - Added: wallet relationship, ai_jobs relationship, payment_orders relationship
  - Added: OAuthAccount model for Google OAuth
  - Added: profile_completeness_percent property
  - Added: last_login_at, has_seen_premium_popup fields to User

v2.1 changes (Feature Additions):
  - Added: profile_picture column (stores Google profile photo URL for OAuth users)
  - Added: EmailVerificationOTP model for the two-step signup OTP flow
    The OTP model stores pending registration data BEFORE the user record is
    created. The user is only inserted into the users table once the OTP is
    validated successfully. This guarantees that unverified emails never
    pollute the users table.
"""

import hashlib

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.base import Base


class User(Base):
    """
    Core user authentication record.

    v2.0: hashed_password is nullable to support Google OAuth users
    who never set a password. A User with hashed_password=None can only
    authenticate via OAuth (not password login).
    """
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(100), nullable=False)
    email           = Column(String(200), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=True)  # v2.0: nullable for OAuth
    is_active       = Column(Boolean, default=True, nullable=False)

    # v2.0 additions
    last_login_at           = Column(DateTime(timezone=True), nullable=True)
    has_seen_premium_popup  = Column(Boolean, default=False, nullable=False)
    email_verified          = Column(Boolean, default=False, nullable=False)

    # v2.1 addition — Google profile photo URL for OAuth users; None for traditional users
    profile_picture = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Auth relationships
    refresh_tokens  = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    oauth_accounts  = relationship(
        "OAuthAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Profile
    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Financial
    wallet = relationship(
        "Wallet",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    payment_orders = relationship(
        "PaymentOrder",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Test engine
    attempts = relationship("Attempt", back_populates="user")

    # AI Jobs
    ai_jobs = relationship(
        "AIJob",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class OAuthAccount(Base):
    """
    Links a VYAS user to an OAuth provider account (Google, etc.).
    One user can have multiple OAuth accounts (e.g., link Google + Apple).
    """
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
        Index("ix_oauth_accounts_user_id", "user_id"),
    )

    id                   = Column(Integer, primary_key=True, index=True)
    user_id              = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider             = Column(String(30), nullable=False)      # "google", "apple"
    provider_account_id  = Column(String(100), nullable=False)     # Google sub claim
    provider_email       = Column(String(200), nullable=True)
    access_token         = Column(Text, nullable=True)
    refresh_token        = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="oauth_accounts")


class EmailVerificationOTP(Base):
    """
    Holds a pending signup registration + OTP before the user record is created.

    The flow:
      1. User submits name, email, password on the signup form.
      2. Backend saves these here (with hashed password), generates a 6-digit OTP,
         hashes it, stores the hash, and emails the raw OTP to the user.
      3. User enters the OTP on the verification screen.
      4. Backend looks up the record by email, verifies the OTP hash.
      5. On success: creates the User, Wallet, signup bonus → deletes this row.
      6. OTP expires after 10 minutes. Expired rows are ignored (and deleted on
         the next attempt for that email, or by a periodic cleanup task).

    Security properties:
      - OTP is hashed (bcrypt) before storage — same as passwords.
      - Max 5 verification attempts before the row is deleted (brute-force guard).
      - Resend is rate-limited to 3 times per session (stored in resend_count).
      - UniqueConstraint on email ensures only one pending OTP per address.
      - Raw OTP is never stored.
    """
    __tablename__ = "email_verification_otps"

    id               = Column(Integer, primary_key=True, index=True)
    email            = Column(String(200), nullable=False, unique=True, index=True)
    name             = Column(String(100), nullable=False)
    hashed_password  = Column(String(200), nullable=False)
    otp_hash         = Column(String(200), nullable=False)
    expires_at       = Column(DateTime(timezone=True), nullable=False)
    attempts         = Column(Integer, nullable=False, default=0)
    resend_count     = Column(Integer, nullable=False, default=0)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())


class UserProfile(Base):
    """
    One-to-one extension of User for exam preferences and personalization.

    v2.0: profile_completeness_percent is computed from required fields.
    Required for v2.0 gating: preparing_exam is required before 2nd AI mock.
    """
    __tablename__ = "user_profiles"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    preparing_exam  = Column(String(50),  nullable=True)
    target_year     = Column(Integer,     nullable=True)
    subject_focus   = Column(String(200), nullable=True)
    avatar          = Column(String(50),  nullable=True)
    daily_goal_mins = Column(Integer,     nullable=True, default=60)
    bio             = Column(String(300), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="profile")

    @property
    def completeness_percent(self) -> int:
        """
        Profile completeness as 0–100.
        Required fields: preparing_exam, target_year, avatar
        Optional fields: subject_focus, daily_goal_mins, bio
        """
        fields = {
            "preparing_exam": (self.preparing_exam, 40),    # most important
            "target_year":    (self.target_year, 20),
            "avatar":         (self.avatar, 10),
            "subject_focus":  (self.subject_focus, 15),
            "bio":            (self.bio, 15),
        }
        total = sum(weight for _, (val, weight) in fields.items() if val)
        return min(100, total)

    @property
    def is_complete_for_ai(self) -> bool:
        """preparing_exam is required before gated AI features."""
        return bool(self.preparing_exam)


class RefreshToken(Base):
    """
    v2.0: Server-side refresh token storage.
    Enables revocation (logout), rotation, and per-device tracking.
    Token value is never stored — only SHA-256 hash.
    """
    __tablename__ = "refresh_tokens"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash  = Column(String(64), unique=True, nullable=False, index=True)
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at  = Column(DateTime(timezone=True), nullable=True)
    user_agent  = Column(String(300), nullable=True)
    ip_address  = Column(String(45), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def revoke(self) -> None:
        from datetime import datetime, timezone
        self.revoked_at = datetime.now(timezone.utc)


class LoginAttempt(Base):
    """v2.0: Tracks login attempts for brute-force protection."""
    __tablename__ = "login_attempts"

    id           = Column(Integer, primary_key=True, index=True)
    email        = Column(String(200), nullable=False, index=True)
    ip_address   = Column(String(45), nullable=True)
    success      = Column(Boolean, nullable=False, default=False)
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())


class PasswordReset(Base):
    """
    Password reset tokens.
    
    Security:
      - token_hash stored (SHA-256), never the raw token
      - Tokens expire after 1 hour
      - One-time use only (verified then deleted)
    """
    __tablename__ = "password_resets"

    id         = Column(String(36), primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 hash
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Hash a reset token using SHA-256 (same as refresh tokens)."""
        return hashlib.sha256(raw_token.encode()).hexdigest()

# ── Backward-compat aliases ───────────────────────────────────────────────────
# otp_service.py imports PendingOTP but the class was renamed EmailVerificationOTP
# during the v2.0 security overhaul. Alias keeps the service import working
# without touching 8 call sites inside otp_service.py.
PendingOTP = EmailVerificationOTP