CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL CHECK (provider IN ('gmail', 'outlook', 'gcal')),
    email_address TEXT NOT NULL,
    display_name TEXT,
    access_token_encrypted BYTEA,
    refresh_token_encrypted BYTEA,
    token_expires_at TIMESTAMPTZ,
    sync_status TEXT DEFAULT 'active'
        CHECK (sync_status IN ('active', 'degraded', 'disconnected', 'error')),
    last_sync_at TIMESTAMPTZ,
    watch_expiry TIMESTAMPTZ,
    history_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('gmail', 'outlook', 'gcal')),
    provider_id TEXT NOT NULL,
    provider_data JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    idempotency_key TEXT UNIQUE NOT NULL,
    UNIQUE(account_id, provider, provider_id)
);

CREATE TABLE IF NOT EXISTS normalized_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_item_id UUID NOT NULL REFERENCES source_items(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL CHECK (item_type IN ('email', 'calendar_event')),
    subject TEXT,
    body_text TEXT,
    body_html TEXT,
    sender_email TEXT,
    sender_name TEXT,
    recipients JSONB,
    thread_id TEXT,
    in_reply_to TEXT,
    sent_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ,
    event_start TIMESTAMPTZ,
    event_end TIMESTAMPTZ,
    attendees JSONB,
    location TEXT,
    normalized_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS persons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name TEXT,
    email_addresses TEXT[] NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_self BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS commitments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_person_id UUID NOT NULL REFERENCES persons(id) ON DELETE RESTRICT,
    target_person_id UUID REFERENCES persons(id) ON DELETE SET NULL,
    direction TEXT NOT NULL CHECK (direction IN ('outbound', 'inbound')),
    summary TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    commitment_type TEXT CHECK (commitment_type IN (
        'deliverable', 'follow_up', 'response_needed',
        'meeting_prep', 'review', 'decision', 'other'
    )),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    due_date TIMESTAMPTZ,
    due_date_confidence FLOAT,
    status TEXT NOT NULL DEFAULT 'detected' CHECK (status IN (
        'detected',
        'confirmed',
        'in_progress',
        'completed',
        'overdue',
        'abandoned',
        'delegated'
    )),
    confidence_score FLOAT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status_changed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS evidence_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    commitment_id UUID NOT NULL REFERENCES commitments(id) ON DELETE CASCADE,
    normalized_item_id UUID NOT NULL REFERENCES normalized_items(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL CHECK (evidence_type IN (
        'origin',
        'update',
        'completion_signal',
        'calendar_link',
        'follow_up'
    )),
    extracted_snippet TEXT,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    commitment_id UUID NOT NULL REFERENCES commitments(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    suggested_action TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'dismissed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    user_decision TEXT
);

CREATE INDEX IF NOT EXISTS idx_normalized_thread
    ON normalized_items(thread_id, account_id);

CREATE INDEX IF NOT EXISTS idx_normalized_sender
    ON normalized_items(sender_email);

CREATE INDEX IF NOT EXISTS idx_normalized_status
    ON normalized_items(processing_status);

CREATE INDEX IF NOT EXISTS idx_persons_emails
    ON persons USING GIN(email_addresses);

CREATE INDEX IF NOT EXISTS idx_commitments_status
    ON commitments(status);

CREATE INDEX IF NOT EXISTS idx_commitments_owner
    ON commitments(owner_person_id);

CREATE INDEX IF NOT EXISTS idx_commitments_due
    ON commitments(due_date)
    WHERE status NOT IN ('completed', 'abandoned');

CREATE INDEX IF NOT EXISTS idx_evidence_commitment
    ON evidence_links(commitment_id);