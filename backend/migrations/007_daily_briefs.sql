CREATE TABLE IF NOT EXISTS daily_brief_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    brief_type TEXT NOT NULL CHECK (brief_type IN ('morning', 'night')),
    brief_date DATE NOT NULL,
    summary_markdown TEXT NOT NULL,
    stats_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS daily_brief_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_run_id UUID NOT NULL REFERENCES daily_brief_runs(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    item_kind TEXT,
    order_index INT NOT NULL DEFAULT 0,
    related_commitment_id UUID REFERENCES commitments(id) ON DELETE SET NULL,
    related_job_application_id UUID REFERENCES job_applications(id) ON DELETE SET NULL,
    related_normalized_item_id UUID REFERENCES normalized_items(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_daily_brief_runs_user_type_date
    ON daily_brief_runs(user_id, brief_type, brief_date DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_daily_brief_runs_account
    ON daily_brief_runs(account_id, brief_date DESC);

CREATE INDEX IF NOT EXISTS idx_daily_brief_items_run
    ON daily_brief_items(brief_run_id, section, order_index);
