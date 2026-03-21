"""
Microsoft OAuth service for Outlook integration.

Uses Microsoft Identity Platform (v2.0 endpoints).
Works with personal Microsoft accounts, work/school (Entra ID),
and college/education accounts.

The tenant_id='common' means the app accepts all account types.
If your college blocks 'common', try 'organizations' or your
specific tenant ID.
"""

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

MS_AUTH_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
MS_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
MS_GRAPH_ME_URL = "https://graph.microsoft.com/v1.0/me"

OUTLOOK_SCOPES = "offline_access Mail.Read User.Read"


def build_microsoft_auth_url(state: str) -> str:
    """Build the Microsoft OAuth consent URL."""
    tenant = settings.ms_tenant_id or "common"
    params = {
        "client_id": settings.ms_client_id,
        "response_type": "code",
        "redirect_uri": settings.ms_redirect_uri,
        "response_mode": "query",
        "scope": OUTLOOK_SCOPES,
        "state": state,
        "prompt": "consent",
    }
    base = MS_AUTH_URL.format(tenant=tenant)
    return f"{base}?{urlencode(params)}"


async def exchange_microsoft_code(code: str) -> dict[str, Any]:
    """Exchange an authorization code for tokens."""
    tenant = settings.ms_tenant_id or "common"
    token_url = MS_TOKEN_URL.format(tenant=tenant)

    data = {
        "client_id": settings.ms_client_id,
        "client_secret": settings.ms_client_secret,
        "code": code,
        "redirect_uri": settings.ms_redirect_uri,
        "grant_type": "authorization_code",
        "scope": OUTLOOK_SCOPES,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(token_url, data=data)
        response.raise_for_status()
        return response.json()


async def fetch_microsoft_profile(access_token: str) -> dict[str, Any]:
    """Get the user's profile from Microsoft Graph."""
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(MS_GRAPH_ME_URL, headers=headers)
        response.raise_for_status()
        return response.json()


async def upsert_outlook_account(
    db: AsyncSession,
    *,
    tokens: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Create or update an Outlook account in the database."""
    # Microsoft Graph returns 'mail' or 'userPrincipalName' for email.
    email_address = (
        profile.get("mail")
        or profile.get("userPrincipalName", "")
    ).strip().lower()

    display_name = profile.get("displayName") or email_address

    access_token_encrypted = encrypt_token(tokens["access_token"])
    refresh_token_encrypted = (
        encrypt_token(tokens["refresh_token"]) if tokens.get("refresh_token") else None
    )

    expires_in = tokens.get("expires_in")
    token_expires_at = None
    if expires_in:
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    # Check if this Outlook account already exists.
    existing = await db.execute(
        text(
            """
            SELECT id, refresh_token_encrypted
            FROM accounts
            WHERE provider = 'outlook' AND email_address = :email
            LIMIT 1
            """
        ),
        {"email": email_address},
    )
    row = existing.mappings().first()

    if row:
        effective_refresh = (
            refresh_token_encrypted
            if refresh_token_encrypted is not None
            else row["refresh_token_encrypted"]
        )
        update_result = await db.execute(
            text(
                """
                UPDATE accounts
                SET display_name = :display_name,
                    access_token_encrypted = :access_token,
                    refresh_token_encrypted = :refresh_token,
                    token_expires_at = :token_expires_at,
                    sync_status = 'active'
                WHERE id = :account_id
                RETURNING id, provider, email_address
                """
            ),
            {
                "account_id": row["id"],
                "display_name": display_name,
                "access_token": access_token_encrypted,
                "refresh_token": effective_refresh,
                "token_expires_at": token_expires_at,
            },
        )
        return dict(update_result.mappings().one())

    insert_result = await db.execute(
        text(
            """
            INSERT INTO accounts (
                provider, email_address, display_name,
                access_token_encrypted, refresh_token_encrypted,
                token_expires_at, sync_status
            )
            VALUES (
                'outlook', :email, :display_name,
                :access_token, :refresh_token,
                :token_expires_at, 'active'
            )
            RETURNING id, provider, email_address
            """
        ),
        {
            "email": email_address,
            "display_name": display_name,
            "access_token": access_token_encrypted,
            "refresh_token": refresh_token_encrypted,
            "token_expires_at": token_expires_at,
        },
    )
    return dict(insert_result.mappings().one())