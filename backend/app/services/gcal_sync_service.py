"""
Google Calendar sync (reusable, user-scoped).

Pulls events for a connected Gmail account into normalized_items
(item_type='calendar_event') under a dedicated 'gcal' account row, and links
them to commitments. Used by the user-facing /api/calendar/sync endpoint and
the legacy /gcal/sync route.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.services.gcal_api import fetch_calendar_events
from app.services.gcal_normalize import (
    link_event_to_commitments,
    normalize_calendar_event,
)
from app.services.google_token import get_fresh_google_access_token

logger = logging.getLogger(__name__)


async def sync_calendar_for_account(
    *,
    gmail_account_id: str,
    email_address: str,
    user_id: str | None,
) -> dict[str, Any]:
    """Sync one Gmail account's calendar. Returns a result summary dict."""
    access_token = await get_fresh_google_access_token(gmail_account_id)
    if not access_token:
        return {"status": "skipped", "reason": "no_token", "email": email_address}

    # The sync token lives on a dedicated 'gcal' account row (separate from the
    # Gmail account's history_id).
    async with AsyncSessionLocal() as db:
        gcal_result = await db.execute(
            text(
                """
                SELECT id, history_id AS sync_token
                FROM accounts
                WHERE provider = 'gcal' AND email_address = :email
                LIMIT 1
                """
            ),
            {"email": email_address},
        )
        gcal_account = gcal_result.mappings().first()

    sync_token = gcal_account["sync_token"] if gcal_account else None

    try:
        cal_data = await fetch_calendar_events(access_token, sync_token=sync_token)
    except RuntimeError as exc:
        logger.warning("Calendar fetch failed for %s: %s", email_address, exc)
        return {"status": "error", "reason": str(exc)[:200], "email": email_address}

    events = cal_data["events"]
    next_sync_token = cal_data["next_sync_token"]

    async with AsyncSessionLocal() as db:
        async with db.begin():
            if gcal_account:
                gcal_account_id = str(gcal_account["id"])
                await db.execute(
                    text(
                        """
                        UPDATE accounts
                        SET history_id = :sync_token,
                            last_sync_at = now(),
                            user_id = COALESCE(user_id, :user_id)
                        WHERE id = :account_id
                        """
                    ),
                    {
                        "sync_token": next_sync_token,
                        "account_id": gcal_account_id,
                        "user_id": user_id,
                    },
                )
            else:
                insert_result = await db.execute(
                    text(
                        """
                        INSERT INTO accounts (provider, email_address, display_name,
                                              sync_status, history_id, user_id, last_sync_at)
                        VALUES ('gcal', :email, :email, 'active', :sync_token, :user_id, now())
                        RETURNING id
                        """
                    ),
                    {"email": email_address, "sync_token": next_sync_token, "user_id": user_id},
                )
                gcal_account_id = str(insert_result.scalar_one())

    created = skipped = linked = 0
    async with AsyncSessionLocal() as db:
        async with db.begin():
            for event in events:
                result = await normalize_calendar_event(
                    db, account_id=gcal_account_id, event=event
                )
                if result["status"] == "created":
                    created += 1
                    attendee_emails = [
                        a["email"] for a in event.get("attendees", []) if a.get("email")
                    ]
                    linked += await link_event_to_commitments(
                        db,
                        normalized_item_id=result["normalized_item_id"],
                        event_summary=event.get("summary", ""),
                        attendee_emails=attendee_emails,
                    )
                else:
                    skipped += 1

    logger.info(
        "Calendar sync %s: %d created, %d skipped, %d linked",
        email_address, created, skipped, linked,
    )
    return {
        "status": "ok",
        "email": email_address,
        "created": created,
        "skipped": skipped,
        "linked": linked,
    }
