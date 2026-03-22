from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> str:
    phone = phone.strip()
    if not phone.startswith("+"):
        raise RuntimeError("Phone number must be in E.164 format, e.g. +15551234567")
    return phone


async def send_sms_message(*, to: str, body: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.twilio_from_number:
        raise RuntimeError("Twilio settings are not configured")

    to = _normalize_phone(to)
    from_number = _normalize_phone(settings.twilio_from_number)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            data={
                "To": to,
                "From": from_number,
                "Body": body[:1500],
            },
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        )

    if response.is_error:
        logger.error("Twilio send failed: %s", response.text)
        raise RuntimeError("Failed to send SMS")

    payload = response.json()
    return {"message_sid": payload.get("sid"), "status": payload.get("status")}
