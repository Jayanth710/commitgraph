CREATE TABLE IF NOT EXISTS job_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    company_name TEXT NOT NULL,
    role_title TEXT,
    status TEXT NOT NULL DEFAULT 'applied' CHECK (status IN (
        'applied',
        'assessment',
        'interview',
        'rejected',
        'offer',
        'withdrawn',
        'closed'
    )),
    summary TEXT NOT NULL,
    raw_text TEXT,
    date_applied TIMESTAMPTZ,
    last_status_at TIMESTAMPTZ,
    source_normalized_item_id UUID REFERENCES normalized_items(id) ON DELETE SET NULL,
    source_thread_id TEXT,
    confidence_score FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_application_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_application_id UUID NOT NULL REFERENCES job_applications(id) ON DELETE CASCADE,
    normalized_item_id UUID REFERENCES normalized_items(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('detected', 'status_change', 'note')),
    status TEXT CHECK (status IN (
        'applied',
        'assessment',
        'interview',
        'rejected',
        'offer',
        'withdrawn',
        'closed'
    )),
    event_date TIMESTAMPTZ,
    summary TEXT NOT NULL,
    raw_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(job_application_id, normalized_item_id, event_type, summary)
);

CREATE INDEX IF NOT EXISTS idx_job_applications_user_status
    ON job_applications(user_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_job_applications_thread
    ON job_applications(source_thread_id);

CREATE INDEX IF NOT EXISTS idx_job_application_events_job
    ON job_application_events(job_application_id, created_at DESC);
