-- Store the connecting user's platform user id (e.g. Slack authed_user.id from
-- the OAuth response). This lets us recognize when a chat message was sent by
-- the account owner themselves -> direction 'outbound' ("I owe") vs by someone
-- else -> 'inbound'. Email accounts already identify "self" via email_address.

ALTER TABLE accounts ADD COLUMN IF NOT EXISTS provider_user_id TEXT;
