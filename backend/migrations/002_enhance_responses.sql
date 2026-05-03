-- ============================================================
-- VYAS Phase 0 — Enhanced Response Tracking
-- Migration 002: Add granular analytics columns to responses
--
-- SAFE ADDITION: purely additive, all columns nullable with
-- defaults. No existing data or queries are affected.
-- ============================================================

-- Subtopic-level granularity (e.g. "National Income" within "Macroeconomics")
ALTER TABLE responses ADD COLUMN IF NOT EXISTS subtopic VARCHAR(100);

-- Question category: conceptual / numerical / application / analytical
ALTER TABLE responses ADD COLUMN IF NOT EXISTS question_category VARCHAR(50);

-- Expected solve time from question JSON (for time efficiency computation)
ALTER TABLE responses ADD COLUMN IF NOT EXISTS estimated_time_sec INTEGER;

-- Ratio of actual time spent vs. estimated time (>1 = slow, <1 = rushed)
-- Computed at submit time: time_spent_seconds / estimated_time_sec
ALTER TABLE responses ADD COLUMN IF NOT EXISTS time_efficiency_ratio FLOAT;

-- ── Indexes for Phase 1 proficiency engine queries ────────────────────────────
-- Composite index used by update_user_proficiency() to scan responses per topic
CREATE INDEX IF NOT EXISTS idx_responses_attempt_topic
    ON responses(attempt_id, topic, difficulty);

-- ============================================================
-- For SQLite (local dev):
-- SQLAlchemy ADD COLUMN is NOT supported via CREATE TABLE for
-- existing tables in SQLite. Run this migration manually via:
--   sqlite3 mockprep.db < 002_enhance_responses.sql
-- OR just delete mockprep.db and let auto-create rebuild it
-- (only safe if you have no prod data in dev).
-- ============================================================
