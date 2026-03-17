from __future__ import annotations

import base64
import json
import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.services.redis_streams import get_redis_client, publish_ingest_raw_event

router = APIRouter(prefix="/api/webhooks", tags=["gmail-webhooks"])
logger = logging.getLogger(__name__)


@router.post("/gmail", status_code=status.HTTP_200_OK)
async def gmail_webhook(request: Request) -> dict:
    body = await request.json()

    logger.info("GMAIL WEBHOOK HIT")
    logger.info("Raw Pub/Sub body: %s", body)

    message = body.get("message") or {}
    encoded_data = message.get("data")

    if not encoded_data:
        return {
            "status": "ignored",
            "reason": "missing_message_data",
        }

    try:
        decoded_payload = json.loads(base64.b64decode(encoded_data).decode("utf-8"))
    except Exception as exc:
        logger.exception("Invalid Pub/Sub payload")
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub payload") from exc

    logger.info("Decoded Gmail notification: %s", decoded_payload)

    email_address = decoded_payload.get("emailAddress")
    history_id = decoded_payload.get("historyId")

    if not email_address or not history_id:
        raise HTTPException(
            status_code=400,
            detail="Missing emailAddress or historyId in Pub/Sub payload",
        )

    redis = get_redis_client()
    try:
        event_id = await publish_ingest_raw_event(
            redis,
            email_address=email_address,
            history_id=str(history_id),
        )
        logger.info(
            "Queued Gmail webhook email=%s history_id=%s stream_id=%s",
            email_address,
            history_id,
            event_id,
        )
        return {
            "status": "queued",
            "stream": "ingest:raw",
            "event_id": event_id,
        }
    except Exception as exc:
        logger.exception("Failed to enqueue Gmail webhook event")
        raise HTTPException(
            status_code=500,
            detail="Failed to enqueue Gmail webhook event",
        ) from exc
    finally:
        await redis.aclose()