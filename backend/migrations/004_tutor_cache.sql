-- ============================================================
-- VYAS Phase 2A — VYAS Tutor
-- Migration 004: Tutor explanation cache
--
-- Stores Gemini-generated explanations keyed by a SHA-256 hash
-- of (question_id + proficiency_bucket + user_answer + correct_answer).
-- Cache TTL is 7 days, enforced by the application layer.
-- No FK on cache_key — explanations are portable across users.
-- ============================================================

CREATE TABLE IF NOT EXISTS tutor_cache (
    id                 SERIAL PRIMARY KEY,

    -- SHA-256(question_id:proficiency_bucket:user_answer:correct_answer)
    cache_key          VARCHAR(64) UNIQUE NOT NULL,

    -- Metadata for debugging and cleanup
    question_id        INTEGER NOT NULL,
    exam               VARCHAR(50),
    proficiency_bucket VARCHAR(20) NOT NULL,  -- Beginner/Intermediate/Advanced/Expert
    user_answer        VARCHAR(1),            -- NULL means skipped
    correct_answer     VARCHAR(1) NOT NULL,

    -- The structured explanation from Gemini (stored as JSON)
    explanation_json   JSONB NOT NULL,

    -- Lifecycle
    created_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at         TIMESTAMP WITH TIME ZONE NOT NULL,
    hit_count          INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tutor_cache_key     ON tutor_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_tutor_cache_expires ON tutor_cache(expires_at);
