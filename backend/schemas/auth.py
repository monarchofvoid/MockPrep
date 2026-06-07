"""VYAS v2.1 — Auth Schemas

v2.1 additions:
  - InitiateSignupRequest: step 1 of the new two-step signup flow
  - VerifyOTPRequest: step 2 — user submits 6-digit OTP
  - InitiateSignupResponse: tells the frontend the OTP was sent
  - ResendOTPRequest: user asks for a fresh OTP
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class SignupRequest(BaseModel):
    """
    PRESERVED — used by authStore.signup() and existing tests.
    In the new two-step flow the frontend still constructs this shape;
    the router now sends the OTP before creating the user.
    """
    name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class InitiateSignupRequest(BaseModel):
    """
    Step 1 of the new email-verified signup flow.
    Identical shape to SignupRequest — kept as a separate class so the
    two-step endpoint can be annotated clearly in the docs.
    """
    name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class InitiateSignupResponse(BaseModel):
    """Returned by POST /auth/signup/initiate."""
    message: str        # "Verification code sent to <email>"
    email: str          # echoed back so the frontend can display it
    expires_in_seconds: int  # countdown for the frontend timer (600 = 10 min)


class VerifyOTPRequest(BaseModel):
    """Step 2 — user enters the 6-digit code from the email."""
    email: EmailStr
    otp: str

    @field_validator("otp")
    @classmethod
    def otp_six_digits(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("OTP must be exactly 6 digits")
        return v


class ResendOTPRequest(BaseModel):
    """Triggers a fresh OTP for an in-progress signup."""
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserProfileOut(BaseModel):
    preparing_exam: Optional[str] = None
    target_year: Optional[int] = None
    subject_focus: Optional[str] = None
    avatar: Optional[str] = None
    daily_goal_mins: Optional[int] = None
    bio: Optional[str] = None


class WalletSnapshotOut(BaseModel):
    balance_microcredits: int
    balance_credits: float


class UserMeResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime
    has_seen_premium_popup: bool
    profile: Optional[UserProfileOut] = None
    profile_completeness_percent: int = 0
    wallet: Optional[WalletSnapshotOut] = None
    low_credit_warning: bool = False
    # v2.1: profile picture from Google OAuth
    profile_picture: Optional[str] = None
    # Included on login/signup/refresh; omitted (None) on GET /auth/me
    access_token: Optional[str] = None


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v
