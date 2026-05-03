-- ============================================================
-- VYAS Phase 2A — VYAS Tutor
-- Migration 005: Tutor interaction log + user ratings
--
-- Every /tutor/explain call is logged here regardless of cache hit.
-- user_rating (1–5 stars) is populated via POST /tutor/rate.
-- ============================================================

CREATE TABLE IF NOT EXISTS tutor_interactions (
    id                   SERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attempt_id           INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    question_id          INTEGER NOT NULL,

    -- Proficiency at the time of the request (for trend analysis)
    proficiency_at_time  FLOAT,

    -- Was the explanation served from cache or freshly generated?
    was_cache_hit        BOOLEAN NOT NULL DEFAULT FALSE,

    -- Optional user rating (1–5), populated via POST /tutor/rate
    user_rating          SMALLINT CHECK (user_rating BETWEEN 1 AND 5),

    created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tutor_interactions_user
    ON tutor_interactions(user_id);

CREATE INDEX IF NOT EXISTS idx_tutor_interactions_attempt
    ON tutor_interactions(attempt_id);
