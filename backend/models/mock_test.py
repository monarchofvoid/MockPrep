"""MockTest and AIMockQuestion models — unchanged from v0.11."""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.base import Base

class MockTest(Base):
    __tablename__ = "mock_tests"
    id               = Column(String(100), primary_key=True)
    exam             = Column(String(50), nullable=False)
    subject          = Column(String(100), nullable=False)
    year             = Column(String(20), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    total_marks      = Column(Float, nullable=False)
    question_count   = Column(Integer, nullable=False)
    json_file_path   = Column(String(300), nullable=True)
    is_ai_generated      = Column(Boolean, nullable=False, default=False)
    ai_generation_params = Column(JSON, nullable=True)
    ai_job_id            = Column(String(36), nullable=True)  # v2.0: link to AIJob
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    attempts     = relationship("Attempt", back_populates="mock_test")
    ai_questions = relationship("AIMockQuestion", back_populates="mock_test",
                                order_by="AIMockQuestion.position", cascade="all, delete-orphan")

class AIMockQuestion(Base):
    __tablename__ = "ai_mock_questions"
    id            = Column(Integer, primary_key=True, index=True)
    mock_id       = Column(String(100), ForeignKey("mock_tests.id", ondelete="CASCADE"), nullable=False)
    question_data = Column(JSON, nullable=False)
    position      = Column(Integer, nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    mock_test = relationship("MockTest", back_populates="ai_questions")
