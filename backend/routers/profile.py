"""
VYAS v0.6 — User Profile Router (NEW — D2)
===========================================
Endpoints:
  GET  /profile/me          — get own profile (or empty defaults)
  PUT  /profile/me          — create or update own profile
  GET  /profile/avatars     — list valid avatar codes

The profile is optional — users can use VYAS without ever setting one.
When no profile exists, GET returns sensible null defaults.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Profile"])

VALID_EXAMS = ("CUET", "GATE", "JEE", "UPSC", "NEET", "CAT", "OTHER")
VALID_AVATARS = (
    "owl", "fox", "bear", "cat",
    "robot", "astronaut", "penguin", "tiger",
)


@router.get("/me", response_model=schemas.UserProfileOut)
def get_my_profile(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the authenticated user's profile.
    If no profile has been created yet, returns empty defaults (HTTP 200).
    No 404 — profile is optional.
    """
    profile = (
        db.query(models.UserProfile)
        .filter_by(user_id=current_user.id)
        .first()
    )

    if profile is None:
        # Return empty defaults so the frontend can render the profile page
        return schemas.UserProfileOut(
            user_id         = current_user.id,
            preparing_exam  = None,
            target_year     = None,
            subject_focus   = None,
            avatar          = None,
            daily_goal_mins = 60,
            bio             = None,
            updated_at      = None,
        )

    return schemas.UserProfileOut(
        user_id         = current_user.id,
        preparing_exam  = profile.preparing_exam,
        target_year     = profile.target_year,
        subject_focus   = profile.subject_focus,
        avatar          = profile.avatar,
        daily_goal_mins = profile.daily_goal_mins,
        bio             = profile.bio,
        updated_at      = profile.updated_at,
    )


@router.put("/me", response_model=schemas.UserProfileOut)
def update_my_profile(
    body: schemas.UserProfileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create or update the authenticated user's profile (upsert).
    Validates exam and avatar values against allowed lists.
    """
    # ── Input validation ──────────────────────────────────────────────────────
    if body.preparing_exam is not None and body.preparing_exam not in VALID_EXAMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"preparing_exam must be one of: {', '.join(VALID_EXAMS)}",
        )

    if body.avatar is not None and body.avatar not in VALID_AVATARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"avatar must be one of: {', '.join(VALID_AVATARS)}",
        )

    if body.target_year is not None and not (2024 <= body.target_year <= 2035):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target_year must be between 2024 and 2035.",
        )

    if body.daily_goal_mins is not None and not (5 <= body.daily_goal_mins <= 720):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="daily_goal_mins must be between 5 and 720.",
        )

    if body.bio is not None and len(body.bio) > 300:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bio must be 300 characters or fewer.",
        )

    # ── Upsert profile ────────────────────────────────────────────────────────
    profile = (
        db.query(models.UserProfile)
        .filter_by(user_id=current_user.id)
        .first()
    )

    if profile is None:
        profile = models.UserProfile(user_id=current_user.id)
        db.add(profile)
        logger.info("Creating new profile for user_id=%s", current_user.id)
    else:
        logger.info("Updating profile for user_id=%s", current_user.id)

    # Only update fields that were explicitly sent (non-None)
    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return schemas.UserProfileOut(
        user_id         = current_user.id,
        preparing_exam  = profile.preparing_exam,
        target_year     = profile.target_year,
        subject_focus   = profile.subject_focus,
        avatar          = profile.avatar,
        daily_goal_mins = profile.daily_goal_mins,
        bio             = profile.bio,
        updated_at      = profile.updated_at,
    )


@router.get("/avatars")
def list_avatars():
    """Return list of valid avatar codes (public endpoint — no auth required)."""
    return {"avatars": list(VALID_AVATARS)}


@router.get("/exams")
def list_exams():
    """Return list of supported exam codes (public endpoint)."""
    return {"exams": list(VALID_EXAMS)}
