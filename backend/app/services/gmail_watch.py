from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_token
from app.services.gmail_api import GmailApiError, _refresh_access_token

settings = get_settings()


async def start_gmail_watch(db: AsyncSession, account: dict[str, Any]) -> dict:
    topic_name = f"projects/{settings.gcp_project_id}/topics/{settings.gcp_pubsub_topic}"
    access_token = decrypt_token(account["access_token_encrypted"])

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "topicName": topic_name,
        "labelIds": ["INBOX"],
        "labelFilterBehavior": "INCLUDE",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/watch",
            headers=headers,
            json=payload,
        )

        if response.status_code == 401:
            if not account.get("refresh_token_encrypted"):
                raise GmailApiError(
                    f"Gmail watch refresh failed for account={account['id']}: missing refresh token"
                )

            await _refresh_access_token(db, account)
            access_token = decrypt_token(account["access_token_encrypted"])
            headers["Authorization"] = f"Bearer {access_token}"
            response = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/watch",
                headers=headers,
                json=payload,
            )

        if response.is_error:
            raise GmailApiError(
                f"Gmail watch start failed for account={account['id']}: "
                f"{response.status_code} {response.text}"
            )

        return response.json()
