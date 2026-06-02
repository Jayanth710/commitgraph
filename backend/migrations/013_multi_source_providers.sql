-- Widen provider / item_type constraints so the schema accepts chat sources
-- (Slack, Discord) alongside email + calendar. This is the safe, additive half
-- of the multi-source data-model work.
--
-- The harder half — generalizing `persons` from email-keyed identity to
-- platform-scoped identities (Slack/Discord user IDs) — is intentionally NOT
-- done here. It should land with the first chat adapter (Slack), where it can
-- be validated against a real non-email identity instead of built blind.
--
-- Login/identity (the `users` table) is unaffected: users still authenticate
-- with Google; Slack/Discord are connected *sources* (accounts) under a user.
--
-- Constraint names below are the Postgres defaults for the inline column CHECKs
-- created in 001_initial_schema.sql. IF EXISTS keeps this safe to re-run.

ALTER TABLE accounts DROP CONSTRAINT IF EXISTS accounts_provider_check;
ALTER TABLE accounts ADD CONSTRAINT accounts_provider_check
    CHECK (provider IN ('gmail', 'outlook', 'gcal', 'slack', 'discord'));

ALTER TABLE source_items DROP CONSTRAINT IF EXISTS source_items_provider_check;
ALTER TABLE source_items ADD CONSTRAINT source_items_provider_check
    CHECK (provider IN ('gmail', 'outlook', 'gcal', 'slack', 'discord'));

ALTER TABLE normalized_items DROP CONSTRAINT IF EXISTS normalized_items_item_type_check;
ALTER TABLE normalized_items ADD CONSTRAINT normalized_items_item_type_check
    CHECK (item_type IN ('email', 'calendar_event', 'chat_message'));
