"""
VYAS v0.6 — SQLAlchemy Models
================================
Changes vs v0.5:
  D2: Added UserProfile model (exam preference, avatar, daily goals, target year)
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id         = Column(String(36), primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token      = Column(Text, nullable=False)
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
    profile  = relationship("UserProfile", back_populates="user", uselist=False,
                            cascade="all, delete-orphan")


class UserProfile(Base):
    """
    D2: One-to-one extension of User for exam preferences and personalisation.
    Created lazily on first profile save — not required for auth or testing.
    """
    __tablename__ = "user_profiles"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                             unique=True, nullable=False)

    # Exam & study preferences
    preparing_exam  = Column(String(50),  nullable=True)   # e.g. "CUET", "GATE", "JEE"
    target_year     = Column(Integer,     nullable=True)   # e.g. 2026
    subject_focus   = Column(String(200), nullable=True)   # comma-separated subjects

    # Personal customisation
    avatar          = Column(String(50),  nullable=True)   # avatar code, e.g. "owl"
    daily_goal_mins = Column(Integer,     nullable=True, default=60)  # minutes per day

    # Bio / motivation
    bio             = Column(String(300), nullable=True)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(),
                         onupdate=func.now())

    user = relationship("User", back_populates="profile")


class MockTest(Base):
    __tablename__ = "mock_tests"

    id               = Column(String(100), primary_key=True)
    exam             = Column(String(50),  nullable=False)
    subject          = Column(String(100), nullable=False)
    year             = Column(String(20),  nullable=False)
    duration_minutes = Column(Integer,     nullable=False)
    total_marks      = Column(Float,       nullable=False)
    question_count   = Column(Integer,     nullable=False)
    json_file_path   = Column(String(300), nullable=True)

    is_ai_generated      = Column(Boolean, nullable=False, default=False)
    ai_generation_params = Column(JSON,    nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attempts     = relationship("Attempt", back_populates="mock_test")
    ai_questions = relationship("AIMockQuestion", back_populates="mock_test",
                                order_by="AIMockQuestion.position",
                                cascade="all, delete-orphan")


class AIMockQuestion(Base):
    __tablename__ = "ai_mock_questions"

    id            = Column(Integer, primary_key=True, index=True)
    mock_id       = Column(String(100), ForeignKey("mock_tests.id", ondelete="CASCADE"), nullable=False)
    question_data = Column(JSON,    nullable=False)
    position      = Column(Integer, nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    mock_test = relationship("MockTest", back_populates="ai_questions")


class Attempt(Base):
    __tablename__ = "attempts"

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mock_id = Column(String(100), ForeignKey("mock_tests.id"), nullable=False)

    score                  = Column(Float,   nullable=True)
    total_marks            = Column(Float,   nullable=True)
    correct_count          = Column(Integer, nullable=True)
    wrong_count            = Column(Integer, nullable=True)
    skipped_count          = Column(Integer, nullable=True)
    accuracy               = Column(Float,   nullable=True)
    attempt_rate           = Column(Float,   nullable=True)
    time_taken_seconds     = Column(Integer, nullable=True)
    avg_time_per_question  = Column(Float,   nullable=True)

    started_at   = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    user      = relationship("User", back_populates="attempts")
    mock_test = relationship("MockTest", back_populates="attempts")
    responses = relationship("Response", back_populates="attempt", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "responses"

    id          = Column(Integer, primary_key=True, index=True)
    attempt_id  = Column(Integer, ForeignKey("attempts.id"), nullable=False)
    question_id = Column(Integer, nullable=False)

    selected_option = Column(String(1), nullable=True)
    is_correct      = Column(Boolean,   nullable=True)
    marks_awarded   = Column(Float,     default=0.0)

    time_spent_seconds    = Column(Integer, default=0)
    visit_count           = Column(Integer, default=0)
    answer_changed_count  = Column(Integer, default=0)
    was_marked_for_review = Column(Boolean, default=False)

    topic      = Column(String(100), nullable=True)
    difficulty = Column(String(20),  nullable=True)

    subtopic              = Column(String(100), nullable=True)
    question_category     = Column(String(50),  nullable=True)
    estimated_time_sec    = Column(Integer,      nullable=True)
    time_efficiency_ratio = Column(Float,        nullable=True)

    attempt = relationship("Attempt", back_populates="responses")


class UserProficiency(Base):
    __tablename__ = "user_proficiency"

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    exam     = Column(String(50),  nullable=False)
    subject  = Column(String(100), nullable=False)
    topic    = Column(String(100), nullable=False)
    subtopic = Column(String(100), nullable=True)

    proficiency = Column(Float, nullable=False, default=400.0)

    accuracy_rate       = Column(Float,   nullable=False, default=0.0)
    attempt_rate        = Column(Float,   nullable=False, default=0.0)
    avg_time_efficiency = Column(Float,   nullable=False, default=1.0)

    correct_count = Column(Integer, nullable=False, default=0)
    total_count   = Column(Integer, nullable=False, default=0)

    difficulty_easy_acc = Column(Float, nullable=False, default=0.0)
    difficulty_med_acc  = Column(Float, nullable=False, default=0.0)
    difficulty_hard_acc = Column(Float, nullable=False, default=0.0)

    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class TutorCache(Base):
    __tablename__ = "tutor_cache"

    id                 = Column(Integer,    primary_key=True, index=True)
    cache_key          = Column(String(64), unique=True, nullable=False)
    question_id        = Column(Integer,    nullable=False)
    exam               = Column(String(50), nullable=True)
    proficiency_bucket = Column(String(20), nullable=False)
    user_answer        = Column(String(1),  nullable=True)
    correct_answer     = Column(String(1),  nullable=False)
    explanation_json   = Column(JSON,       nullable=False)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())
    expires_at         = Column(DateTime(timezone=True), nullable=False)
    hit_count          = Column(Integer,    nullable=False, default=0)


class TutorInteraction(Base):
    __tablename__ = "tutor_interactions"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id",    ondelete="CASCADE"), nullable=False)
    attempt_id          = Column(Integer, ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False)
    question_id         = Column(Integer, nullable=False)
    proficiency_at_time = Column(Float,   nullable=True)
    was_cache_hit       = Column(Boolean, nullable=False, default=False)
    user_rating         = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user    = relationship("User")
    attempt = relationship("Attempt")
