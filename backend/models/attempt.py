"""Attempt and Response models — unchanged from v0.11."""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.base import Base

class Attempt(Base):
    __tablename__ = "attempts"
    id                     = Column(Integer, primary_key=True, index=True)
    user_id                = Column(Integer, ForeignKey("users.id"), nullable=False)
    mock_id                = Column(String(100), ForeignKey("mock_tests.id"), nullable=False)
    score                  = Column(Float, nullable=True)
    total_marks            = Column(Float, nullable=True)
    correct_count          = Column(Integer, nullable=True)
    wrong_count            = Column(Integer, nullable=True)
    skipped_count          = Column(Integer, nullable=True)
    accuracy               = Column(Float, nullable=True)
    attempt_rate           = Column(Float, nullable=True)
    time_taken_seconds     = Column(Integer, nullable=True)
    avg_time_per_question  = Column(Float, nullable=True)
    started_at             = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at           = Column(DateTime(timezone=True), nullable=True)
    user      = relationship("User", back_populates="attempts")
    mock_test = relationship("MockTest", back_populates="attempts")
    responses = relationship("Response", back_populates="attempt", cascade="all, delete-orphan")

class Response(Base):
    __tablename__ = "responses"
    id                    = Column(Integer, primary_key=True, index=True)
    attempt_id            = Column(Integer, ForeignKey("attempts.id"), nullable=False)
    question_id           = Column(Integer, nullable=False)
    selected_option       = Column(String(1), nullable=True)
    is_correct            = Column(Boolean, nullable=True)
    marks_awarded         = Column(Float, default=0.0)
    time_spent_seconds    = Column(Integer, default=0)
    visit_count           = Column(Integer, default=0)
    answer_changed_count  = Column(Integer, default=0)
    was_marked_for_review = Column(Boolean, default=False)
    topic                 = Column(String(100), nullable=True)
    difficulty            = Column(String(20), nullable=True)
    subtopic              = Column(String(100), nullable=True)
    question_category     = Column(String(50), nullable=True)
    estimated_time_sec    = Column(Integer, nullable=True)
    time_efficiency_ratio = Column(Float, nullable=True)
    attempt = relationship("Attempt", back_populates="responses")
