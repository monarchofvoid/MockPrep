"""
VYAS Phase 2B — AI Mock Generator Service
==========================================
Generates personalized MCQ mock tests on demand via the Gemini API.
Questions are validated against the QuestionRenderer schema before storage.

Public API:
  get_difficulty_distribution(proficiency_score) → dict
  validate_ai_question(raw, index) → dict (raises ValueError on invalid)
  build_generation_prompt(exam, subject, difficulty, count,
                          dist, weak_topics) → (system, user)
  async generate_questions(exam, subject, difficulty, count,
                           proficiency_score, weak_topics) → list[dict]
"""

import json
import os
import traceback
from typing import Optional

import httpx

# ── Configuration ──────────────────────────────────────────────────────────────
# NOTE: Do NOT read GEMINI_MODEL at module level.
# It is read fresh inside call_gemini_generate() on every request so that:
#   1. A server restart after editing .env picks up the new value correctly.
#   2. A missing env var produces a clear error, not a silent None→404.
GEMINI_TIMEOUT = 40.0   # generation takes longer than explanation

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)

# ── Difficulty distributions ───────────────────────────────────────────────────

def get_difficulty_distribution(proficiency_score: float) -> dict:
    """
    Return easy/medium/hard question count ratios based on ELO score.
    If proficiency data is unavailable (score = 400 default), uses Intermediate.
    Glue between Phase 1 (proficiency) and Phase 2B (AI mock content).
    """
    if proficiency_score < 300:     # Beginner
        return {"easy": 0.60, "medium": 0.35, "hard": 0.05}
    elif proficiency_score < 600:   # Intermediate
        return {"easy": 0.20, "medium": 0.55, "hard": 0.25}
    elif proficiency_score < 800:   # Advanced
        return {"easy": 0.05, "medium": 0.35, "hard": 0.60}
    else:                           # Expert
        return {"easy": 0.00, "medium": 0.20, "hard": 0.80}


def counts_from_distribution(total: int, dist: dict) -> dict:
    """Convert ratio dict to exact integer counts that sum to total."""
    easy   = round(total * dist["easy"])
    hard   = round(total * dist["hard"])
    medium = total - easy - hard          # ensure sum = total
    return {"easy": max(0, easy), "medium": max(0, medium), "hard": max(0, hard)}


# ── Question validation ────────────────────────────────────────────────────────

def validate_ai_question(raw: dict, index: int) -> dict:
    """
    Validate and normalise a single question object from Gemini.
    Raises ValueError with a clear message on any violation.
    Applies safe defaults for optional fields.
    """
    required = ["question", "options", "correct", "explanation", "difficulty", "topic"]
    for field in required:
        if field not in raw or not raw[field]:
            raise ValueError(f"Question {index + 1}: missing required field '{field}'")

    if not isinstance(raw["options"], dict):
        raise ValueError(f"Question {index + 1}: 'options' must be a dict")

    if len(raw["options"]) != 4:
        raise ValueError(f"Question {index + 1}: must have exactly 4 options, got {len(raw['options'])}")

    for key in raw["options"]:
        if key not in ("A", "B", "C", "D"):
            raise ValueError(f"Question {index + 1}: option keys must be A/B/C/D, got '{key}'")

    if raw["correct"] not in raw["options"]:
        raise ValueError(
            f"Question {index + 1}: correct='{raw['correct']}' not in options keys"
        )

    if raw["difficulty"] not in ("easy", "medium", "hard"):
        raw["difficulty"] = "medium"    # safe default rather than raising

    # Apply safe defaults for optional fields
    raw.setdefault("id",               index + 1)
    raw.setdefault("type",             "mcq")
    raw.setdefault("marks",            4)
    raw.setdefault("negative_marking", 1)
    raw.setdefault("passage",          None)
    raw.setdefault("passage_title",    None)
    raw.setdefault("subtopic",         None)
    raw.setdefault("estimated_time_sec", None)

    # Override id to match 1-based position (Gemini may send wrong ids)
    raw["id"] = index + 1

    return raw


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_generation_prompt(
    exam: str,
    subject: str,
    difficulty: str,      # "auto" uses distribution, else "easy"/"medium"/"hard"
    count: int,
    dist: dict,           # {"easy": n, "medium": n, "hard": n}
    weak_topics: list[str],
) -> tuple[str, str]:
    """
    Build (system_prompt, user_message) for the Gemini question generation call.
    """
    topic_hint = ""
    if weak_topics:
        top3 = ", ".join(weak_topics[:3])
        topic_hint = f"\nPRIORITY TOPICS (student's weak areas — weight these heavily): {top3}"

    if difficulty == "auto":
        diff_instruction = (
            f"Generate exactly {dist['easy']} easy, {dist['medium']} medium, "
            f"and {dist['hard']} hard questions."
        )
    else:
        diff_instruction = f"All {count} questions must be {difficulty} difficulty."

    system_prompt = f"""You are an expert question setter for Indian competitive exams ({exam}).
Your task is to generate high-quality, original MCQ questions for the subject: {subject}.

RULES — you must follow ALL of these exactly:
1. Generate exactly {count} questions. No more, no less.
2. {diff_instruction}
3. Each question must have exactly 4 options labeled A, B, C, D.
4. The 'correct' field must be one of: A, B, C, or D — and must actually be correct.
5. All distractors (wrong options) must be plausible — not obviously wrong.
6. 'explanation' must be 2–4 sentences explaining WHY the correct answer is right.
7. Each question must have a 'topic' field (the sub-topic within {subject}).
8. Do NOT repeat questions or use trivial true/false phrasing.
9. Questions must be suitable for {exam} level — neither too easy nor academic.
10. Do NOT include any answer hints in the question text itself.{topic_hint}

OUTPUT FORMAT:
Return ONLY a valid JSON array — no markdown, no preamble, no trailing text.
The array must contain exactly {count} question objects with this exact schema:

[
  {{
    "id": 1,
    "type": "mcq",
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct": "B",
    "explanation": "...",
    "difficulty": "easy|medium|hard",
    "topic": "...",
    "marks": 4,
    "negative_marking": 1
  }}
]"""

    user_message = (
        f"Generate {count} {exam} {subject} MCQ questions now. "
        f"Output ONLY the JSON array — nothing else."
    )

    return system_prompt, user_message


