from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import encrypt_token

settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"


def build_google_auth_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": settings.google_oauth_scope,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()


async def fetch_gmail_profile(access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(GMAIL_PROFILE_URL, headers=headers)
        response.raise_for_status()
        return response.json()


def _compute_token_expires_at(tokens: dict[str, Any]) -> datetime | None:
    expires_in = tokens.get("expires_in")
    if expires_in is None:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))


async def upsert_gmail_account(
    db: AsyncSession,
    *,
    tokens: dict[str, Any],
    gmail_profile: dict[str, Any],
) -> dict[str, Any]:
    email_address = gmail_profile["emailAddress"]
    display_name = gmail_profile.get("emailAddress")
    history_id = str(gmail_profile["historyId"]) if gmail_profile.get("historyId") else None

    access_token_encrypted = encrypt_token(tokens["access_token"])

    refresh_token_plain = tokens.get("refresh_token")
    refresh_token_encrypted = (
        encrypt_token(refresh_token_plain) if refresh_token_plain else None
    )

    token_expires_at = _compute_token_expires_at(tokens)

    existing_result = await db.execute(
        text(
            """
            SELECT id, refresh_token_encrypted
            FROM accounts
            WHERE provider = 'gmail'
              AND email_address = :email_address
            LIMIT 1
            """
        ),
        {"email_address": email_address},
    )
    existing = existing_result.mappings().first()

    if existing:
        effective_refresh_token_encrypted = (
            refresh_token_encrypted
            if refresh_token_encrypted is not None
            else existing["refresh_token_encrypted"]
        )

        update_result = await db.execute(
            text(
                """
                UPDATE accounts
                SET display_name = :display_name,
                    access_token_encrypted = :access_token_encrypted,
                    refresh_token_encrypted = :refresh_token_encrypted,
                    token_expires_at = :token_expires_at,
                    sync_status = 'active',
                    history_id = COALESCE(:history_id, history_id)
                WHERE id = :account_id
                RETURNING id, provider, email_address, history_id, watch_expiry
                """
            ),
            {
                "account_id": existing["id"],
                "display_name": display_name,
                "access_token_encrypted": access_token_encrypted,
                "refresh_token_encrypted": effective_refresh_token_encrypted,
                "token_expires_at": token_expires_at,
                "history_id": history_id,
            },
        )
        return dict(update_result.mappings().one())

    insert_result = await db.execute(
        text(
            """
            INSERT INTO accounts (
                provider,
                email_address,
                display_name,
                access_token_encrypted,
                refresh_token_encrypted,
                token_expires_at,
                sync_status,
                history_id
            )
            VALUES (
                'gmail',
                :email_address,
                :display_name,
                :access_token_encrypted,
                :refresh_token_encrypted,
                :token_expires_at,
                'active',
                :history_id
            )
            RETURNING id, provider, email_address, history_id, watch_expiry
            """
        ),
        {
            "email_address": email_address,
            "display_name": display_name,
            "access_token_encrypted": access_token_encrypted,
            "refresh_token_encrypted": refresh_token_encrypted,
            "token_expires_at": token_expires_at,
            "history_id": history_id,
        },
    )
    return dict(insert_result.mappings().one())