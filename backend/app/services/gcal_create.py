"""
Create Google Calendar events from extracted commitments.

When a commitment with a due date is extracted, create a calendar
event as a reminder. This makes commitments visible in the user's
Google Calendar alongside their other events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text

logger = logging.getLogger(__name__)

GCAL_API_BASE = "https://www.googleapis.com/calendar/v3"


class CalendarEventError(Exception):
    """Raised when the Google Calendar API rejects an event create request."""


async def create_commitment_event(
    *,
    account_id: str,
    summary: str,
    due_date: str,
    direction: str,
    owner_email: str | None = None,
    target_email: str | None = None,
    commitment_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    from app.db.session import AsyncSessionLocal
    from app.services.google_token import get_fresh_google_access_token

    # Candidate Gmail accounts for the event: the commitment's source account
    # first, then the user's other Gmail accounts. This way a stale account
    # whose token can't be decrypted doesn't block the reminder — it just lands
    # on another of the user's calendars.
    candidate_ids: list[str] = [account_id]
    if user_id:
        async with AsyncSessionLocal() as db:
            others = (
                await db.execute(
                    text(
                        "SELECT id FROM accounts "
                        "WHERE user_id = :uid AND provider = 'gmail' AND id <> :aid"
                    ),
                    {"uid": user_id, "aid": account_id},
                )
            ).scalars().all()
        candidate_ids.extend(str(o) for o in others)

    access_token: str | None = None
    for cand in candidate_ids:
        access_token = await get_fresh_google_access_token(cand)
        if access_token:
            break

    if not access_token:
        raise CalendarEventError(
            "Couldn't access your Google Calendar — please reconnect a Gmail "
            "account in Settings, then try again."
        )

    # Build the calendar event
    prefix = "📤 You committed:" if direction == "outbound" else "📥 Committed to you:"
    event_summary = f"{prefix} {summary}"

    try:
        due = datetime.fromisoformat(due_date)
    except (ValueError, TypeError):
        logger.warning("Invalid due_date: %s", due_date)
        return None

    event_body: dict[str, Any] = {
        "summary": event_summary,
        "description": _build_description(
            summary=summary,
            direction=direction,
            owner_email=owner_email,
            target_email=target_email,
            commitment_id=commitment_id,
        ),
        "start": {"date": due.strftime("%Y-%m-%d")},
        "end": {"date": (due + timedelta(days=1)).strftime("%Y-%m-%d")},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 60 * 24},
                {"method": "popup", "minutes": 60},
            ],
        },
        "colorId": "11" if direction == "outbound" else "10",
    }

    if target_email and direction == "outbound":
        event_body["attendees"] = [{"email": target_email}]

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GCAL_API_BASE}/calendars/primary/events",
                headers=headers,
                json=event_body,
            )

        if response.is_error:
            logger.error("Failed to create calendar event: %s %s", response.status_code, response.text)
            if response.status_code in (401, 403):
                raise CalendarEventError(
                    "Google rejected the request (insufficient calendar permission). "
                    "Reconnect your Google account and grant calendar access "
                    "(the 'calendar.events' scope)."
                )
            raise CalendarEventError(
                f"Google Calendar API error {response.status_code}: {response.text[:300]}"
            )

        event_data = response.json()
        logger.info("Created calendar event: id=%s due=%s", event_data.get("id"), due_date)
        return event_data

    except CalendarEventError:
        raise
    except Exception as exc:
        logger.exception("Error creating calendar event: %s", exc)
        raise CalendarEventError(f"Could not reach Google Calendar: {exc}")

def _build_description(
    *,
    summary: str,
    direction: str,
    owner_email: str | None,
    target_email: str | None,
    commitment_id: str | None,
) -> str:
    """Build a rich description for the calendar event."""
    lines = [
        f"Commitment: {summary}",
        "",
        f"Direction: {'You committed (outbound)' if direction == 'outbound' else 'Committed to you (inbound)'}",
    ]

    if owner_email:
        lines.append(f"From: {owner_email}")
    if target_email:
        lines.append(f"To: {target_email}")

    lines.append("")
    lines.append("— Created by CommitGraph")

    if commitment_id:
        lines.append(f"Commitment ID: {commitment_id}")

    return "\n".join(lines)