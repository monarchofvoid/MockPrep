"""TutorCache and TutorInteraction models — unchanged from v0.11."""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.base import Base

class TutorCache(Base):
    __tablename__ = "tutor_cache"
    id                 = Column(Integer, primary_key=True, index=True)
    cache_key          = Column(String(64), unique=True, nullable=False)
    question_id        = Column(Integer, nullable=False)
    exam               = Column(String(50), nullable=True)
    proficiency_bucket = Column(String(20), nullable=False)
    user_answer        = Column(String(1), nullable=True)
    correct_answer     = Column(String(1), nullable=False)
    explanation_json   = Column(JSON, nullable=False)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())
    expires_at         = Column(DateTime(timezone=True), nullable=False)
    hit_count          = Column(Integer, nullable=False, default=0)

class TutorInteraction(Base):
    __tablename__ = "tutor_interactions"
    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    attempt_id          = Column(Integer, ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False)
    question_id         = Column(Integer, nullable=False)
    proficiency_at_time = Column(Float, nullable=True)
    was_cache_hit       = Column(Boolean, nullable=False, default=False)
    user_rating         = Column(Integer, nullable=True)
    credit_ledger_entry_id = Column(Integer, ForeignKey("credit_ledger.id"), nullable=True)  # v2.0
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    user    = relationship("User")
    attempt = relationship("Attempt")
