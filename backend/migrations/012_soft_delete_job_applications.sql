ALTER TABLE job_applications
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_job_applications_active_user_status
    ON job_applications(user_id, deleted_at, status, updated_at DESC);
