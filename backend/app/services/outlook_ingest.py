"""
Outlook email ingest service.

Processes Outlook webhook notifications from the ingest:raw stream.
Fetches the full message from Microsoft Graph, normalizes it,
and emits to process:normalized for the extraction pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.outlook_api import get_outlook_message, OutlookApiError
from app.services.outlook_normalize import normalize_outlook_message
from app.services.redis_streams import publish_normalized_event_once

logger = logging.getLogger(__name__)


async def process_outlook_notification(
    db: AsyncSession,
    redis: Redis,
    *,
    message_id: str,
    subscription_id: str,
) -> dict[str, Any]:
    """Process a single Outlook webhook notification.

    1. Find the account by subscription_id (stored in history_id)
    2. Fetch the full message from Microsoft Graph
    3. Normalize it
    4. Emit to process:normalized stream

    Returns a result dict with status and counts.
    """
    async with db.begin():
        # Find the Outlook account by subscription ID.
        result = await db.execute(
            text(
                """
                SELECT id, email_address, access_token_encrypted,
                       refresh_token_encrypted, history_id
                FROM accounts
                WHERE provider = 'outlook'
                  AND history_id = :subscription_id
                LIMIT 1
                """
            ),
            {"subscription_id": subscription_id},
        )
        account = result.mappings().first()

        if not account:
            # Fallback: try to find any Outlook account.
            result = await db.execute(
                text(
                    """
                    SELECT id, email_address, access_token_encrypted,
                           refresh_token_encrypted, history_id
                    FROM accounts
                    WHERE provider = 'outlook'
                      AND sync_status = 'active'
                    LIMIT 1
                    """
                )
            )
            account = result.mappings().first()

        if not account:
            logger.warning("No Outlook account found for subscription=%s", subscription_id)
            return {"status": "ignored", "reason": "account_not_found"}

        account = dict(account)
        account_id = str(account["id"])

        # Fetch the full message from Microsoft Graph.
        try:
            message = await get_outlook_message(db, account, message_id)
        except OutlookApiError as exc:
            if "404" in str(exc) or "NotFound" in str(exc):
                logger.warning("Outlook message %s not found, skipping", message_id[:20])
                return {"status": "skipped", "reason": "message_not_found"}
            raise

        # Normalize and store.
        norm_result = await normalize_outlook_message(
            db,
            account_id=account_id,
            message=message,
        )

        if norm_result["status"] != "created":
            return {"status": "skipped", "reason": "already_exists"}

        # Emit to process:normalized for the extraction pipeline.
        emit_result = await publish_normalized_event_once(
            redis,
            normalized_item_id=norm_result["normalized_item_id"],
            source_item_id=norm_result["source_item_id"],
            account_id=account_id,
            email_address=account["email_address"],
            provider_id=message_id,
            thread_id=norm_result.get("thread_id"),
        )

        logger.info(
            "Processed Outlook notification: message=%s account=%s "
            "normalized=%s emit=%s",
            message_id[:20],
            account["email_address"],
            norm_result["normalized_item_id"],
            emit_result["status"],
        )

        return {
            "status": "processed",
            "normalized_item_id": norm_result["normalized_item_id"],
            "subject": norm_result.get("subject"),
        }