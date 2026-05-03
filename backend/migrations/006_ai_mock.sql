-- ============================================================
-- VYAS Phase 2B — AI Mock Generator
-- Migration 006: AI-generated question storage + mock_tests flags
--
-- SAFE ADDITION: new table + two nullable columns on mock_tests.
-- All existing mock_tests rows get is_ai_generated = FALSE (default).
-- Zero existing queries or behavior change.
-- ============================================================

-- ── New table: stores questions for AI-generated mocks ────────────────────────
-- Each row = one question object (JSONB) for a specific AI mock.
-- Linked to mock_tests.id via FK so cascade delete cleans up automatically.
CREATE TABLE IF NOT EXISTS ai_mock_questions (
    id            SERIAL PRIMARY KEY,
    mock_id       VARCHAR(100) NOT NULL REFERENCES mock_tests(id) ON DELETE CASCADE,
    question_data JSONB        NOT NULL,   -- Full question object (matches QuestionRenderer schema)
    position      INTEGER      NOT NULL,   -- 1-based ordering
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_mock_questions_mock
    ON ai_mock_questions(mock_id, position);

-- ── Extend mock_tests to flag AI-generated rows ───────────────────────────────
ALTER TABLE mock_tests
    ADD COLUMN IF NOT EXISTS is_ai_generated BOOLEAN NOT NULL DEFAULT FALSE;

-- Stores generation params (exam, subject, difficulty, count, proficiency snapshot)
-- for audit / history reconstruction.
ALTER TABLE mock_tests
    ADD COLUMN IF NOT EXISTS ai_generation_params JSONB;

-- ============================================================
-- SQLite (local dev): metadata.create_all() handles ai_mock_questions
-- automatically since it's a new table.
-- The two ALTER TABLE statements need to be run manually in SQLite:
--   sqlite3 mockprep.db < migrations/006_ai_mock.sql
-- OR delete mockprep.db and let auto-create rebuild everything.
-- ============================================================
