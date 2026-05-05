-- VYAS v0.6 Migration 007 — User Profiles (D2)
-- Run this after deploying v0.6 if using an existing database.
-- For fresh installs, SQLAlchemy creates this table automatically via create_all().

CREATE TABLE IF NOT EXISTS user_profiles (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    preparing_exam  VARCHAR(50),
    target_year     INTEGER,
    subject_focus   VARCHAR(200),
    avatar          VARCHAR(50),
    daily_goal_mins INTEGER DEFAULT 60,
    bio             VARCHAR(300),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);

-- For PostgreSQL: auto-update updated_at on row change
-- (SQLite does not support triggers in this way — handled by SQLAlchemy onupdate)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'set_user_profiles_updated_at'
    ) THEN
        CREATE TRIGGER set_user_profiles_updated_at
            BEFORE UPDATE ON user_profiles
            FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
    END IF;
END $$;
