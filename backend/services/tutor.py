"""
VYAS Phase 2A — Tutor Service
================================
Provides personalized AI explanations via the Gemini API.

Public API:
  get_proficiency_bucket(score) → str
  make_cache_key(question_id, bucket, user_answer, correct_answer) → str
  build_tutor_prompt(question_data, user_answer, proficiency_level,
                     time_efficiency, was_marked, answer_changes) → (system, user)
  async call_gemini(system_prompt, user_message) → dict
  async get_or_create_explanation(db, question_data, response_row,
                                  proficiency_score, force_refresh) → (dict, bool)
"""

import hashlib
import json
import os
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

import models

# ── Configuration ──────────────────────────────────────────────────────────────
# NOTE: Do NOT read GEMINI_MODEL at module level.
# It is read fresh inside call_gemini() on every request so that:
#   1. A server restart after editing .env picks up the new value correctly.
#   2. A missing env var produces a clear error, not a silent None→404.
CACHE_TTL_DAYS  = 7
GEMINI_TIMEOUT  = 20.0   # seconds

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


# ── Proficiency helpers ────────────────────────────────────────────────────────

def get_proficiency_bucket(score: float) -> str:
    """Map ELO score to one of the 4 cache bucket labels."""
    if score >= 800:
        return "Expert"
    if score >= 600:
        return "Advanced"
    if score >= 300:
        return "Intermediate"
    return "Beginner"


# ── Cache key ──────────────────────────────────────────────────────────────────

def make_cache_key(
    question_id: int,
    proficiency_bucket: str,
    user_answer: Optional[str],
    correct_answer: str,
) -> str:
    """
    SHA-256 of (question_id:bucket:user_answer:correct_answer).
    Produces a 64-char hex string suitable for VARCHAR(64).
    user_answer=None → "SKIPPED" (different explanation tone than wrong answer).
    """
    raw = f"{question_id}:{proficiency_bucket}:{user_answer or 'SKIPPED'}:{correct_answer}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_tutor_prompt(
    question_data: dict,
    user_answer: Optional[str],
    proficiency_level: str,
    time_efficiency: Optional[float],
    was_marked: bool,
    answer_changes: int,
) -> tuple[str, str]:
    """
    Build (system_prompt, user_message) for the Gemini explain call.
    Returns a tuple; both are plain strings.
    """
    actual_time   = question_data.get("_actual_time_seconds", 0)
    estimated     = question_data.get("estimated_time_sec", 0)
    subject       = question_data.get("_subject", "")
    topic         = question_data.get("topic", "")

    # ── System prompt ──────────────────────────────────────────────────────────
    system_prompt = f"""You are VYAS, an expert AI tutor for Indian competitive exam preparation (CUET, GATE, JEE, UPSC).

You are generating a personalized explanation for a student.

STUDENT PROFILE:
- Proficiency Level: {proficiency_level}  (Beginner / Intermediate / Advanced / Expert)
- Subject: {subject}
- Topic: {topic}
- Time taken: {actual_time}s (estimated: {estimated}s)
- They marked this for review: {"Yes" if was_marked else "No"}
- They changed their answer {answer_changes} time(s)

EXPLANATION STYLE RULES:
- Beginner: Use simple language. Start with a real-world analogy. Be encouraging. Avoid jargon. (150–250 words)
- Intermediate: Be precise. Show the logic chain. Reference the principle, not just the answer. (100–180 words)
- Advanced: Be direct. Assume concept knowledge. Focus on the edge case or trick. (60–120 words)
- Expert: Pose a follow-up challenge. Be peer-level. No hand-holding. (40–80 words + follow-up)

BEHAVIORAL NOTES:
- If actual_time < 0.5 * estimated_time AND estimated_time > 0: include a note that the student may have rushed
- If was_marked_for_review = Yes: acknowledge that the student had doubts
- If answer_changes >= 2: address the second-guessing pattern

OUTPUT FORMAT:
Return ONLY valid JSON — no markdown, no preamble, no trailing text. Exactly this schema:
{{
  "opening": "...",
  "core_concept": "...",
  "why_correct": "...",
  "why_wrong": "...",
  "memory_anchor": "...",
  "follow_up": "..."
}}

Field rules:
- opening: 1–2 sentences addressing what went wrong (or "you skipped this" if no answer given)
- core_concept: the underlying principle, explained at the student's level
- why_correct: why the correct answer is right
- why_wrong: why the student's answer was wrong (use null if student skipped)
- memory_anchor: a memorable hook to remember this concept
- follow_up: a practice question or challenge (use null for Beginner/Intermediate if not helpful)

Do NOT invent facts. If uncertain, express it within the explanation."""

    # ── User message ───────────────────────────────────────────────────────────
    q_text    = question_data.get("question", "")
    options   = question_data.get("options", {})
    correct   = question_data.get("correct", "")
    selected  = user_answer or "Not answered (skipped)"

    options_str = "\n".join(f"{k}) {v}" for k, v in options.items())

    user_message = f"""QUESTION: {q_text}

OPTIONS:
{options_str}

CORRECT ANSWER: {correct}
STUDENT SELECTED: {selected}

Generate the explanation now."""

    return system_prompt, user_message


