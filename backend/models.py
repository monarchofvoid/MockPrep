from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attempts = relationship("Attempt", back_populates="user")


class MockTest(Base):
    __tablename__ = "mock_tests"

    id = Column(String(100), primary_key=True)   # e.g. "dbms_pyq_2021"
    exam = Column(String(50), nullable=False)     # "GATE"
    subject = Column(String(100), nullable=False) # "DBMS"
    year = Column(String(20), nullable=False)     # "2021"
    duration_minutes = Column(Integer, nullable=False)
    total_marks = Column(Float, nullable=False)
    question_count = Column(Integer, nullable=False)
    json_file_path = Column(String(300), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attempts = relationship("Attempt", back_populates="mock_test")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mock_id = Column(String(100), ForeignKey("mock_tests.id"), nullable=False)

    # Evaluation results (populated on submit)
    score = Column(Float, nullable=True)
    total_marks = Column(Float, nullable=True)
    correct_count = Column(Integer, nullable=True)
    wrong_count = Column(Integer, nullable=True)
    skipped_count = Column(Integer, nullable=True)
    accuracy = Column(Float, nullable=True)       # correct / attempted * 100
    attempt_rate = Column(Float, nullable=True)   # attempted / total * 100
    time_taken_seconds = Column(Integer, nullable=True)
    avg_time_per_question = Column(Float, nullable=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="attempts")
    mock_test = relationship("MockTest", back_populates="attempts")
    responses = relationship("Response", back_populates="attempt", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=False)
    question_id = Column(Integer, nullable=False)

    # What the user did
    selected_option = Column(String(1), nullable=True)   # "A" / "B" / "C" / "D" / None
    is_correct = Column(Boolean, nullable=True)
    marks_awarded = Column(Float, default=0.0)

    # Tracking data (from frontend)
    time_spent_seconds = Column(Integer, default=0)
    visit_count = Column(Integer, default=0)
    answer_changed_count = Column(Integer, default=0)
    was_marked_for_review = Column(Boolean, default=False)

    # Topic/difficulty (denormalised for faster analytics)
    topic = Column(String(100), nullable=True)
    difficulty = Column(String(20), nullable=True)

    attempt = relationship("Attempt", back_populates="responses")
