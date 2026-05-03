from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


# ── Password Reset ─────────────────────────────────────────────────────────────

class PasswordReset(Base):
    """
    Stores hashed one-time password-reset tokens.

    Security design:
      • token column holds SHA-256(raw_token) — the raw token is only ever
        emailed and never persisted.
      • ON DELETE CASCADE ensures cleanup when a user is deleted.
      • expires_at enforces a 15-minute window.
      • Records are deleted immediately on successful use (one-time tokens).
    """
    __tablename__ = "password_resets"

    # Use String(36) for cross-DB compat (SQLite + PostgreSQL)
    id         = Column(String(36), primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token      = Column(Text, nullable=False)                        # SHA-256 hash
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class User(Base):
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String(100), nullable=False)
    email            = Column(String(200), unique=True, index=True, nullable=False)
    hashed_password  = Column(String(200), nullable=False)
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    attempts = relationship("Attempt", back_populates="user")


class MockTest(Base):
    __tablename__ = "mock_tests"

    id             = Column(String(100), primary_key=True)   # e.g. "dbms_pyq_2021"
    exam           = Column(String(50), nullable=False)      # "GATE"
    subject        = Column(String(100), nullable=False)     # "DBMS"
    year           = Column(String(20), nullable=False)      # "2021"
    duration_minutes = Column(Integer, nullable=False)
    total_marks    = Column(Float, nullable=False)
    question_count = Column(Integer, nullable=False)
    json_file_path = Column(String(300), nullable=True)      # NULL for AI-generated mocks

    # ── Phase 2B: AI mock flags ───────────────────────────────────────────────
    is_ai_generated      = Column(Boolean, nullable=False, default=False)
    ai_generation_params = Column(JSON,    nullable=True)    # audit/history payload

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attempts    = relationship("Attempt", back_populates="mock_test")
    ai_questions = relationship("AIMockQuestion", back_populates="mock_test",
                                order_by="AIMockQuestion.position",
                                cascade="all, delete-orphan")


# ── Phase 2B: AI Mock Question Storage ────────────────────────────────────────

class AIMockQuestion(Base):
    """
    Stores one question per row for AI-generated mocks.
    question_data is a JSONB blob that exactly matches the QuestionRenderer schema.
    Position is 1-based; questions are ordered by position when served.
    """
    __tablename__ = "ai_mock_questions"

    id            = Column(Integer, primary_key=True, index=True)
    mock_id       = Column(String(100), ForeignKey("mock_tests.id", ondelete="CASCADE"), nullable=False)
    question_data = Column(JSON,    nullable=False)   # full MCQ object
    position      = Column(Integer, nullable=False)   # 1-based ordering
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    mock_test = relationship("MockTest", back_populates="ai_questions")


class Attempt(Base):
    __tablename__ = "attempts"

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mock_id = Column(String(100), ForeignKey("mock_tests.id"), nullable=False)

    # Evaluation results (populated on submit)
    score                  = Column(Float, nullable=True)
    total_marks            = Column(Float, nullable=True)
    correct_count          = Column(Integer, nullable=True)
    wrong_count            = Column(Integer, nullable=True)
    skipped_count          = Column(Integer, nullable=True)
    accuracy               = Column(Float, nullable=True)   # correct / attempted * 100
    attempt_rate           = Column(Float, nullable=True)   # attempted / total * 100
    time_taken_seconds     = Column(Integer, nullable=True)
    avg_time_per_question  = Column(Float, nullable=True)

    started_at   = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    user      = relationship("User", back_populates="attempts")
    mock_test = relationship("MockTest", back_populates="attempts")
    responses = relationship("Response", back_populates="attempt", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "responses"

    id         = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=False)
    question_id = Column(Integer, nullable=False)

    # What the user did
    selected_option = Column(String(1), nullable=True)   # "A" / "B" / "C" / "D" / None
    is_correct      = Column(Boolean, nullable=True)
    marks_awarded   = Column(Float, default=0.0)

    # Tracking data (from frontend)
    time_spent_seconds    = Column(Integer, default=0)
    visit_count           = Column(Integer, default=0)
    answer_changed_count  = Column(Integer, default=0)
    was_marked_for_review = Column(Boolean, default=False)

    # Topic/difficulty (denormalised for faster analytics)
    topic      = Column(String(100), nullable=True)
    difficulty = Column(String(20), nullable=True)

    # ── Phase 0: Enhanced response tracking ───────────────────────────────────
    # Captures granular signals from question JSON for richer analytics and
    # the Phase 1 proficiency engine. All columns are nullable — existing rows
    # have NULL here, new submissions populate them from question JSON.
    subtopic              = Column(String(100), nullable=True)
    question_category     = Column(String(50),  nullable=True)   # conceptual/numerical/application/analytical
    estimated_time_sec    = Column(Integer,      nullable=True)   # from question JSON
    time_efficiency_ratio = Column(Float,        nullable=True)   # actual / estimated (None if estimated missing)

    attempt = relationship("Attempt", back_populates="responses")


