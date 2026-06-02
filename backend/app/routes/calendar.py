"""
Calendar API — surfaces synced Google Calendar events in the app.

GET  /api/calendar/events  → synced events (item_type='calendar_event'), user-scoped
POST /api/calendar/sync    → pull fresh events for the user's Gmail accounts
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user
from app.services.gcal_sync_service import sync_calendar_for_account

router = APIRouter(prefix="/api", tags=["calendar"])


def _is_all_day(start: datetime | None, end: datetime | None) -> bool:
    """All-day events come from Google as a 'date' → stored at 00:00 UTC."""
    if start is None:
        return False
    if start.hour or start.minute or start.second:
        return False
    if end is not None and (end.hour or end.minute or end.second):
        return False
    return True


def _serialize_event(row) -> dict[str, Any]:
    start = row["event_start"]
    end = row["event_end"]
    attendees = row["attendees"]
    if isinstance(attendees, str):
        try:
            attendees = json.loads(attendees)
        except (ValueError, TypeError):
            attendees = []
    return {
        "id": str(row["id"]),
        "title": row["subject"] or "(no title)",
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "all_day": _is_all_day(start, end),
        "location": row["location"],
        "attendees": attendees or [],
        "account_email": row["account_email"],
        "linked_commitment_id": (
            str(row["linked_commitment_id"]) if row["linked_commitment_id"] else None
        ),
    }


@router.get("/calendar/events")
async def list_calendar_events(
    user: dict = Depends(get_current_user),
    account_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    user_id = str(user["id"])
    conditions = [
        "ni.item_type = 'calendar_event'",
        # Scope to this user's mailboxes (the gcal row shares the Gmail email).
        "ga.email_address IN (SELECT email_address FROM accounts WHERE user_id = :user_id AND provider = 'gmail')",
        # Hide events CommitGraph itself created from a commitment — that
        # commitment already shows on the calendar as its own due-date entry.
        "COALESCE(ni.body_text, '') NOT LIKE '%Created by CommitGraph%'",
    ]
    params: dict[str, Any] = {"user_id": user_id}

    if account_id:
        conditions.append(
            "ga.email_address = (SELECT email_address FROM accounts WHERE id = :account_id)"
        )
        params["account_id"] = account_id
    if date_from:
        try:
            params["date_from"] = date.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from (YYYY-MM-DD)")
        conditions.append("ni.event_start >= :date_from")
    if date_to:
        try:
            # inclusive of the whole end day
            params["date_to"] = date.fromisoformat(date_to) + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to (YYYY-MM-DD)")
        conditions.append("ni.event_start < :date_to")

    where_clause = "WHERE " + " AND ".join(conditions)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                f"""
                SELECT
                    ni.id, ni.subject, ni.event_start, ni.event_end,
                    ni.location, ni.attendees,
                    ga.email_address AS account_email,
                    (
                        SELECT el.commitment_id FROM evidence_links el
                        WHERE el.normalized_item_id = ni.id
                          AND el.evidence_type = 'calendar_link'
                        LIMIT 1
                    ) AS linked_commitment_id
                FROM normalized_items ni
                JOIN accounts ga ON ga.id = ni.account_id AND ga.provider = 'gcal'
                {where_clause}
                ORDER BY ni.event_start ASC
                LIMIT 1000
                """
            ),
            params,
        )
        rows = result.mappings().all()

    return {"events": [_serialize_event(r) for r in rows], "total": len(rows)}


@router.post("/calendar/sync")
async def sync_calendar(
    user: dict = Depends(get_current_user),
    account_id: str | None = Query(default=None),
):
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        conditions = ["user_id = :user_id", "provider = 'gmail'"]
        params: dict[str, Any] = {"user_id": user_id}
        if account_id:
            conditions.append("id = :account_id")
            params["account_id"] = account_id
        result = await db.execute(
            text(
                f"SELECT id, email_address FROM accounts WHERE {' AND '.join(conditions)}"
            ),
            params,
        )
        accounts = result.mappings().all()

    if not accounts:
        raise HTTPException(status_code=404, detail="No connected Gmail accounts")

    results = []
    for acct in accounts:
        results.append(
            await sync_calendar_for_account(
                gmail_account_id=str(acct["id"]),
                email_address=acct["email_address"],
                user_id=user_id,
            )
        )

    return {
        "synced": results,
        "events_created": sum(r.get("created", 0) for r in results),
    }
