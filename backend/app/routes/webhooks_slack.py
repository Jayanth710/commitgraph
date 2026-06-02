"""
Slack Events API receiver.

Slack requires a 200 within ~3 seconds or it retries, so this endpoint does the
minimum: verify the request signature, then enqueue message events to ingest:raw
for the workers to process. (Same queue-primary model as Gmail/Outlook.)

Two request shapes:
  1. url_verification — sent once when you set the Request URL; echo the challenge.
  2. event_callback   — real events; we enqueue user message events.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.background import BackgroundTask

from app.core.config import get_settings
from app.core.security import decrypt_token
from app.db.session import AsyncSessionLocal
from app.services.redis_streams import get_redis_client
from app.services.slack_api import join_channel
from app.services.slack_auth import verify_slack_signature

router = APIRouter(prefix="/api/webhooks", tags=["slack-webhooks"])
settings = get_settings()
logger = logging.getLogger(__name__)


async def _join_new_channel(team_id: str, channel_id: str) -> None:
    """Look up the workspace's bot token and join a newly created channel."""
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                text(
                    "SELECT access_token_encrypted FROM accounts "
                    "WHERE provider = 'slack' AND history_id = :team_id LIMIT 1"
                ),
                {"team_id": team_id},
            )
        ).first()
    if not row or not row[0]:
        logger.warning("channel_created: no Slack account for team=%s", team_id)
        return
    ok = await join_channel(decrypt_token(row[0]), channel_id)
    logger.info("Auto-joined new channel %s (team=%s): %s", channel_id, team_id, ok)


@router.post("/slack", status_code=status.HTTP_200_OK)
async def slack_webhook(request: Request):
    raw = await request.body()
    body_str = raw.decode("utf-8")

    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError:
        return {"status": "ignored", "reason": "bad_json"}

    # URL-verification handshake: echo the challenge BEFORE checking the
    # signature. It only reflects a value Slack just sent (nothing to forge), and
    # handling it first keeps Event Subscriptions setup from failing on an
    # imperfect signing secret.
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # Verify the signature on real event deliveries.
    if settings.slack_signing_secret:
        if not verify_slack_signature(
            signing_secret=settings.slack_signing_secret,
            timestamp=request.headers.get("X-Slack-Request-Timestamp"),
            body=body_str,
            signature=request.headers.get("X-Slack-Signature"),
        ):
            logger.warning("Rejected Slack request: invalid signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid slack signature",
            )
    else:
        logger.warning(
            "Slack webhook signature is NOT enforced; set SLACK_SIGNING_SECRET "
            "for production"
        )

    if payload.get("type") != "event_callback":
        return {"status": "ignored", "reason": "not_event_callback"}

    event = payload.get("event", {})

    # Auto-join newly created public channels (so we see their messages).
    if event.get("type") == "channel_created":
        channel_id = (event.get("channel") or {}).get("id")
        if not channel_id:
            return {"status": "ignored", "reason": "no_channel_id"}
        return JSONResponse(
            {"status": "joining_channel"},
            background=BackgroundTask(
                _join_new_channel, payload.get("team_id", ""), channel_id
            ),
        )

    # Only human-authored messages: skip bot messages and edits/joins/etc.
    if (
        event.get("type") != "message"
        or event.get("bot_id")
        or event.get("subtype") is not None
    ):
        return {"status": "ignored", "reason": "not_user_message"}

    redis = None
    try:
        redis = get_redis_client()
        await redis.xadd(
            settings.stream_ingest_raw,
            {
                "provider": "slack",
                "team_id": payload.get("team_id", ""),
                "channel": event.get("channel", ""),
                "event_ts": event.get("ts", ""),
                "thread_ts": event.get("thread_ts", "") or "",
                "slack_user": event.get("user", ""),
                "text": event.get("text", "") or "",
                "enqueued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info(
            "Queued Slack message to ingest:raw team=%s channel=%s ts=%s",
            payload.get("team_id", ""),
            event.get("channel", ""),
            event.get("ts", ""),
        )
    except Exception:
        # Ack 200 anyway so Slack doesn't hammer retries; the event is lost
        # rather than reprocessed. (Slack delivers at-least-once on non-200.)
        logger.exception("Failed to enqueue Slack event")
    finally:
        if redis is not None:
            await redis.aclose()

    return {"status": "queued"}
