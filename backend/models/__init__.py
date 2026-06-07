"""
VYAS v2.0 — Models Package
=============================
Import all models here so:
  1. Alembic detects them all via `target_metadata`
  2. `models.Base.metadata.create_all()` creates all tables
  3. SQLAlchemy relationship() references work correctly

Import order matters — referenced tables must be imported before
tables that reference them via ForeignKey.
"""

from models.base import Base

# Core Auth models
from models.user import User, UserProfile, RefreshToken, LoginAttempt, PasswordReset

# Financial models
from models.wallet import Wallet, CreditLedger, FeaturePricing, LedgerEntryType
from models.payment import CreditPlan, PaymentOrder, PaymentWebhookLog, PaymentOrderStatus

# AI models
from models.ai_job import AIJob, AIJobStatus

# Test engine models
from models.mock_test import MockTest, AIMockQuestion
from models.attempt import Attempt, Response
from models.proficiency import UserProficiency
from models.tutor import TutorCache, TutorInteraction

__all__ = [
    # Base
    "Base",
    # Auth
    "User", "UserProfile", "RefreshToken", "LoginAttempt", "PasswordReset",
    # Financial
    "Wallet", "CreditLedger", "FeaturePricing", "LedgerEntryType",
    "CreditPlan", "PaymentOrder", "PaymentWebhookLog", "PaymentOrderStatus",
    # AI Jobs
    "AIJob", "AIJobStatus",
    # Test Engine
    "MockTest", "AIMockQuestion",
    "Attempt", "Response",
    "UserProficiency",
    "TutorCache", "TutorInteraction",
]
