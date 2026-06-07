"""
VYAS v2.0 — Pydantic Schemas Package

Re-exports every schema so routers can do:
    import schemas
    schemas.UserProfileOut(...)   # etc.
"""

from schemas.auth import (
    SignupRequest,
    LoginRequest,
    UserOut,
    UserMeResponse,
    WalletSnapshotOut,
    TokenResponse,
    RefreshResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)

from schemas.profile import (
    UserProfileOut,
    UserProfileUpdate,
)

from schemas.tutor import (
    DifficultyProfile,
    TopicProficiency,
    UserProficiencyResponse,
    TutorExplainRequest,
    TutorExplanation,
    TutorExplainResponse,
    TutorRateRequest,
    TutorRateResponse,
)

from schemas.ai_mock import *   # noqa: F401,F403
from schemas.payment import *   # noqa: F401,F403
from schemas.wallet import *    # noqa: F401,F403

__all__ = [
    # auth
    "SignupRequest", "LoginRequest", "UserOut", "UserMeResponse",
    "WalletSnapshotOut", "TokenResponse", "RefreshResponse",
    "ForgotPasswordRequest", "ResetPasswordRequest",
    # profile
    "UserProfileOut", "UserProfileUpdate",
    # tutor / proficiency
    "DifficultyProfile", "TopicProficiency", "UserProficiencyResponse",
    "TutorExplainRequest", "TutorExplanation", "TutorExplainResponse",
    "TutorRateRequest", "TutorRateResponse",
]