"""
Google Calendar API client.

Fetches calendar events using incremental sync:
    1. First sync: fetch events from past 30 days + next 60 days → get syncToken
    2. Subsequent syncs: pass syncToken → get only changed events + new syncToken

The syncToken is stored in the accounts table (reusing history_id field
for gcal accounts, or we can add a dedicated column later).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


logger = logging.getLogger(__name__)

GCAL_API_BASE = "https://www.googleapis.com/calendar/v3"


async def _gcal_request(
    access_token: str,
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the Google Calendar API."""
    url = f"{GCAL_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, url, headers=headers, params=params)

    if response.is_error:
        raise RuntimeError(
            f"Calendar API error: {method} {path} → {response.status_code} {response.text}"
        )

    return response.json()


async def fetch_calendar_events(
    access_token: str,
    *,
    sync_token: str | None = None,
) -> dict[str, Any]:
    """Fetch calendar events, either full sync or incremental.

    Args:
        access_token: Google OAuth access token.
        sync_token: If provided, fetch only changes since this token.
                    If None, do a full sync (past 30 days + next 60 days).

    Returns:
        Dict with:
            - events: list of calendar event dicts
            - next_sync_token: token for the next incremental sync
    """
    all_events: list[dict] = []
    page_token: str | None = None

    while True:
        params: dict[str, str] = {
            "singleEvents": "true",       # Expand recurring events
            "orderBy": "startTime",
            "maxResults": "250",
        }

        if sync_token and page_token is None:
            # Incremental sync — use syncToken.
            params["syncToken"] = sync_token
        elif not sync_token and page_token is None:
            # Full sync — set time bounds.
            now = datetime.now(timezone.utc)
            time_min = (now - timedelta(days=30)).isoformat()
            time_max = (now + timedelta(days=60)).isoformat()
            params["timeMin"] = time_min
            params["timeMax"] = time_max

        if page_token:
            params["pageToken"] = page_token

        try:
            data = await _gcal_request(access_token, "GET", "/calendars/primary/events", params=params)
        except RuntimeError as exc:
            # If syncToken is invalid (expired), fall back to full sync.
            if sync_token and "410" in str(exc):
                logger.warning("Calendar sync token expired, falling back to full sync")
                return await fetch_calendar_events(access_token, sync_token=None)
            raise

        items = data.get("items", [])
        all_events.extend(items)

        page_token = data.get("nextPageToken")
        if not page_token:
            next_sync_token = data.get("nextSyncToken")
            break

    logger.info("Fetched %d calendar events (sync_token=%s)", len(all_events), bool(sync_token))

    return {
        "events": all_events,
        "next_sync_token": next_sync_token,
    }