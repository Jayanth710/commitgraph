"""
Gmail webhook — receives Pub/Sub push and enqueues for async processing.

Queue-primary: the webhook does the minimum (verify the push is genuinely from
our Pub/Sub subscription, then enqueue to ingest:raw) and acks fast. The
normalizer/extractor workers do the Gmail fetch + LLM extraction off the
request path. This keeps the webhook well under any push ack deadline, avoids
redelivery/duplicate work from slow LLM calls, and matches the model the other
sources need (Slack's <3s ack, Discord's gateway consumer).

Requires the workers to be running — there is no inline fallback.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import get_settings
from app.services.pubsub_auth import (
    PubSubAuthError,
    pubsub_auth_enforced,
    verify_pubsub_token,
)
from app.services.redis_streams import get_redis_client

router = APIRouter(prefix="/api/webhooks", tags=["gmail-webhooks"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/gmail", status_code=status.HTTP_200_OK)
async def gmail_webhook(request: Request):
    # Verify the push request actually came from our Pub/Sub subscription.
    if pubsub_auth_enforced():
        try:
            await verify_pubsub_token(request.headers.get("Authorization"))
        except PubSubAuthError as exc:
            logger.warning("Rejected unauthenticated Gmail webhook: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid pub/sub token",
            ) from exc
    else:
        logger.warning(
            "Gmail webhook auth is NOT enforced; set PUBSUB_VERIFICATION_EMAIL "
            "for production"
        )

    body = await request.json()
    message = body.get("message", {})
    data_b64 = message.get("data", "")

    if not data_b64:
        return {"status": "ignored", "reason": "no_data"}

    decoded = base64.b64decode(data_b64).decode("utf-8")
    payload = json.loads(decoded)

    email_address = payload.get("emailAddress", "")
    history_id = payload.get("historyId", "")

    if not email_address or not history_id:
        return {"status": "ignored", "reason": "missing_fields"}

    logger.info("Gmail webhook: email=%s historyId=%s", email_address, history_id)

    # Enqueue and ack fast — the normalizer worker fetches + processes.
    redis = None
    try:
        redis = get_redis_client()
        await redis.xadd(
            settings.stream_ingest_raw,
            {
                "provider": "gmail",
                "email_address": email_address,
                "history_id": history_id,
                "enqueued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info("Queued to ingest:raw: email=%s historyId=%s", email_address, history_id)
        return {"status": "queued"}

    except Exception as exc:
        # Return 503 so Pub/Sub retries the delivery once Redis is back.
        logger.exception("Failed to enqueue Gmail notification")
        raise HTTPException(
            status_code=503,
            detail=f"Gmail webhook enqueue failed: {exc}",
        ) from exc
    finally:
        if redis is not None:
            await redis.aclose()
