"""
VYAS v2.2.0 — AI Mock Generation Router
========================================
v2.2.0 Migration: Celery → asyncio.create_task

Changes from v2.1.5:
  1. create_mock_test() converted from `def` to `async def`.
     Required because service.enqueue_job() calls asyncio.create_task(), which
     requires a running event loop. FastAPI async endpoints always run in the
     event loop; sync endpoints do not.

  2. Error message updated: "Celery dispatch FAILED" → "Task dispatch FAILED".

All security hardening from v2.1.5 is fully preserved and unchanged.
"""

import logging
import re
import traceback

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.config import get_settings
from core.exceptions import (
    AIJobAlreadyActiveError,
    AIJobNotFoundError,
    InsufficientCreditsError,
    ProfileIncompleteError,
)
from database import get_db
from middleware.rate_limit import ai_rate_limit
from models.user import User
from schemas.ai_mock import (
    AIJobStatusResponse,
    CancelJobResponse,
    CreateMockTestRequest,
    CreateMockTestResponse,
)
from services.ai_job_service import AIJobService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/mock-tests", tags=["AI Mock Tests"])
ai_jobs_router = APIRouter(prefix="/api/v1/ai-jobs", tags=["AI Jobs"])

_JOB_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def _validate_job_id(job_id: str, param_name: str = "job_id") -> str:
    if not _JOB_ID_PATTERN.match(job_id):
        raise HTTPException(status_code=400, detail=f"Invalid {param_name} format.")
    return job_id


# ── Create Mock Test (Start AI Job) ──────────────────────────────────────────

@router.post("/generate", response_model=CreateMockTestResponse, status_code=202)
async def create_mock_test(
    body: CreateMockTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(ai_rate_limit),
):
    """
    Start an asynchronous AI mock test generation job.
    Deducts credits atomically. Returns job_id for status polling.

    v2.2.0: Endpoint is now `async def` to support asyncio.create_task() in
    service.enqueue_job(). Returns HTTP 202 immediately; AI generation runs
    concurrently as an asyncio task in the event loop.
    """
    service = AIJobService(db)

    try:
        job, cost_microcredits = service.create_job_with_deduction(
            user_id=current_user.id,
            exam=body.exam_type,
            subject=body.subject,
            difficulty=body.difficulty,
            question_count=body.num_questions,
        )
        db.commit()

    except AIJobAlreadyActiveError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "active_job_exists",
                "message": exc.message,
                "existing_job_id": exc.details.get("existing_job_id"),
            },
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "message": exc.message,
                "available_credits": exc.details.get("available_credits"),
                "required_credits": exc.details.get("required_credits"),
            },
        )
    except ProfileIncompleteError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "profile_incomplete",
                "message": exc.message,
                "missing_fields": exc.details.get("missing_fields", []),
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(
            "create_mock_test FAILED: user_id=%s subject=%s error=%s\n%s",
            current_user.id, body.subject, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to start mock test generation. Please try again.",
        )

    # v2.2.0: enqueue_job() calls asyncio.create_task(_run_ai_generation()).
    # Returns immediately; generation runs in background event loop.
    try:
        service.enqueue_job(job)
    except Exception as exc:
        db.rollback()
        logger.error(
            "Task dispatch FAILED for job_id=%s: %s\n%s",
            job.id, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=503,
            detail="AI generation service temporarily unavailable. Please try again in a moment.",
        )

    logger.info(
        "AI mock job created: job_id=%s user_id=%s subject=%s questions=%s",
        job.id, current_user.id, body.subject, body.num_questions,
    )
    return CreateMockTestResponse(
        job_id=job.id,
        status=job.status.value,
        estimated_seconds=body.num_questions * 4,
        credits_deducted=cost_microcredits // 100 if cost_microcredits else None,
    )


# ── Job Status Polling ────────────────────────────────────────────────────────


def _derive_progress_message(job) -> str:
    """
    BUG FIX: AIJob model has no progress_message column.
    Derive a human-readable status string from job.status and job.progress_percent.
    """
    status = job.status.value if hasattr(job.status, "value") else str(job.status)
    pct = job.progress_percent or 0
    messages = {
        "pending":   "Waiting to start…",
        "queued":    "Queued for generation…",
        "running":   f"Generating questions… ({pct}%)",
        "completed": "Generation complete.",
        "failed":    job.error_message or "Generation failed.",
        "cancelled": "Cancelled.",
    }
    return messages.get(status, f"Status: {status}")


@ai_jobs_router.get("/{job_id}", response_model=AIJobStatusResponse)
def get_job_status(
    job_id: str = Path(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll job status. Returns progress and result when complete."""
    _validate_job_id(job_id)
    service = AIJobService(db)

    try:
        job = service.get_job(job_id=job_id, user_id=current_user.id)
    except AIJobNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found.")

    return AIJobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        mock_test_id=job.result_mock_id,
        progress_message=_derive_progress_message(job),
    )


@ai_jobs_router.get("/{job_id}/result")
def get_job_result(
    job_id: str = Path(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full result of a completed AI job."""
    _validate_job_id(job_id)
    service = AIJobService(db)

    try:
        job = service.get_job(job_id=job_id, user_id=current_user.id)
    except AIJobNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status.value in ("pending", "queued", "running"):
        raise HTTPException(status_code=202, detail="Job is still processing.")

    if job.status.value == "failed":
        raise HTTPException(
            status_code=422,
            detail={"error": "job_failed", "message": job.error_message or "Generation failed."},
        )

    if not job.result_mock_id:
        raise HTTPException(status_code=404, detail="Result not available yet.")

    try:
        result = service.get_job_result(job_id=job_id, user_id=current_user.id)
    except AIJobNotFoundError:
        raise HTTPException(status_code=404, detail="Result not found.")
    except Exception as exc:
        logger.error(
            "get_job_result FAILED: job_id=%s user_id=%s error=%s\n%s",
            job_id, current_user.id, exc, traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve job result.")

    return result


# ── Cancel Job ────────────────────────────────────────────────────────────────

@ai_jobs_router.delete("/{job_id}", response_model=CancelJobResponse)
def cancel_job(
    job_id: str = Path(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending or processing AI job. Issues a credit refund."""
    _validate_job_id(job_id)
    service = AIJobService(db)

    try:
        result = service.cancel_job(job_id=job_id, user_id=current_user.id)
        db.commit()
    except AIJobNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        logger.error(
            "cancel_job FAILED: job_id=%s user_id=%s error=%s\n%s",
            job_id, current_user.id, exc, traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail="Failed to cancel job.")

    return CancelJobResponse(
        job_id=job_id,
        cancelled=result.get("cancelled", True),
        refunded_credits=result.get("refunded_credits"),
    )


# ── List Active Jobs ──────────────────────────────────────────────────────────

@ai_jobs_router.get("/", response_model=list[AIJobStatusResponse])
def list_my_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all AI jobs for the current user (most recent first)."""
    service = AIJobService(db)
    jobs = service.list_jobs(user_id=current_user.id)
    return [
        AIJobStatusResponse(
            job_id=j.id,
            status=j.status.value,
            created_at=j.created_at,
            completed_at=j.completed_at,
            error_message=j.error_message,
            mock_test_id=j.result_mock_id,
            progress_message=_derive_progress_message(j),
        )
        for j in jobs
    ]