"""
VYAS v2.0 — AI Job Model
==========================
Tracks the lifecycle of async AI mock generation jobs.

Job Lifecycle:
  PENDING   — job record created, not yet picked up by Celery
  QUEUED    — enqueued in Celery (Redis), worker not started yet
  RUNNING   — Celery worker is actively generating questions
  COMPLETED — generation successful, mock_id populated
  FAILED    — generation failed, refund issued
  REFUNDED  — credits refunded (terminal state after FAILED)
  CANCELLED — cancelled before worker picked it up

Credit Integration:
  - Credits are deducted BEFORE job is created (deduction_ledger_entry_id)
  - On failure: a refund ledger entry is created (refund_ledger_entry_id)
  - The job_id is stored in the ledger entry for full traceability

Idempotency:
  - Each job has a unique celery_task_id
  - Celery acks_late=True prevents task loss
  - Retry logic lives in the Celery task, not here
"""

import enum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SAEnum,
    Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.base import Base


class AIJobStatus(str, enum.Enum):
    PENDING   = "pending"    # Created in DB, not yet enqueued
    QUEUED    = "queued"     # Sent to Celery/Redis queue
    RUNNING   = "running"    # Worker actively processing
    COMPLETED = "completed"  # Done, mock_id populated
    FAILED    = "failed"     # Error, refund pending
    REFUNDED  = "refunded"   # Credits returned to wallet
    CANCELLED = "cancelled"  # Cancelled before worker picked up


class AIJob(Base):
    """
    Represents one async AI mock generation request.

    Each job deducts credits upfront and refunds on failure.
    Frontend polls /ai-jobs/{job_id}/status until completed or failed.
    Redis caches the status for fast polling without DB hits.
    """
    __tablename__ = "ai_jobs"
    __table_args__ = (
        Index("ix_ai_jobs_user_id", "user_id"),
        Index("ix_ai_jobs_status", "status"),
        Index("ix_ai_jobs_created_at", "created_at"),
        Index("ix_ai_jobs_celery_task_id", "celery_task_id"),
    )

    id              = Column(String(36), primary_key=True)  # UUID v4
    user_id         = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Job parameters (what to generate)
    exam            = Column(String(50), nullable=False)
    subject         = Column(String(100), nullable=False)
    difficulty      = Column(String(20), nullable=False)
    question_count  = Column(Integer, nullable=False)
    use_proficiency = Column(Boolean, default=True, nullable=False)

    # Credit tracking
    cost_microcredits           = Column(Integer, nullable=False)
    deduction_ledger_entry_id   = Column(
        Integer, ForeignKey("credit_ledger.id"), nullable=True
    )
    refund_ledger_entry_id      = Column(
        Integer, ForeignKey("credit_ledger.id"), nullable=True
    )

    # Celery integration
    celery_task_id  = Column(String(50), nullable=True, index=True)

    # Status tracking
    status = Column(
        SAEnum(AIJobStatus),
        default=AIJobStatus.PENDING,
        nullable=False,
    )

    # Progress (updated by Celery task, cached in Redis)
    progress_percent        = Column(Integer, default=0, nullable=False)
    questions_generated     = Column(Integer, default=0, nullable=False)

    # Result
    result_mock_id   = Column(String(100), nullable=True)   # MockTest.id when completed
    error_message    = Column(String(1000), nullable=True)
    attempt_count    = Column(Integer, default=0, nullable=False)

    # Timing
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    started_at    = Column(DateTime(timezone=True), nullable=True)
    completed_at  = Column(DateTime(timezone=True), nullable=True)
    failed_at     = Column(DateTime(timezone=True), nullable=True)

    # Generation metadata (set by worker, used for analytics)
    proficiency_score   = Column(Float, nullable=True)
    weak_topics_json    = Column(Text, nullable=True)  # JSON list

    # Relationships
    user                    = relationship("User", back_populates="ai_jobs")
    deduction_ledger_entry  = relationship(
        "CreditLedger",
        foreign_keys=[deduction_ledger_entry_id],
    )
    refund_ledger_entry     = relationship(
        "CreditLedger",
        foreign_keys=[refund_ledger_entry_id],
    )

    @property
    def is_terminal(self) -> bool:
        """True if the job is in a final state (no more status changes expected)."""
        return self.status in (
            AIJobStatus.COMPLETED,
            AIJobStatus.FAILED,
            AIJobStatus.REFUNDED,
            AIJobStatus.CANCELLED,
        )

    @property
    def cost_credits(self) -> float:
        """Display cost in credits. Display layer only."""
        return self.cost_microcredits / 100.0
