"""VYAS v2.0 — Tutor & Proficiency Schemas

BUGFIX v2.1.1:
  Renamed TutorExplanation fields to match BOTH the AI prompt output
  and the frontend SECTION_LABELS dictionary.

  Root cause: The old schema used `common_mistake` and `mnemonic` as field
  names, but:
    - The Groq prompt outputs JSON keys `why_wrong` and `follow_up`
    - The frontend SECTION_LABELS also expects `why_wrong` and `follow_up`
    - The router was doing a lossy rename (common_mistake, mnemonic) that
      broke both the cache round-trip AND the frontend rendering

  Fix: Use `why_wrong` and `follow_up` throughout. The router no longer
  needs to remap these keys at all.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


# ── Proficiency ───────────────────────────────────────────────────────────────

class DifficultyProfile(BaseModel):
    easy: Optional[float] = None
    medium: Optional[float] = None
    hard: Optional[float] = None


class TopicProficiency(BaseModel):
    exam: Optional[str] = None
    subject: Optional[str] = None
    topic: str
    subtopic: Optional[str] = None
    proficiency: float
    level: str
    accuracy_rate: Optional[float] = None
    total_count: int = 0
    correct_count: int = 0
    difficulty_profile: Optional[DifficultyProfile] = None
    avg_time_efficiency: Optional[float] = None
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProficiencyResponse(BaseModel):
    user_id: int
    overall_level: str
    overall_score: float
    topic_count: int
    topics: List[TopicProficiency]


# ── Tutor Explain ─────────────────────────────────────────────────────────────

class TutorExplainRequest(BaseModel):
    attempt_id: int
    question_id: str
    force_refresh: bool = False


class TutorExplanation(BaseModel):
    """
    Mirrors the JSON structure returned by the Groq prompt AND the keys
    the frontend SECTION_LABELS dictionary uses.

    AI prompt output keys  → schema field  → frontend SECTION_LABELS key
    ─────────────────────────────────────────────────────────────────────
    opening                  opening          opening
    core_concept             core_concept     core_concept
    why_correct              why_correct      why_correct
    why_wrong                why_wrong        why_wrong       ← was "common_mistake"
    memory_anchor            memory_anchor    memory_anchor
    follow_up                follow_up        follow_up       ← was "mnemonic"
    """
    opening: str
    core_concept: str
    why_correct: str
    memory_anchor: str
    # Optional fields — names now match the AI prompt output and frontend
    why_wrong: Optional[str] = None    # renamed from common_mistake
    follow_up: Optional[str] = None    # renamed from mnemonic
    # Extra optional fields that some AI responses may include
    steps: Optional[List[str]] = None
    formula: Optional[str] = None

    class Config:
        extra = "allow"  # allow any additional fields from AI without error


class TutorExplainResponse(BaseModel):
    interaction_id: int
    question_id: str
    proficiency_level: str
    proficiency_score: float
    was_cache_hit: bool
    behavioral_note: Optional[str] = None
    explanation: TutorExplanation


# ── Tutor Rate ────────────────────────────────────────────────────────────────

class TutorRateRequest(BaseModel):
    interaction_id: int
    rating: int  # 1–5


class TutorRateResponse(BaseModel):
    interaction_id: int
    rating: int
    message: str
