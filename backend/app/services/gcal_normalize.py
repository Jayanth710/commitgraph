"""
Google Calendar event normalization.

Takes raw Calendar API event data and stores it as normalized_items
with item_type='calendar_event'. Also attempts to link events to
existing commitments via attendee email matching and subject similarity.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.reconciliation import compute_similarity

logger = logging.getLogger(__name__)


def _parse_event_time(time_obj: dict | None) -> datetime | None:
    """Parse a Calendar API time object (dateTime or date) to a datetime."""
    if not time_obj:
        return None

    # All-day events have 'date', timed events have 'dateTime'.
    dt_str = time_obj.get("dateTime") or time_obj.get("date")
    if not dt_str:
        return None

    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _extract_attendees(event: dict) -> list[dict]:
    """Extract attendees from a calendar event."""
    attendees = []
    for attendee in event.get("attendees", []):
        email = attendee.get("email", "").strip().lower()
        if not email:
            continue
        attendees.append({
            "email": email,
            "name": attendee.get("displayName"),
            "response_status": attendee.get("responseStatus"),
        })
    return attendees


async def normalize_calendar_event(
    db: AsyncSession,
    *,
    account_id: str,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Store a calendar event as a source_item + normalized_item.

    Returns dict with status ('created', 'exists', or 'skipped').
    """
    event_id = event.get("id")
    if not event_id:
        return {"status": "skipped", "reason": "no_event_id"}

    # Skip cancelled events.
    if event.get("status") == "cancelled":
        return {"status": "skipped", "reason": "cancelled"}

    idempotency_key = f"gcal:{account_id}:{event_id}"

    # Check if already stored.
    existing = await db.execute(
        text("SELECT id FROM source_items WHERE idempotency_key = :key LIMIT 1"),
        {"key": idempotency_key},
    )
    if existing.scalar_one_or_none():
        return {"status": "exists", "idempotency_key": idempotency_key}

    # Insert source_item.
    source_result = await db.execute(
        text(
            """
            INSERT INTO source_items (account_id, provider, provider_id, provider_data, idempotency_key)
            VALUES (:account_id, 'gcal', :provider_id, CAST(:provider_data AS JSONB), :idempotency_key)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """
        ),
        {
            "account_id": account_id,
            "provider_id": event_id,
            "provider_data": json.dumps(event),
            "idempotency_key": idempotency_key,
        },
    )
    source_item_id = source_result.scalar_one_or_none()
    if not source_item_id:
        return {"status": "exists", "idempotency_key": idempotency_key}

    # Parse event fields.
    summary = event.get("summary") or "(no title)"
    description = event.get("description") or ""
    location = event.get("location")
    event_start = _parse_event_time(event.get("start"))
    event_end = _parse_event_time(event.get("end"))
    attendees = _extract_attendees(event)
    organizer = event.get("organizer", {})
    organizer_email = organizer.get("email", "").strip().lower() or None
    organizer_name = organizer.get("displayName")

    # Build recipients from attendees (for consistency with email schema).
    recipients = [
        {"email": a["email"], "name": a["name"], "type": "to"}
        for a in attendees
    ]

    # Insert normalized_item.
    ni_result = await db.execute(
        text(
            """
            INSERT INTO normalized_items (
                source_item_id, account_id, item_type,
                subject, body_text, sender_email, sender_name,
                recipients, thread_id,
                event_start, event_end, attendees, location,
                processing_status
            )
            VALUES (
                :source_item_id, :account_id, 'calendar_event',
                :subject, :body_text, :sender_email, :sender_name,
                CAST(:recipients AS JSONB), :thread_id,
                :event_start, :event_end, CAST(:attendees AS JSONB), :location,
                'processed'
            )
            RETURNING id
            """
        ),
        {
            "source_item_id": str(source_item_id),
            "account_id": account_id,
            "subject": summary,
            "body_text": description[:4000] if description else None,
            "sender_email": organizer_email,
            "sender_name": organizer_name,
            "recipients": json.dumps(recipients),
            "thread_id": event_id,  # Use event ID as thread for linking
            "event_start": event_start,
            "event_end": event_end,
            "attendees": json.dumps(attendees),
            "location": location,
        },
    )
    normalized_item_id = str(ni_result.scalar_one())

    logger.info(
        "Normalized calendar event: %s → %s",
        event_id,
        normalized_item_id,
    )

    return {
        "status": "created",
        "source_item_id": str(source_item_id),
        "normalized_item_id": normalized_item_id,
        "summary": summary,
    }


async def link_event_to_commitments(
    db: AsyncSession,
    *,
    normalized_item_id: str,
    event_summary: str,
    attendee_emails: list[str],
) -> int:
    """Try to link a calendar event to existing commitments.

    Matching strategies:
    1. Attendee emails match commitment owner/target persons
       AND event title is similar to commitment summary
    2. Event title alone is very similar to a commitment summary (>0.7)

    Returns the number of evidence_links created.
    """
    links_created = 0

    # Find commitments where the owner or target has an attendee email.
    if attendee_emails:
        result = await db.execute(
            text(
                """
                SELECT c.id, c.summary
                FROM commitments c
                JOIN persons p ON p.id = c.owner_person_id OR p.id = c.target_person_id
                WHERE p.email_addresses && :emails
                  AND c.status NOT IN ('abandoned', 'completed')
                ORDER BY c.created_at DESC
                LIMIT 20
                """
            ),
            {"emails": attendee_emails},
        )

        for row in result.mappings().all():
            sim = compute_similarity(event_summary, row["summary"])
            if sim >= 0.4:  # Lower threshold — calendar titles are often short
                # Check if link already exists.
                existing_link = await db.execute(
                    text(
                        """
                        SELECT id FROM evidence_links
                        WHERE commitment_id = :cid AND normalized_item_id = :nid
                        LIMIT 1
                        """
                    ),
                    {"cid": row["id"], "nid": normalized_item_id},
                )
                if existing_link.scalar_one_or_none():
                    continue

                await db.execute(
                    text(
                        """
                        INSERT INTO evidence_links (commitment_id, normalized_item_id, evidence_type, extracted_snippet)
                        VALUES (:cid, :nid, 'calendar_link', :snippet)
                        """
                    ),
                    {
                        "cid": row["id"],
                        "nid": normalized_item_id,
                        "snippet": f"Calendar event: {event_summary}",
                    },
                )
                links_created += 1
                logger.info(
                    "Linked calendar event to commitment %s similarity=%.2f",
                    row["id"], sim,
                )

    return links_created