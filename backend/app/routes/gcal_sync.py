"""
Google Calendar sync endpoint.

POST /gcal/sync?email_address=you@gmail.com

Triggers a calendar sync for the specified Gmail account.
First call does a full sync (past 30 days + next 60 days).
Subsequent calls use the stored syncToken for incremental updates.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.security import decrypt_token
from app.db.session import AsyncSessionLocal
from app.services.gcal_api import fetch_calendar_events
from app.services.gcal_normalize import (
    link_event_to_commitments,
    normalize_calendar_event,
)

router = APIRouter(prefix="/gcal", tags=["google-calendar"])
logger = logging.getLogger(__name__)


@router.post("/sync")
async def gcal_sync(email_address: str):
    """Sync calendar events for a connected Gmail account.

    Uses the same OAuth tokens as Gmail (calendar.readonly scope was
    added to the Google OAuth consent).

    The sync_token is stored in a separate 'gcal' account row
    so it doesn't interfere with Gmail's history_id.
    """
    async with AsyncSessionLocal() as db:
        # Get the Gmail account's access token.
        result = await db.execute(
            text(
                """
                SELECT id, access_token_encrypted
                FROM accounts
                WHERE provider = 'gmail' AND email_address = :email
                LIMIT 1
                """
            ),
            {"email": email_address},
        )
        gmail_account = result.mappings().first()

        if not gmail_account:
            raise HTTPException(status_code=404, detail="Gmail account not found")

        # Check for an existing gcal account row (stores the sync token).
        gcal_result = await db.execute(
            text(
                """
                SELECT id, history_id as sync_token
                FROM accounts
                WHERE provider = 'gcal' AND email_address = :email
                LIMIT 1
                """
            ),
            {"email": email_address},
        )
        gcal_account = gcal_result.mappings().first()

        # Decrypt access token.
        access_token = decrypt_token(gmail_account["access_token_encrypted"])
        sync_token = gcal_account["sync_token"] if gcal_account else None

    # Fetch events from Calendar API.
    cal_data = await fetch_calendar_events(access_token, sync_token=sync_token)
    events = cal_data["events"]
    next_sync_token = cal_data["next_sync_token"]

    # Determine the account_id for storing events.
    # Use a dedicated 'gcal' account row.
    async with AsyncSessionLocal() as db:
        async with db.begin():
            if gcal_account:
                gcal_account_id = str(gcal_account["id"])
                # Update sync token.
                await db.execute(
                    text(
                        """
                        UPDATE accounts
                        SET history_id = :sync_token, last_sync_at = now()
                        WHERE id = :account_id
                        """
                    ),
                    {"sync_token": next_sync_token, "account_id": gcal_account_id},
                )
            else:
                # Create a gcal account row to store the sync token.
                insert_result = await db.execute(
                    text(
                        """
                        INSERT INTO accounts (provider, email_address, display_name,
                                              sync_status, history_id)
                        VALUES ('gcal', :email, :email, 'active', :sync_token)
                        RETURNING id
                        """
                    ),
                    {"email": email_address, "sync_token": next_sync_token},
                )
                gcal_account_id = str(insert_result.scalar_one())

    # Normalize each event and try to link to commitments.
    created = 0
    skipped = 0
    linked = 0

    async with AsyncSessionLocal() as db:
        async with db.begin():
            for event in events:
                result = await normalize_calendar_event(
                    db,
                    account_id=gcal_account_id,
                    event=event,
                )

                if result["status"] == "created":
                    created += 1

                    # Try to link to existing commitments.
                    attendee_emails = [
                        a["email"] for a in event.get("attendees", [])
                        if a.get("email")
                    ]
                    links = await link_event_to_commitments(
                        db,
                        normalized_item_id=result["normalized_item_id"],
                        event_summary=event.get("summary", ""),
                        attendee_emails=attendee_emails,
                    )
                    linked += links
                else:
                    skipped += 1

    logger.info(
        "Calendar sync for %s: %d events created, %d skipped, %d linked to commitments",
        email_address, created, skipped, linked,
    )

    return {
        "message": "Calendar sync complete",
        "email_address": email_address,
        "events_created": created,
        "events_skipped": skipped,
        "commitment_links_created": linked,
        "sync_token_stored": bool(next_sync_token),
    }