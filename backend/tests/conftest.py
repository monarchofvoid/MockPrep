"""
VYAS v2.2.0 — pytest Configuration
=====================================
v2.2.0 Changes:
  1. Added SCHEDULER_ENABLED=false to test environment defaults.
     This prevents APScheduler from starting during tests, which would
     try to connect to Redis and create apscheduler:* keys in the test
     Redis DB, potentially interfering with test isolation.

  2. Removed CELERY_BROKER_URL and CELERY_RESULT_BACKEND from defaults
     (these env vars no longer exist in the application).

  3. lru_cache cleared before tests to pick up the new SCHEDULER_ENABLED
     setting (config is cached via @lru_cache in core/config.py).

Preserved from v2.0.4:
  1. Auto-rewrites 'postgresql://' → 'postgresql+psycopg://'
  2. engine fixture uses inspect() to skip create_all when tables already exist.
  3. TEST_DATABASE_URL should NOT be set unless you have a local PostgreSQL.
"""

import os
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# ── Test environment defaults ──────────────────────────────────────────────────
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret_key_not_for_production")
os.environ.setdefault("REFRESH_SECRET_KEY", "test_refresh_secret_not_for_production")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("GROQ_API_KEY", "dummy_groq_key_for_tests")
os.environ.setdefault("RAZORPAY_KEY_ID", "rzp_test_dummy")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "dummy_razorpay_secret")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret_for_tests_only")
os.environ.setdefault("BREVO_API_KEY", "dummy_brevo_key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SIGNUP_BONUS_MICROCREDITS", "500")
os.environ.setdefault("MICROCREDITS_PER_CREDIT", "100")

# v2.2.0: Disable APScheduler in tests.
# This prevents scheduler from connecting to Redis and firing jobs during tests,
# which would interfere with test isolation and Redis key state.
os.environ["SCHEDULER_ENABLED"] = "false"

# Clear the lru_cache so the updated SCHEDULER_ENABLED=false is picked up.
# The cache may have been populated during a previous import before this file ran.
try:
    from core.config import get_settings
    get_settings.cache_clear()
except Exception:
    pass  # Module may not be importable yet at this point


# ── Resolve DB URL ─────────────────────────────────────────────────────────────
# Use TEST_DATABASE_URL if set, otherwise fall back to DATABASE_URL (Supabase).
# Auto-rewrite postgresql:// → postgresql+psycopg:// to use the psycopg v3
# driver that is already installed. psycopg2 is NOT installed in this project.
_raw_db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "")

def _fix_url(url: str) -> str:
    """Replace postgresql:// with postgresql+psycopg:// if not already set."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url

TEST_DB_URL = _fix_url(_raw_db_url)

# ── Model imports (after env vars set) ────────────────────────────────────────
from models.base import Base
from models.user import User
from models.wallet import Wallet, CreditLedger, LedgerEntryType
from models.payment import CreditPlan, PaymentOrder, PaymentOrderStatus as PaymentStatus
from database import get_db
from services.wallet_service import WalletService
from core.security import hash_password, create_access_token


# ── Engine fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    if not TEST_DB_URL:
        pytest.skip("No DATABASE_URL configured — skipping DB tests")

    eng = create_engine(TEST_DB_URL, echo=False)

    # Inspect the DB to check if schema already exists.
    # If tables exist (migrations were run) → skip create_all entirely.
    # If empty DB → create all tables so tests are self-contained.
    inspector = inspect(eng)
    existing_tables = set(inspector.get_table_names())

    _created = False
    if "users" not in existing_tables:
        Base.metadata.create_all(eng)
        _created = True

    yield eng

    # Only drop if we created the schema (never wipe a shared/prod DB)
    if _created:
        Base.metadata.drop_all(eng)


@pytest.fixture(scope="session")
def _SessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db(_SessionLocal):
    """
    Per-test session with SAVEPOINT rollback.
    No test data is ever committed — safe to run against Supabase.
    """
    session = _SessionLocal()
    session.begin_nested()
    yield session
    session.rollback()
    session.close()


# ── App client ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client(db):
    from main import create_app
    app = create_app()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Factories ──────────────────────────────────────────────────────────────────

@pytest.fixture
def make_user(db):
    _n = [0]
    def _make(name=None, email=None, password="TestPass123!",
              with_wallet=True, wallet_microcredits=1000, is_active=True):
        _n[0] += 1
        user = User(
            name=name or f"Test User {_n[0]}",
            email=email or f"testuser_{_n[0]}_{id(db)}@vyas.test",
            hashed_password=hash_password(password),
            is_active=is_active,
        )
        db.add(user)
        db.flush()
        if with_wallet:
            svc = WalletService(db)
            svc.create_wallet(user.id)
            if wallet_microcredits > 0:
                svc.grant_credits(
                    user_id=user.id,
                    amount_microcredits=wallet_microcredits,
                    entry_type=LedgerEntryType.SIGNUP_BONUS,
                    idempotency_key=f"test_bonus:{user.id}:{_n[0]}:{id(db)}",
                    description="Test setup bonus",
                )
            db.flush()
        return user
    return _make


@pytest.fixture
def make_auth_headers():
    def _make(user):
        token = create_access_token({"sub": str(user.id)})
        return {"Authorization": f"Bearer {token}"}
    return _make


@pytest.fixture
def make_credit_plan(db):
    _n = [0]
    def _make(name=None, amount_paise=9900, credits_granted=10, is_popular=False):
        _n[0] += 1
        plan = CreditPlan(
            name=name or f"Test Plan {_n[0]}",
            amount_paise=amount_paise,
            credits_granted=credits_granted,
            is_popular=is_popular,
            is_active=True,
            sort_order=_n[0],
        )
        db.add(plan)
        db.flush()
        return plan
    return _make