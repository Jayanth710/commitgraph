from __future__ import annotations

import logging

import httpx
from sqlalchemy import text

from app.core.security import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

GCAL_API_BASE = "https://www.googleapis.com/calendar/v3"


async def delete_commitment_event(
    *,
    account_id: str,
    event_id: str,
) -> bool:
    from app.db.session import AsyncSessionLocal
    from app.core.config import get_settings

    settings = get_settings()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT access_token_encrypted, refresh_token_encrypted
                FROM accounts
                WHERE id = :aid AND provider = 'gmail'
                """
            ),
            {"aid": account_id},
        )
        account = result.mappings().first()

    if not account:
        logger.warning("No Gmail account found for id=%s", account_id)
        return False

    access_token = decrypt_token(account["access_token_encrypted"])

    if account["refresh_token_encrypted"]:
        refresh_token = decrypt_token(account["refresh_token_encrypted"])
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                if resp.is_success:
                    new_tokens = resp.json()
                    access_token = new_tokens["access_token"]

                    async with AsyncSessionLocal() as db:
                        async with db.begin():
                            await db.execute(
                                text(
                                    """
                                    UPDATE accounts
                                    SET access_token_encrypted = :token
                                    WHERE id = :aid
                                    """
                                ),
                                {
                                    "token": encrypt_token(access_token),
                                    "aid": account_id,
                                },
                            )
        except Exception as exc:
            logger.warning("Token refresh failed before delete: %s", exc)

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{GCAL_API_BASE}/calendars/primary/events/{event_id}",
                headers=headers,
            )

        if response.status_code in (204, 404):
            return True

        logger.error(
            "Failed to delete calendar event: %s %s",
            response.status_code,
            response.text,
        )
        return False

    except Exception as exc:
        logger.exception("Error deleting calendar event: %s", exc)
        return False
