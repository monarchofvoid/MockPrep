-- ============================================================
-- VYAS Phase 1 — Proficiency Engine
-- Migration 003: Create user_proficiency table
--
-- SAFE ADDITION: new table only. Zero existing queries affected.
-- One row per (user, exam, subject, topic) triplet.
-- Upserted by services/proficiency.py after every submission.
-- ============================================================

CREATE TABLE IF NOT EXISTS user_proficiency (
    id                   SERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Scope: which exam/subject/topic this row tracks
    exam                 VARCHAR(50)  NOT NULL,
    subject              VARCHAR(100) NOT NULL,
    topic                VARCHAR(100) NOT NULL,
    subtopic             VARCHAR(100),              -- best-known subtopic for this topic

    -- ELO-like proficiency score (0–1000, starts at 400)
    proficiency          FLOAT NOT NULL DEFAULT 400.0,

    -- Derived analytics
    accuracy_rate        FLOAT NOT NULL DEFAULT 0.0,   -- correct / total (0.0–1.0)
    attempt_rate         FLOAT NOT NULL DEFAULT 0.0,   -- for future use
    avg_time_efficiency  FLOAT NOT NULL DEFAULT 1.0,   -- avg(actual_time / estimated_time)

    -- Raw counts (needed to compute running averages correctly)
    correct_count        INTEGER NOT NULL DEFAULT 0,
    total_count          INTEGER NOT NULL DEFAULT 0,

    -- Per-difficulty accuracy (running averages, 0.0–1.0)
    difficulty_easy_acc  FLOAT NOT NULL DEFAULT 0.0,
    difficulty_med_acc   FLOAT NOT NULL DEFAULT 0.0,
    difficulty_hard_acc  FLOAT NOT NULL DEFAULT 0.0,

    last_updated         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- One row per user+exam+subject+topic combination
    CONSTRAINT uq_user_proficiency UNIQUE(user_id, exam, subject, topic)
);

-- Fast lookup by user (used in GET /tutor/proficiency and Phase 2A/2B)
CREATE INDEX IF NOT EXISTS idx_user_proficiency_user
    ON user_proficiency(user_id);

-- Fast lookup for per-subject proficiency (used by AI mock generator in Phase 2B)
CREATE INDEX IF NOT EXISTS idx_user_proficiency_user_subject
    ON user_proficiency(user_id, subject, topic);
