"""UserProficiency model — unchanged from v0.11."""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.base import Base

class UserProficiency(Base):
    __tablename__ = "user_proficiency"
    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exam                = Column(String(50), nullable=False)
    subject             = Column(String(100), nullable=False)
    topic               = Column(String(100), nullable=False)
    subtopic            = Column(String(100), nullable=True)
    proficiency         = Column(Float, nullable=False, default=400.0)
    accuracy_rate       = Column(Float, nullable=False, default=0.0)
    attempt_rate        = Column(Float, nullable=False, default=0.0)
    avg_time_efficiency = Column(Float, nullable=False, default=1.0)
    correct_count       = Column(Integer, nullable=False, default=0)
    total_count         = Column(Integer, nullable=False, default=0)
    difficulty_easy_acc = Column(Float, nullable=False, default=0.0)
    difficulty_med_acc  = Column(Float, nullable=False, default=0.0)
    difficulty_hard_acc = Column(Float, nullable=False, default=0.0)
    last_updated        = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user = relationship("User")
