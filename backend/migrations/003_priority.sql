ALTER TABLE commitments ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_commitments_priority ON commitments(priority);