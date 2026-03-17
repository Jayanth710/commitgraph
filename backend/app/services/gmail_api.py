from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_token, encrypt_token

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GmailApiError(Exception):
    pass


class GmailHistoryExpiredError(GmailApiError):
    pass


async def _refresh_access_token(db: AsyncSession, account: dict[str, Any]) -> None:
    refresh_token = decrypt_token(account["refresh_token_encrypted"])

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": get_settings().google_client_id,
                "client_secret": get_settings().google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if response.is_error:
        raise GmailApiError(
            f"Failed to refresh Gmail access token for account={account['id']}: "
            f"{response.status_code} {response.text}"
        )

    payload = response.json()
    new_access_token = payload["access_token"]
    new_refresh_token = payload.get("refresh_token", refresh_token)

    encrypted_access_token = encrypt_token(new_access_token)
    encrypted_refresh_token = encrypt_token(new_refresh_token)

    await db.execute(
        text(
            """
            UPDATE accounts
            SET access_token_encrypted = :access_token_encrypted,
                refresh_token_encrypted = :refresh_token_encrypted
            WHERE id = :account_id
            """
        ),
        {
            "account_id": account["id"],
            "access_token_encrypted": encrypted_access_token,
            "refresh_token_encrypted": encrypted_refresh_token,
        },
    )

    account["access_token_encrypted"] = encrypted_access_token
    account["refresh_token_encrypted"] = encrypted_refresh_token


async def gmail_request(
    db: AsyncSession,
    account: dict[str, Any],
    method: str,
    path: str,
    *,
    params: dict[str, Any] | list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    url = f"{GMAIL_API_BASE}{path}"
    access_token = decrypt_token(account["access_token_encrypted"])
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, url, headers=headers, params=params)

        if response.status_code == 401:
            await _refresh_access_token(db, account)
            access_token = decrypt_token(account["access_token_encrypted"])
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.request(method, url, headers=headers, params=params)

    if response.status_code == 404 and "/users/me/history" in path:
        raise GmailHistoryExpiredError(
            f"startHistoryId is no longer valid for account={account['id']}"
        )

    if response.is_error:
        raise GmailApiError(
            f"Gmail API request failed: {method} {path} -> "
            f"{response.status_code} {response.text}"
        )

    return response.json()


async def list_new_message_ids(
    db: AsyncSession,
    account: dict[str, Any],
    start_history_id: str,
) -> list[str]:
    message_ids: list[str] = []
    seen: set[str] = set()
    page_token: str | None = None

    while True:
        params: list[tuple[str, str]] = [
            ("startHistoryId", start_history_id),
            ("historyTypes", "messageAdded"),
            ("maxResults", "500"),
        ]
        if page_token:
            params.append(("pageToken", page_token))

        payload = await gmail_request(
            db,
            account,
            "GET",
            "/users/me/history",
            params=params,
        )

        for history_record in payload.get("history", []):
            for message_added in history_record.get("messagesAdded", []):
                message = message_added.get("message", {})
                message_id = message.get("id")
                if message_id and message_id not in seen:
                    seen.add(message_id)
                    message_ids.append(message_id)

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return message_ids


async def get_full_message(
    db: AsyncSession,
    account: dict[str, Any],
    message_id: str,
) -> dict[str, Any]:
    return await gmail_request(
        db,
        account,
        "GET",
        f"/users/me/messages/{message_id}",
        params={"format": "FULL"},
    )