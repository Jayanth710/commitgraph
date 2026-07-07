"""
Outlook subscription management.

Creates a Microsoft Graph webhook subscription for a connected Outlook account.
This tells Microsoft: "notify me at my webhook URL when new emails arrive."

Subscriptions expire after ~3 days (4230 minutes max).
The scheduler handles renewal.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.config import get_settings
from app.core.security import decrypt_token
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/outlook/watch", tags=["outlook-watch"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/start")
async def outlook_watch_start(email_address: str):
    """Create a Microsoft Graph subscription for inbox change notifications.

    Requires:
    - The Outlook account to be connected (via /auth/microsoft/start)
    - A publicly accessible webhook URL (ngrok for development)
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                SELECT id, access_token_encrypted
                FROM accounts
                WHERE provider = 'outlook' AND email_address = :email
                LIMIT 1
                """
            ),
            {"email": email_address},
        )
        row = result.mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Outlook account not found")

        account_id = row["id"]
        access_token = decrypt_token(row["access_token_encrypted"])

    # Build the subscription request.
    webhook_url = settings.public_webhook_base_url
    if not webhook_url:
        raise HTTPException(
            status_code=400,
            detail="PUBLIC_WEBHOOK_BASE_URL not set. Set it to your ngrok URL.",
        )

    notification_url = f"{webhook_url}/api/webhooks/outlook"

    # Subscriptions expire after max ~3 days. Set to 2 days for safety.
    expiry = datetime.now(timezone.utc) + timedelta(days=2)

    subscription_payload = {
        "changeType": "created",
        "notificationUrl": notification_url,
        "resource": "me/mailFolders('inbox')/messages",
        "expirationDateTime": expiry.strftime("%Y-%m-%dT%H:%M:%S.0000000Z"),
        "clientState": settings.effective_outlook_client_state,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers=headers,
            json=subscription_payload,
        )

    if response.is_error:
        logger.error("Failed to create Outlook subscription: %s", response.text)
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to create Outlook subscription: {response.text}",
        )

    sub_data = response.json()
    subscription_id = sub_data.get("id")
    expiration = sub_data.get("expirationDateTime")

    # Parse expiration and store.
    watch_expiry = None
    if expiration:
        try:
            watch_expiry = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    UPDATE accounts
                    SET watch_expiry = :watch_expiry,
                        history_id = :subscription_id,
                        sync_status = 'active',
                        last_sync_at = now()
                    WHERE id = :account_id
                    """
                ),
                {
                    "watch_expiry": watch_expiry,
                    "subscription_id": subscription_id,
                    "account_id": account_id,
                },
            )

    logger.info(
        "Outlook subscription created for %s: id=%s expires=%s",
        email_address, subscription_id, watch_expiry,
    )

    return {
        "message": "Outlook watch started",
        "email_address": email_address,
        "subscription_id": subscription_id,
        "watch_expiry": watch_expiry.isoformat() if watch_expiry else None,
    }