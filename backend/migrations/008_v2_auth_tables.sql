-- ============================================================
-- VYAS v2.0 Migration 008 — Refresh Tokens & Login Attempts
-- ============================================================
-- Run ONCE against your PostgreSQL production database.
-- SQLite users: these tables are auto-created by SQLAlchemy
-- on startup, so this migration is mainly for PostgreSQL.
--
-- Tables added:
--   refresh_tokens   — server-side refresh token store
--   login_attempts   — brute-force protection audit log
-- ============================================================

-- ── refresh_tokens ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at  TIMESTAMPTZ,
    user_agent  VARCHAR(300),
    ip_address  VARCHAR(45)
);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash
    ON refresh_tokens(token_hash);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id
    ON refresh_tokens(user_id);

-- Partial index: fast lookup of active (non-revoked, non-expired) tokens
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_active
    ON refresh_tokens(user_id, expires_at)
    WHERE revoked_at IS NULL;

-- ── login_attempts ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS login_attempts (
    id           SERIAL PRIMARY KEY,
    email        VARCHAR(200) NOT NULL,
    ip_address   VARCHAR(45),
    success      BOOLEAN NOT NULL DEFAULT FALSE,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_login_attempts_email
    ON login_attempts(email);

-- Partial index: fast brute-force check (only failed attempts)
CREATE INDEX IF NOT EXISTS ix_login_attempts_email_failed
    ON login_attempts(email, attempted_at)
    WHERE success = FALSE;

-- ── Maintenance: auto-clean old login attempts (optional, run manually) ──────
-- DELETE FROM login_attempts WHERE attempted_at < NOW() - INTERVAL '7 days';

-- ── Maintenance: auto-clean expired/revoked refresh tokens ───────────────────
-- DELETE FROM refresh_tokens
--   WHERE expires_at < NOW() OR revoked_at IS NOT NULL;
