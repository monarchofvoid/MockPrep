"""
VYAS v0.6 — Gemini Response Utilities
=======================================
Centralised safe JSON extraction from Gemini API responses.

Key exports:
  _safe_json_extract(raw_text)          → dict | list
  check_finish_reason(data, max_tokens) → None (raises on truncation)
  extract_raw_text(data)                → str

All functions raise descriptive exceptions — never silently return None.
"""

import json
import logging
import re
from typing import Union

logger = logging.getLogger(__name__)


class GeminiTruncationError(ValueError):
    """Raised when Gemini stops generation due to MAX_TOKENS."""


class GeminiParseError(ValueError):
    """Raised when the Gemini response cannot be parsed as valid JSON."""


def extract_raw_text(data: dict) -> str:
    """
    Safely extract the text payload from a Gemini generateContent response dict.

    Raises:
        KeyError / IndexError: if the response structure is unexpected.
        GeminiTruncationError: if finishReason is MAX_TOKENS.
    """
    # Validate finish reason before touching the content
    check_finish_reason(data)

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Unexpected Gemini response structure: %s", type(exc).__name__)
        raise GeminiParseError(
            "Gemini returned an unexpected response structure — no text content found."
        ) from exc


def check_finish_reason(data: dict) -> None:
    """
    Inspect the finishReason field in the first candidate.
    Raises GeminiTruncationError if the model was cut off.
    Logs warnings for non-STOP reasons (SAFETY, RECITATION, etc.).

    Args:
        data: The raw parsed JSON response from Gemini.
    """
    try:
        candidates = data.get("candidates", [])
        if not candidates:
            return  # No candidates → handled by extract_raw_text

        finish_reason = candidates[0].get("finishReason", "STOP")

        if finish_reason == "MAX_TOKENS":
            logger.error(
                "Gemini response truncated (MAX_TOKENS). Increase maxOutputTokens or reduce prompt size."
            )
            raise GeminiTruncationError(
                "AI response was truncated due to token limit. "
                "Please try again with fewer questions or a shorter prompt."
            )

        if finish_reason not in ("STOP", "FINISH_REASON_UNSPECIFIED", None, ""):
            logger.warning(
                "Gemini finished with non-STOP reason: %s", finish_reason
            )

    except GeminiTruncationError:
        raise
    except Exception as exc:
        # Structural issues — log but don't block (extract_raw_text handles those)
        logger.warning("Could not inspect finishReason: %s", exc)


def _safe_json_extract(raw_text: str) -> Union[dict, list]:
    """
    Robustly extract a JSON object or array from Gemini's raw text output.

    Handles all known Gemini response patterns:
      1. Clean JSON (no wrapper)
      2. Markdown fences: ```json\\n{...}\\n```
      3. Preamble text before JSON: "Sure! Here's the response:\\n{...}"
      4. Trailing text after JSON
      5. Mixed: preamble + fences + trailing

    Args:
        raw_text: The raw string from Gemini's parts[0].text

    Returns:
        Parsed dict or list.

    Raises:
        GeminiParseError: if no valid JSON can be extracted.
    """
    if not raw_text or not isinstance(raw_text, str):
        raise GeminiParseError("Gemini returned empty or non-string content.")

    text = raw_text.strip()

    # ── Strategy 1: Direct parse (clean JSON) ─────────────────────────────────
    if text.startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass  # Fall through to extraction strategies

    # ── Strategy 2: Strip markdown code fences ────────────────────────────────
    fence_pattern = re.compile(
        r"```(?:json)?\s*\n?([\s\S]*?)\n?```",
        re.IGNORECASE,
    )
    fence_match = fence_pattern.search(text)
    if fence_match:
        inner = fence_match.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass  # Still try other strategies

    # ── Strategy 3: Find first { or [ and extract balanced JSON ───────────────
    # Handles preamble text like "Sure! Here is the JSON:\n{...}"
    for start_char, end_char in (('{', '}'), ('[', ']')):
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue

        # Walk backwards from the last occurrence of the matching end char
        end_idx = text.rfind(end_char)
        if end_idx == -1 or end_idx <= start_idx:
            continue

        candidate = text[start_idx : end_idx + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # If the naive slice fails, try finding a balanced closing bracket
        extracted = _extract_balanced(text, start_idx, start_char, end_char)
        if extracted:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                pass

    # ── Strategy 4: Clean common issues and retry ─────────────────────────────
    cleaned = _clean_json_string(text)
    if cleaned:
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # All strategies exhausted
    logger.error(
        "Failed to parse Gemini response as JSON. First 200 chars: %r",
        text[:200],
    )
    raise GeminiParseError(
        "AI returned a response that could not be parsed as JSON. "
        "This is usually a transient Gemini issue — please retry."
    )


def _extract_balanced(text: str, start_idx: int, open_char: str, close_char: str) -> str:
    """
    Walk character-by-character from start_idx, tracking bracket depth.
    Returns the balanced JSON string, or empty string if not found.
    """
    depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(text[start_idx:], start=start_idx):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[start_idx : i + 1]

    return ""


def _clean_json_string(text: str) -> str:
    """
    Apply common cleanup transformations to malformed JSON strings.
    Returns cleaned string or empty string if nothing useful found.
    """
    # Remove BOM
    text = text.lstrip("\ufeff")

    # Find start of JSON structure
    for start_char in ('{', '['):
        idx = text.find(start_char)
        if idx != -1:
            return text[idx:]

    return ""
