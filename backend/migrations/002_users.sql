-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    password_hash TEXT,  -- NULL for Google-only users
    auth_provider TEXT NOT NULL DEFAULT 'email' CHECK (auth_provider IN ('email', 'google')),
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

-- Link accounts to users
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(user_id);