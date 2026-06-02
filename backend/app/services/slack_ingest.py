"""
Slack message ingestion.

Unlike Gmail (which sends only a historyId and requires a fetch), a Slack event
already carries the message text, so we store it directly: source_item ->
normalized_item (item_type='chat_message') -> publish to process:normalized so
the extractor worker runs on it.

MVP identity handling: a Slack sender has no email, so we key the person by a
synthetic identifier ("slack:<user_id>") stored in sender_email. The
account-owner email (for direction) is the connecting user's email. Both are
rough and will be replaced by the proper platform-scoped identity model.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_token
from app.services.redis_streams import publish_normalized_event_once
from app.services.slack_api import get_slack_user_name

logger = logging.getLogger(__name__)

# Slack message markup that's noise to the extractor.
_SLACK_BROADCAST = re.compile(r"<!(?:channel|here|everyone)>")
_SLACK_SUBTEAM = re.compile(r"<!subteam\^[^|>]+(?:\|([^>]+))?>")
_SLACK_USER_MENTION = re.compile(r"<@[UW][A-Z0-9]+(?:\|([^>]+))?>")
_SLACK_CHANNEL_MENTION = re.compile(r"<#C[A-Z0-9]+(?:\|([^>]+))?>")
_SLACK_LINK = re.compile(r"<(https?://[^|>]+)(?:\|([^>]+))?>")


def _clean_slack_markup(text_in: str | None) -> str:
    """Strip Slack's <...> markup so the extractor sees plain text."""
    if not text_in:
        return ""
    t = _SLACK_BROADCAST.sub("", text_in)
    t = _SLACK_SUBTEAM.sub(lambda m: f"@{m.group(1)}" if m.group(1) else "", t)
    t = _SLACK_USER_MENTION.sub(lambda m: f"@{m.group(1)}" if m.group(1) else "", t)
    t = _SLACK_CHANNEL_MENTION.sub(lambda m: f"#{m.group(1)}" if m.group(1) else "", t)
    t = _SLACK_LINK.sub(lambda m: m.group(2) or m.group(1), t)
    t = unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def _slack_ts_to_dt(ts: str | None) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


async def process_slack_notification(
    db: AsyncSession,
    redis,
    *,
    team_id: str,
    channel: str,
    event_ts: str,
    thread_ts: str,
    slack_user: str,
    text_body: str,
) -> dict[str, Any]:
    provider_id = f"{channel}:{event_ts}"
    sender_identifier = f"slack:{slack_user}" if slack_user else None
    thread_id = thread_ts or channel
    sent_at = _slack_ts_to_dt(event_ts)
    cleaned_body = _clean_slack_markup(text_body)

    owner_email = ""
    source_item_id: str | None = None
    normalized_item_id: str | None = None

    async with db.begin():
        account = (
            await db.execute(
                text(
                    """
                    SELECT a.id, a.provider_user_id, a.access_token_encrypted,
                           u.email AS owner_email
                    FROM accounts a
                    LEFT JOIN users u ON u.id = a.user_id
                    WHERE a.provider = 'slack' AND a.history_id = :team_id
                    LIMIT 1
                    """
                ),
                {"team_id": team_id},
            )
        ).mappings().first()

        if not account:
            logger.warning("No Slack account for team_id=%s; skipping", team_id)
            return {"status": "ignored", "reason": "unknown_team"}

        account_id = str(account["id"])

        # Resolve the sender's Slack id to a human name (cached).
        sender_display_name = slack_user or None
        if slack_user and account["access_token_encrypted"]:
            try:
                resolved = await get_slack_user_name(
                    decrypt_token(account["access_token_encrypted"]), slack_user
                )
                if resolved:
                    sender_display_name = resolved
            except Exception:
                logger.warning("Failed to resolve Slack user name for %s", slack_user)
        # The account owner's identity in Slack-space (slack:<authed_user_id>),
        # so the extractor can tell self (outbound) from others (inbound). Falls
        # back to the user's email if the workspace was connected before we
        # captured authed_user.id (reconnect to populate it).
        owner_email = (
            f"slack:{account['provider_user_id']}"
            if account["provider_user_id"]
            else (account["owner_email"] or "")
        )
        idempotency_key = f"slack:{account_id}:{provider_id}"

        inserted = (
            await db.execute(
                text(
                    """
                    INSERT INTO source_items
                        (account_id, provider, provider_id, provider_data, idempotency_key)
                    VALUES
                        (:account_id, 'slack', :provider_id, CAST(:data AS JSONB), :idem)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "account_id": account_id,
                    "provider_id": provider_id,
                    "data": json.dumps(
                        {
                            "team_id": team_id,
                            "channel": channel,
                            "ts": event_ts,
                            "thread_ts": thread_ts,
                            "user": slack_user,
                            "text": text_body,
                        }
                    ),
                    "idem": idempotency_key,
                },
            )
        ).scalar_one_or_none()

        if inserted is None:
            existing_src = (
                await db.execute(
                    text("SELECT id FROM source_items WHERE idempotency_key = :idem"),
                    {"idem": idempotency_key},
                )
            ).scalar_one_or_none()
            if existing_src is None:
                return {"status": "ignored", "reason": "insert_race"}
            source_item_id = str(existing_src)
        else:
            source_item_id = str(inserted)

        existing_norm = (
            await db.execute(
                text(
                    "SELECT id FROM normalized_items WHERE source_item_id = :sid LIMIT 1"
                ),
                {"sid": source_item_id},
            )
        ).scalar_one_or_none()

        if existing_norm is not None:
            normalized_item_id = str(existing_norm)
        else:
            normalized_item_id = str(
                (
                    await db.execute(
                        text(
                            """
                            INSERT INTO normalized_items (
                                source_item_id, account_id, item_type, subject,
                                body_text, sender_email, sender_name, recipients,
                                thread_id, sent_at, received_at, processing_status
                            )
                            VALUES (
                                :sid, :aid, 'chat_message', NULL,
                                :body, :sender, :sender_name, CAST(:recipients AS JSONB),
                                :thread, :sent_at, :sent_at, 'pending'
                            )
                            RETURNING id
                            """
                        ),
                        {
                            "sid": source_item_id,
                            "aid": account_id,
                            "body": cleaned_body,
                            "sender": sender_identifier,
                            "sender_name": sender_display_name,
                            "recipients": json.dumps([]),
                            "thread": thread_id,
                            "sent_at": sent_at,
                        },
                    )
                ).scalar_one()
            )

    # After commit: hand off to the extractor (deduped by the Lua script).
    if redis is not None and normalized_item_id is not None:
        await publish_normalized_event_once(
            redis,
            normalized_item_id=normalized_item_id,
            source_item_id=source_item_id,
            account_id=account_id,
            email_address=owner_email,
            provider_id=provider_id,
            thread_id=thread_id,
        )

    logger.info(
        "Processed Slack message account=%s channel=%s ts=%s normalized=%s",
        account_id, channel, event_ts, normalized_item_id,
    )
    return {
        "status": "processed",
        "account_id": account_id,
        "normalized_item_id": normalized_item_id,
    }
