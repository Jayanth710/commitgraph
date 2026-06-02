"""
Microsoft Graph API client for Outlook email.

Key differences from Gmail:
    - Body is direct HTML/text (not base64 encoded)
    - Threading uses conversationId (not threadId)
    - Recipients are in toRecipients/ccRecipients arrays
    - Token refresh uses MSAL-style endpoint
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
MS_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


class OutlookApiError(Exception):
    pass


async def _refresh_outlook_token(db: AsyncSession, account: dict[str, Any]) -> None:
    """Refresh an expired Outlook access token."""
    settings = get_settings()
    refresh_token = decrypt_token(account["refresh_token_encrypted"])
    tenant = settings.ms_tenant_id or "common"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            MS_TOKEN_URL.format(tenant=tenant),
            data={
                "client_id": settings.ms_client_id,
                "client_secret": settings.ms_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "offline_access Mail.Read User.Read",
            },
        )

    if response.is_error:
        raise OutlookApiError(
            f"Failed to refresh Outlook token for account={account['id']}: "
            f"{response.status_code} {response.text}"
        )

    payload = response.json()
    new_access = encrypt_token(payload["access_token"])
    new_refresh = encrypt_token(payload.get("refresh_token", refresh_token))

    await db.execute(
        text(
            """
            UPDATE accounts
            SET access_token_encrypted = :access_token,
                refresh_token_encrypted = :refresh_token
            WHERE id = :account_id
            """
        ),
        {
            "account_id": account["id"],
            "access_token": new_access,
            "refresh_token": new_refresh,
        },
    )

    account["access_token_encrypted"] = new_access
    account["refresh_token_encrypted"] = new_refresh


async def graph_request(
    db: AsyncSession,
    account: dict[str, Any],
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the Microsoft Graph API.

    Handles 401 by refreshing the token and retrying once.
    """
    url = f"{GRAPH_API_BASE}{path}"
    access_token = decrypt_token(account["access_token_encrypted"])
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method, url, headers=headers, params=params, json=json_body
        )

        if response.status_code == 401:
            await _refresh_outlook_token(db, account)
            access_token = decrypt_token(account["access_token_encrypted"])
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.request(
                method, url, headers=headers, params=params, json=json_body
            )

    if response.is_error:
        raise OutlookApiError(
            f"Graph API error: {method} {path} → {response.status_code} {response.text}"
        )

    # Graph returns 204 No Content for some PATCH/DELETE calls.
    if not response.content:
        return {}
    return response.json()


async def get_outlook_message(
    db: AsyncSession,
    account: dict[str, Any],
    message_id: str,
) -> dict[str, Any]:
    """Fetch a single Outlook email by ID."""
    return await graph_request(
        db, account, "GET",
        f"/me/messages/{message_id}",
        params={"$select": "id,subject,body,from,toRecipients,ccRecipients,bccRecipients,conversationId,receivedDateTime,sentDateTime,isRead"},
    )


async def list_recent_outlook_messages(
    db: AsyncSession,
    account: dict[str, Any],
    *,
    top: int = 50,
) -> list[dict[str, Any]]:
    """Fetch recent inbox messages for initial sync."""
    data = await graph_request(
        db, account, "GET",
        "/me/mailFolders/inbox/messages",
        params={
            "$top": str(top),
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,body,from,toRecipients,ccRecipients,bccRecipients,conversationId,receivedDateTime,sentDateTime,isRead",
        },
    )
    return data.get("value", [])