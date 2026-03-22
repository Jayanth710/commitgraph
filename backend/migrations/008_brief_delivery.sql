CREATE TABLE IF NOT EXISTS brief_delivery_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL DEFAULT 'email' CHECK (channel IN ('email', 'sms')),
    destination TEXT,
    timezone TEXT NOT NULL DEFAULT 'America/Denver',
    morning_enabled BOOLEAN NOT NULL DEFAULT true,
    morning_time TIME NOT NULL DEFAULT '08:00',
    night_enabled BOOLEAN NOT NULL DEFAULT false,
    night_time TIME NOT NULL DEFAULT '20:00',
    sender_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS brief_delivery_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_run_id UUID REFERENCES daily_brief_runs(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preference_id UUID REFERENCES brief_delivery_preferences(id) ON DELETE SET NULL,
    channel TEXT NOT NULL CHECK (channel IN ('email', 'sms')),
    destination TEXT,
    brief_type TEXT NOT NULL CHECK (brief_type IN ('morning', 'night')),
    brief_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed', 'skipped')),
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, channel, brief_type, brief_date)
);

CREATE INDEX IF NOT EXISTS idx_brief_delivery_preferences_active
    ON brief_delivery_preferences(is_active, user_id);

CREATE INDEX IF NOT EXISTS idx_brief_delivery_runs_user_date
    ON brief_delivery_runs(user_id, brief_date DESC, created_at DESC);