# ── Gemini API call ────────────────────────────────────────────────────────────

async def call_gemini_generate(system_prompt: str, user_message: str) -> list[dict]:
    """
    Call Gemini to generate questions. Returns a parsed list of raw question dicts.
    Raises ValueError on missing API key or model, httpx.HTTPError on API failure.

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
            "temperature":      0.7,    # more creative than tutor (0.3)
            "maxOutputTokens":  8192,   # enough for 20 full questions
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    data     = response.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Strip markdown fences if present
    if raw_text.startswith("```"):
        parts    = raw_text.split("```")
        inner    = parts[1]
        if inner.startswith("json"):
            inner = inner[4:]
        raw_text = inner.strip()

    parsed = json.loads(raw_text)

    if not isinstance(parsed, list):
        raise ValueError(f"Expected a JSON array, got {type(parsed).__name__}")

    return parsed


# ── Main generation entry point ────────────────────────────────────────────────

async def generate_questions(
    exam: str,
    subject: str,
    difficulty: str,       # "auto" | "easy" | "medium" | "hard"
    count: int,
    proficiency_score: float = 400.0,
    weak_topics: Optional[list[str]] = None,
) -> list[dict]:
    """
    Full generation pipeline:
      1. Compute difficulty distribution (uses proficiency if difficulty="auto")
      2. Build prompt
      3. Call Gemini
      4. Validate and normalise each question
      5. Return validated list

    Raises ValueError or httpx.HTTPError on failure.
    Count is capped at 20 to avoid token overruns and abuse.
    """
    count      = min(count, 20)
    weak_topics = weak_topics or []

    dist   = get_difficulty_distribution(proficiency_score)
    counts = counts_from_distribution(count, dist)

    system_prompt, user_message = build_generation_prompt(
        exam=exam,
        subject=subject,
        difficulty=difficulty,
        count=count,
        dist=counts,
        weak_topics=weak_topics,
    )

    raw_questions = await call_gemini_generate(system_prompt, user_message)

    validated = []
    errors    = []
    for i, raw in enumerate(raw_questions[:count]):    # never exceed requested count
        try:
            validated.append(validate_ai_question(raw, i))
        except ValueError as e:
            errors.append(str(e))

    if errors:
        # Log validation errors but don't fail the whole generation if most passed
        print(f"[ai_mock] {len(errors)} validation errors:\n  " + "\n  ".join(errors))

    if len(validated) < max(1, count // 2):
        raise ValueError(
            f"Too few valid questions generated ({len(validated)}/{count}). "
            f"Errors: {'; '.join(errors[:3])}"
        )

    return validated