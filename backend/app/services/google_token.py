"""
Google OAuth access-token helper.

Returns a usable access token for a connected Google account, refreshing it
via the stored refresh token when possible and persisting the new token.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.core.security import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)


async def get_fresh_google_access_token(account_id: str) -> str | None:
    from app.db.session import AsyncSessionLocal

    settings = get_settings()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT access_token_encrypted, refresh_token_encrypted
                FROM accounts
                WHERE id = :aid
                """
            ),
            {"aid": account_id},
        )
        account = result.mappings().first()

    if not account or not account["access_token_encrypted"]:
        return None

    try:
        access_token = decrypt_token(account["access_token_encrypted"])
    except Exception as exc:
        # Token was encrypted with a different ENCRYPTION_KEY (stale account) —
        # skip it rather than failing the whole sync. Reconnect fixes it.
        logger.warning("Cannot decrypt token for account %s: %s", account_id, exc)
        return None

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
                access_token = resp.json()["access_token"]
                async with AsyncSessionLocal() as db:
                    async with db.begin():
                        await db.execute(
                            text(
                                "UPDATE accounts SET access_token_encrypted = :t WHERE id = :aid"
                            ),
                            {"t": encrypt_token(access_token), "aid": account_id},
                        )
        except Exception as exc:
            logger.warning("Google token refresh failed for account %s: %s", account_id, exc)

    return access_token
