"""
VYAS v2.0 — Recommendations Router
=====================================
GET /recommendations — returns onboarding card and proficiency-based
recommendations for Dashboard.jsx.

FIX: The original router had its own inline stub implementation that
hardcoded `recommended_mocks: []` with a "future phase" comment.
The full recommendation engine already existed in services/recommendations.py
but was never wired up. This router now delegates entirely to that service.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user
from services.recommendations import get_recommendations as _get_recommendations

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Recommendations"])


@router.get("/recommendations")
def get_recommendations(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_recommendations(db=db, user_id=current_user.id)