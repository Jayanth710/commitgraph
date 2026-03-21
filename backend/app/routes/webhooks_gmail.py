"""
Gmail webhook — receives Pub/Sub push, processes email inline.

In production, we process the email directly in the webhook request
instead of queuing to Redis. This avoids needing always-on workers.
Falls back to Redis queue if inline processing fails.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, status

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.gmail_ingest import process_gmail_push_notification
from app.services.redis_streams import get_redis_client

router = APIRouter(prefix="/api/webhooks", tags=["gmail-webhooks"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/gmail", status_code=status.HTTP_200_OK)
async def gmail_webhook(request: Request):
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

    # Try inline processing first (production mode).
    if settings.app_env == "production":
        try:
            redis = get_redis_client()
            async with AsyncSessionLocal() as session:
                result = await process_gmail_push_notification(
                    session,
                    redis,
                    email_address=email_address,
                    latest_history_id=history_id,
                )
            await redis.aclose()
            logger.info("Webhook inline processing complete: %s", result)
            return {"status": "processed", "result": str(result)}

        except Exception:
            logger.exception("Inline processing failed, falling back to queue")
            # Fall through to queue below.

    # Queue to Redis (local dev or fallback).
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
        await redis.aclose()
        logger.info("Queued to Redis: email=%s historyId=%s", email_address, history_id)
        return {"status": "queued"}

    except Exception as exc:
        logger.exception("Failed to queue Gmail notification")
        return {"status": "error", "detail": str(exc)}