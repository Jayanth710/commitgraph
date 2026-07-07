-- Per-user daily LLM spend, so one user's runaway usage (e.g. a huge inbox
-- backfill) can't rack up unbounded cost. The worker sets the current user in a
-- contextvar before extraction; the LLM gateway checks this table before each
-- call and accumulates cost after.

CREATE TABLE IF NOT EXISTS llm_daily_spend (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day DATE NOT NULL DEFAULT CURRENT_DATE,
    cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, day)
);
