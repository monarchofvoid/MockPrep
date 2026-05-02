-- ============================================================
-- VYAS — Password Reset Table Migration
-- Run this ONCE against your database before deploying the
-- forgot-password feature.
--
-- This is a SAFE ADDITION — it does NOT modify the users table
-- or any existing data.
-- ============================================================

-- For PostgreSQL (production):
CREATE TABLE IF NOT EXISTS password_resets (
    id          VARCHAR(36)                  NOT NULL,
    user_id     INTEGER                      NOT NULL,
    token       TEXT                         NOT NULL,   -- SHA-256 hash of raw token
    expires_at  TIMESTAMP WITH TIME ZONE     NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE     NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_password_resets PRIMARY KEY (id),
    CONSTRAINT fk_password_resets_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

-- Index for fast token lookup
CREATE INDEX IF NOT EXISTS idx_password_resets_token   ON password_resets(token);
CREATE INDEX IF NOT EXISTS idx_password_resets_user_id ON password_resets(user_id);

-- ============================================================
-- For SQLite (local dev):
-- SQLAlchemy will create this table automatically on startup
-- via models.Base.metadata.create_all(bind=engine).
-- No manual migration needed in dev.
-- ============================================================
