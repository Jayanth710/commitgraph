"""
Microsoft Graph webhook handler for Outlook.

Key differences from Gmail webhook:
    1. Validation: When creating a subscription, Microsoft sends a GET
       with ?validationToken=... Your endpoint MUST echo it back as
       text/plain within seconds, or the subscription creation fails.

    2. Speed: Microsoft requires a 202 response within 3 seconds.
       We acknowledge immediately and queue to Redis for async processing.

    3. Payload format: Notifications come as a JSON array of change objects,
       each containing the resource path (e.g., /me/messages/{id}).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.services.redis_streams import get_redis_client

router = APIRouter(prefix="/api/webhooks", tags=["outlook-webhooks"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/outlook", status_code=status.HTTP_202_ACCEPTED)
async def outlook_webhook(
    request: Request,
    validationToken: str | None = Query(default=None),
):
    """Handle Microsoft Graph webhook notifications.

    Two modes:
    1. Subscription validation: Microsoft sends ?validationToken=xxx
       → echo it back as text/plain
    2. Change notification: Microsoft sends JSON with notification data
       → queue to Redis, respond 202 immediately
    """
    # Mode 1: Subscription validation.
    if validationToken:
        logger.info("Outlook webhook validation: echoing token")
        return PlainTextResponse(content=validationToken, status_code=200)

    # Mode 2: Change notification.
    body = await request.json()
    logger.info("Outlook webhook notification received")

    notifications = body.get("value", [])

    redis = get_redis_client()
    try:
        queued = 0
        for notification in notifications:
            resource = notification.get("resource", "")
            change_type = notification.get("changeType", "")

            # Reject forged notifications: the clientState must match the secret
            # we set when creating the subscription.
            if notification.get("clientState") != settings.effective_outlook_client_state:
                logger.warning("Outlook notification rejected: clientState mismatch")
                continue

            # Extract the message ID from the resource path.
            # Resource looks like: "me/messages/{message_id}"
            # or "Users/{user_id}/messages/{message_id}"
            parts = resource.split("/")
            message_id = None
            for i, part in enumerate(parts):
                if part == "messages" and i + 1 < len(parts):
                    message_id = parts[i + 1]
                    break

            if not message_id:
                logger.warning("Could not extract message_id from resource: %s", resource)
                continue

            # Find the subscription ID to identify the account.
            subscription_id = notification.get("subscriptionId", "")

            from datetime import datetime, timezone
            await redis.xadd(
                "ingest:raw",
                {
                    "provider": "outlook",
                    "message_id": message_id,
                    "change_type": change_type,
                    "subscription_id": subscription_id,
                    "resource": resource,
                    "enqueued_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            queued += 1

        logger.info("Outlook webhook: queued %d notifications to ingest:raw", queued)

        return {"status": "accepted", "queued": queued}

    except Exception as exc:
        logger.exception("Failed to process Outlook webhook")
        # Still return 202 to prevent Microsoft from retrying aggressively.
        return {"status": "error", "detail": str(exc)}
    finally:
        await redis.aclose()


@router.get("/outlook")
async def outlook_webhook_validation(
    validationToken: str | None = Query(default=None),
):
    """Handle GET-based validation during subscription creation.

    Some Microsoft Graph versions send validation as GET instead of POST.
    """
    if validationToken:
        logger.info("Outlook webhook GET validation: echoing token")
        return PlainTextResponse(content=validationToken, status_code=200)

    return {"status": "ok", "message": "Outlook webhook endpoint active"}