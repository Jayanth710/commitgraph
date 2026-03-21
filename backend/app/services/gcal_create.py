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

from app.core.security import decrypt_token

logger = logging.getLogger(__name__)

GCAL_API_BASE = "https://www.googleapis.com/calendar/v3"


async def create_commitment_event(
    *,
    account_id: str,
    summary: str,
    due_date: str,
    direction: str,
    owner_email: str | None = None,
    target_email: str | None = None,
    commitment_id: str | None = None,
) -> dict[str, Any] | None:
    from app.db.session import AsyncSessionLocal
    from app.core.security import encrypt_token
    from app.core.config import get_settings

    settings = get_settings()

    # Get tokens
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT access_token_encrypted, refresh_token_encrypted, email_address
                FROM accounts
                WHERE id = :aid AND provider = 'gmail'
                """
            ),
            {"aid": account_id},
        )
        account = result.mappings().first()

    if not account:
        logger.warning("No Gmail account found for id=%s", account_id)
        return None

    access_token = decrypt_token(account["access_token_encrypted"])

    # Try to refresh the token first
    if account["refresh_token_encrypted"]:
        refresh_token = decrypt_token(account["refresh_token_encrypted"])
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                if resp.is_success:
                    new_tokens = resp.json()
                    access_token = new_tokens["access_token"]
                    # Save refreshed token
                    async with AsyncSessionLocal() as db:
                        async with db.begin():
                            await db.execute(
                                text("UPDATE accounts SET access_token_encrypted = :token WHERE id = :aid"),
                                {"token": encrypt_token(access_token), "aid": account_id},
                            )
                    logger.info("Refreshed access token for calendar event creation")
        except Exception as exc:
            logger.warning("Token refresh failed, using existing: %s", exc)

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
            return None

        event_data = response.json()
        logger.info("Created calendar event: id=%s summary=%s due=%s", event_data.get("id"), summary[:50], due_date)
        return event_data

    except Exception as exc:
        logger.exception("Error creating calendar event: %s", exc)
        return None

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