"""
seed.py — Run any time to sync the mock_tests table with question_bank/.

Usage:
  cd backend
  python seed.py

How it works:
  - Scans every .json file inside ../question_bank/ recursively
  - NEW files   → inserted into mock_tests
  - CHANGED files → updated in mock_tests (duration, marks, question count, etc.)
  - UNCHANGED files → skipped
  - Never deletes existing papers or any attempt/response data
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from database import engine, SessionLocal
import models

QB_ROOT = Path(__file__).parent.parent / "question_bank"

# Fields that are compared and updated when JSON changes
TRACKED_FIELDS = [
    "exam",
    "subject",
    "year",
    "duration_minutes",
    "total_marks",
    "question_count",
    "json_file_path",
]


def make_mock_id(relative_path: Path) -> str:
    parts = list(relative_path.with_suffix("").parts)
    return "_".join(parts)


def load_paper(json_path: Path) -> dict:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    relative    = json_path.relative_to(QB_ROOT)
    mock_id     = make_mock_id(relative)
    duration    = data.get("duration_minutes") or data.get("duration") or 30
    total_marks = data.get("total_marks") or sum(
        q.get("marks", 1) for q in data.get("questions", [])
    )

    return {
        "id":               mock_id,
        "exam":             data.get("exam", "UNKNOWN"),
        "subject":          data.get("subject", relative.parts[0].upper()),
        "year":             data.get("year", ""),
        "duration_minutes": int(duration),
        "total_marks":      float(total_marks),
        "question_count":   len(data.get("questions", [])),
        "json_file_path":   str(relative),
    }


def diff(existing: models.MockTest, paper: dict) -> dict:
    """Return only the fields that differ between DB row and parsed JSON."""
    changed = {}
    for field in TRACKED_FIELDS:
        db_val   = getattr(existing, field)
        json_val = paper[field]
        # Normalise types for fair comparison
        if isinstance(db_val, float) or isinstance(json_val, float):
            db_val   = float(db_val   or 0)
            json_val = float(json_val or 0)
        if db_val != json_val:
            changed[field] = {"before": db_val, "after": json_val}
    return changed


def seed():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── Scan question_bank/ ───────────────────────────────────
        json_files = sorted(QB_ROOT.rglob("*.json"))

        if not json_files:
            print(f"\n⚠  No JSON files found in {QB_ROOT}")
            return

        print(f"\n🔍 Found {len(json_files)} JSON file(s) in question_bank/\n")

        added   = 0
        updated = 0
        skipped = 0
        errors  = 0

        for json_path in json_files:
            rel = json_path.relative_to(QB_ROOT)

            try:
                paper = load_paper(json_path)
            except Exception as e:
                print(f"  ❌ Parse error — {rel}: {e}")
                errors += 1
                continue

            existing = db.query(models.MockTest).filter_by(id=paper["id"]).first()

            # ── NEW paper ─────────────────────────────────────────
            if not existing:
                db.add(models.MockTest(**paper))
                print(
                    f"  ✅ NEW      — {paper['id']}\n"
                    f"              {paper['exam']} · {paper['subject']} · "
                    f"{paper['year']} · {paper['question_count']} Qs · "
                    f"{paper['total_marks']} marks · {paper['duration_minutes']} min"
                )
                added += 1
                continue

            # ── EXISTING — check for changes ──────────────────────
            changes = diff(existing, paper)

            if not changes:
                print(f"  ─  no change — {paper['id']}")
                skipped += 1
                continue

            # Apply updates
            for field, vals in changes.items():
                setattr(existing, field, paper[field])

            # Pretty-print what changed
            change_lines = "  ".join(
                f"{f}: {v['before']} → {v['after']}"
                for f, v in changes.items()
            )
            print(f"  🔄 UPDATED  — {paper['id']}\n"
                  f"              {change_lines}")
            updated += 1

        db.commit()

        print(f"""
────────────────────────────────────────
  {added}   newly added
  {updated}   updated (JSON changed)
  {skipped}   unchanged (skipped)
  {errors}   parse errors
────────────────────────────────────────""")

        if added + updated > 0:
            print("🎉 Changes saved. Restart the server:  uvicorn main:app --reload")
        else:
            print("✔  Database already up to date.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()