# ── Phase 1: User Proficiency Model ───────────────────────────────────────────

class UserProficiency(Base):
    """
    One row per (user, exam, subject, topic) combination.
    ELO-like proficiency score, updated after every submission via BackgroundTask.
    Read by GET /tutor/proficiency and (Phase 2A) tutor explain endpoint.
    """
    __tablename__ = "user_proficiency"

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Scope
    exam     = Column(String(50),  nullable=False)
    subject  = Column(String(100), nullable=False)
    topic    = Column(String(100), nullable=False)
    subtopic = Column(String(100), nullable=True)

    # ELO-like score: 0–1000, default 400 (Intermediate start)
    proficiency = Column(Float, nullable=False, default=400.0)

    # Derived analytics
    accuracy_rate       = Column(Float,   nullable=False, default=0.0)
    attempt_rate        = Column(Float,   nullable=False, default=0.0)
    avg_time_efficiency = Column(Float,   nullable=False, default=1.0)

    # Raw counts (required for correct incremental average computation)
    correct_count = Column(Integer, nullable=False, default=0)
    total_count   = Column(Integer, nullable=False, default=0)

    # Per-difficulty running accuracy (0.0–1.0)
    difficulty_easy_acc = Column(Float, nullable=False, default=0.0)
    difficulty_med_acc  = Column(Float, nullable=False, default=0.0)
    difficulty_hard_acc = Column(Float, nullable=False, default=0.0)

    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")


# ── Phase 2A: Tutor Cache ──────────────────────────────────────────────────────

class TutorCache(Base):
    """
    Cached Gemini explanations keyed by SHA-256(question_id:bucket:answer:correct).
    Shared across users in the same proficiency cohort — AI costs plateau fast.
    TTL: 7 days, enforced by expires_at check in services/tutor.py.
    """
    __tablename__ = "tutor_cache"

    id                 = Column(Integer, primary_key=True, index=True)
    cache_key          = Column(String(64), unique=True, nullable=False)   # SHA-256 hex
    question_id        = Column(Integer,    nullable=False)
    exam               = Column(String(50), nullable=True)
    proficiency_bucket = Column(String(20), nullable=False)   # Beginner/Intermediate/Advanced/Expert
    user_answer        = Column(String(1),  nullable=True)    # NULL = skipped
    correct_answer     = Column(String(1),  nullable=False)
    explanation_json   = Column(JSON,       nullable=False)   # Parsed Gemini response dict
    created_at         = Column(DateTime(timezone=True), server_default=func.now())
    expires_at         = Column(DateTime(timezone=True), nullable=False)
    hit_count          = Column(Integer,    nullable=False, default=0)


# ── Phase 2A: Tutor Interaction Log ───────────────────────────────────────────

class TutorInteraction(Base):
    """
    One row per /tutor/explain call.
    Records proficiency at time of call, cache hit, and optional 1–5 star rating.
    """
    __tablename__ = "tutor_interactions"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id",    ondelete="CASCADE"), nullable=False)
    attempt_id          = Column(Integer, ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False)
    question_id         = Column(Integer, nullable=False)
    proficiency_at_time = Column(Float,   nullable=True)
    was_cache_hit       = Column(Boolean, nullable=False, default=False)
    user_rating         = Column(Integer, nullable=True)   # 1–5 stars

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user    = relationship("User")
    attempt = relationship("Attempt")