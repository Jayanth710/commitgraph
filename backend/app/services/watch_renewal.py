"""
Watch subscription renewal.

Gmail and Outlook push subscriptions expire (Gmail ~7 days, Outlook ~3 days).
Without renewal, ingestion silently stops once a watch lapses. This service is
run periodically by the scheduler: it finds accounts whose watch is expiring
soon (or already lapsed), re-establishes the subscription, and marks the
account ``sync_status = 'error'`` when renewal fails so the dead watch is
visible in the dashboard instead of failing silently.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.gmail_watch import start_gmail_watch
from app.services.outlook_api import graph_request

logger = logging.getLogger(__name__)
settings = get_settings()

# Outlook subscriptions max out at ~3 days; renew to 2 for safety, matching
# the creation path in routes/outlook_watch.py.
OUTLOOK_RENEWAL_DAYS = 2


async def run_due_watch_renewals() -> dict[str, int]:
    """Renew every Gmail/Outlook watch that expires within the buffer window.

    Returns counts of {renewed, failed, skipped}. Never raises — per-account
    failures are isolated and recorded as sync_status='error'.
    """
    cutoff = datetime.now(timezone.utc) + timedelta(
        seconds=settings.watch_renewal_buffer_seconds
    )

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT id, provider
                    FROM accounts
                    WHERE provider IN ('gmail', 'outlook')
                      AND watch_expiry IS NOT NULL
                      AND sync_status <> 'disconnected'
                      AND watch_expiry < :cutoff
                    ORDER BY watch_expiry ASC
                    """
                ),
                {"cutoff": cutoff},
            )
        ).mappings().all()

    renewed = 0
    failed = 0
    skipped = 0

    for row in rows:
        account_id = row["id"]
        provider = row["provider"]
        try:
            if provider == "gmail":
                await _renew_gmail_watch(account_id)
            elif provider == "outlook":
                await _renew_outlook_watch(account_id)
            else:
                skipped += 1
                continue
            renewed += 1
        except Exception:
            logger.exception(
                "Watch renewal failed for account=%s provider=%s", account_id, provider
            )
            await _mark_watch_error(account_id)
            failed += 1

    return {"renewed": renewed, "failed": failed, "skipped": skipped}


async def _renew_gmail_watch(account_id) -> None:
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                text(
                    """
                    SELECT id, access_token_encrypted, refresh_token_encrypted
                    FROM accounts
                    WHERE id = :id AND provider = 'gmail'
                    LIMIT 1
                    """
                ),
                {"id": account_id},
            )
        ).mappings().first()

        if not row or not row["access_token_encrypted"]:
            raise RuntimeError(f"Gmail account {account_id} has no stored access token")

        watch_data = await start_gmail_watch(db, dict(row))

        history_id = watch_data.get("historyId")
        expiration_ms = watch_data.get("expiration")
        watch_expiry = (
            datetime.fromtimestamp(int(expiration_ms) / 1000, tz=timezone.utc)
            if expiration_ms
            else None
        )

        await db.execute(
            text(
                """
                UPDATE accounts
                SET history_id = :history_id,
                    watch_expiry = :watch_expiry,
                    last_sync_at = now(),
                    sync_status = 'active'
                WHERE id = :id
                """
            ),
            {"history_id": history_id, "watch_expiry": watch_expiry, "id": account_id},
        )
        await db.commit()

    logger.info("Renewed Gmail watch account=%s expiry=%s", account_id, watch_expiry)


async def _renew_outlook_watch(account_id) -> None:
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                text(
                    """
                    SELECT id, access_token_encrypted, refresh_token_encrypted, history_id
                    FROM accounts
                    WHERE id = :id AND provider = 'outlook'
                    LIMIT 1
                    """
                ),
                {"id": account_id},
            )
        ).mappings().first()

        if not row:
            raise RuntimeError(f"Outlook account {account_id} not found")

        subscription_id = row["history_id"]
        if not subscription_id:
            raise RuntimeError(
                f"Outlook account {account_id} has no subscription id; needs reconnect"
            )

        new_expiry = datetime.now(timezone.utc) + timedelta(days=OUTLOOK_RENEWAL_DAYS)

        await graph_request(
            db,
            dict(row),
            "PATCH",
            f"/subscriptions/{subscription_id}",
            json_body={
                "expirationDateTime": new_expiry.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
            },
        )

        await db.execute(
            text(
                """
                UPDATE accounts
                SET watch_expiry = :watch_expiry,
                    last_sync_at = now(),
                    sync_status = 'active'
                WHERE id = :id
                """
            ),
            {"watch_expiry": new_expiry, "id": account_id},
        )
        await db.commit()

    logger.info(
        "Renewed Outlook subscription account=%s sub=%s expiry=%s",
        account_id,
        subscription_id,
        new_expiry,
    )


async def _mark_watch_error(account_id) -> None:
    """Best-effort flag so a lapsed watch surfaces in the dashboard. Alerts via
    Sentry only on the first transition into error (avoids per-cycle spam)."""
    from app.core.observability import capture_message

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    "UPDATE accounts SET sync_status = 'error' "
                    "WHERE id = :id AND sync_status <> 'error' RETURNING id"
                ),
                {"id": account_id},
            )
            changed = result.first() is not None
            await db.commit()
        if changed:
            capture_message(
                f"Watch renewal failed; account {account_id} marked sync_status=error",
                level="error",
            )
    except Exception:
        logger.exception("Failed to mark sync_status=error for account=%s", account_id)
