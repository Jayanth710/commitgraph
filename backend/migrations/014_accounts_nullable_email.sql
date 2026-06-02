-- A connected source isn't always an email account. A Slack account is a
-- workspace/team; a Discord account is a guild/bot. Relax the NOT NULL on
-- accounts.email_address so non-email sources can be represented (their human
-- label goes in display_name; the provider's account id goes in history_id,
-- consistent with how the Outlook subscription id is already stored there).
--
-- Additive and safe: existing email accounts keep their address.

ALTER TABLE accounts ALTER COLUMN email_address DROP NOT NULL;