# ── Gemini API call ────────────────────────────────────────────────────────────

async def call_gemini(system_prompt: str, user_message: str) -> dict:
    """
    Make an async POST to the Gemini generateContent endpoint.
    Returns the parsed explanation dict.
    Raises ValueError on API key/model absence, httpx.HTTPError on API failure,
    and json.JSONDecodeError if the response isn't valid JSON.

    IMPORTANT: GEMINI_MODEL and GEMINI_API_KEY are read here at call time (not
    at module import time) so that:
      - Editing .env and restarting the server always picks up the new values.
      - A missing/empty env var raises a clear error instead of a silent 404.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment variables.")

    # Read model name fresh on every call — never stale after a restart
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    if not gemini_model:
        raise ValueError("GEMINI_MODEL is not set in environment variables.")

    url = _GEMINI_URL.format(model=gemini_model, key=api_key)

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": user_message}]}
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

    # Strip markdown fences if Gemini wraps the JSON
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        parts = raw_text.split("```")
        # parts[1] starts with optional "json\n", then the content
        inner = parts[1]
        if inner.startswith("json"):
            inner = inner[4:]
        raw_text = inner.strip()

    return json.loads(raw_text)


# ── Cache-aware explanation retrieval ─────────────────────────────────────────

async def get_or_create_explanation(
    db: Session,
    question_data: dict,          # enriched with _actual_time_seconds, _subject
    response_row: models.Response,
    proficiency_score: float,
    force_refresh: bool = False,
) -> tuple[dict, bool]:
    """
    Returns (explanation_dict, was_cache_hit).
    Checks tutor_cache first; calls Gemini on miss; updates cache.
    On any Gemini failure, raises the exception — caller handles fallback.
    """
    correct_answer = question_data.get("correct", "")
    user_answer    = response_row.selected_option  # may be None
    bucket         = get_proficiency_bucket(proficiency_score)
    cache_key      = make_cache_key(
        question_id=response_row.question_id,
        proficiency_bucket=bucket,
        user_answer=user_answer,
        correct_answer=correct_answer,
    )

    now = datetime.now(timezone.utc)

    # ── Cache lookup ──────────────────────────────────────────────────────────
    if not force_refresh:
        cached = (
            db.query(models.TutorCache)
            .filter_by(cache_key=cache_key)
            .filter(models.TutorCache.expires_at > now)
            .first()
        )
        if cached:
            cached.hit_count += 1
            db.commit()
            return cached.explanation_json, True

    # ── Build prompt and call Gemini ──────────────────────────────────────────
    system_prompt, user_message = build_tutor_prompt(
        question_data=question_data,
        user_answer=user_answer,
        proficiency_level=bucket,
        time_efficiency=getattr(response_row, "time_efficiency_ratio", None),
        was_marked=bool(response_row.was_marked_for_review),
        answer_changes=response_row.answer_changed_count or 0,
    )

    explanation = await call_gemini(system_prompt, user_message)

    # ── Validate explanation has required fields (apply safe defaults) ─────────
    for field in ("opening", "core_concept", "why_correct", "memory_anchor"):
        if field not in explanation or not explanation[field]:
            explanation[field] = "Explanation not available for this field."
    explanation.setdefault("why_wrong", None)
    explanation.setdefault("follow_up", None)

    # ── Store in cache ────────────────────────────────────────────────────────
    expires = now + timedelta(days=CACHE_TTL_DAYS)

    # Upsert: replace if expired or force_refresh
    existing = db.query(models.TutorCache).filter_by(cache_key=cache_key).first()
    if existing:
        existing.explanation_json   = explanation
        existing.expires_at         = expires
        existing.hit_count          = 0
        existing.proficiency_bucket = bucket
    else:
        db.add(models.TutorCache(
            cache_key          = cache_key,
            question_id        = response_row.question_id,
            exam               = question_data.get("_exam"),
            proficiency_bucket = bucket,
            user_answer        = user_answer,
            correct_answer     = correct_answer,
            explanation_json   = explanation,
            expires_at         = expires,
            hit_count          = 0,
        ))

    db.commit()
    return explanation, False


# ── Behavioral note helper ─────────────────────────────────────────────────────

def build_behavioral_note(
    response_row: models.Response,
    question_data: dict,
) -> Optional[str]:
    """
    Produce a short contextual note about the student's behaviour on this question.
    Returns None if there's nothing notable.
    """
    notes = []

    estimated = question_data.get("estimated_time_sec") or 0
    actual    = response_row.time_spent_seconds or 0

    if estimated > 0 and actual < 0.5 * estimated:
        notes.append(
            f"You spent {actual}s (estimated: {estimated}s) — you may have rushed this one."
        )

    if response_row.was_marked_for_review:
        notes.append("You marked this for review, indicating you had doubts.")

    if (response_row.answer_changed_count or 0) >= 2:
        notes.append(
            f"You changed your answer {response_row.answer_changed_count}× — "
            "trust your first instinct more often."
        )

    return " ".join(notes) if notes else None