from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import encrypt_token

settings = get_settings()

SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_OAUTH_ACCESS_URL = "https://slack.com/api/oauth.v2.access"


def build_slack_auth_url(state: str) -> str:
    params = {
        "client_id": settings.slack_client_id,
        "scope": settings.slack_scopes,  # bot token scopes (comma-separated)
        "redirect_uri": settings.slack_redirect_uri,
        "state": state,
    }
    return f"{SLACK_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_slack_code(code: str) -> dict[str, Any]:
    """Exchange an OAuth code for a bot token. Raises on Slack-level errors."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            SLACK_OAUTH_ACCESS_URL,
            data={
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
                "code": code,
                "redirect_uri": settings.slack_redirect_uri,
            },
        )
        response.raise_for_status()
        data = response.json()

    if not data.get("ok"):
        raise RuntimeError(f"Slack OAuth exchange failed: {data.get('error', 'unknown')}")
    return data


async def upsert_slack_account(
    db: AsyncSession,
    *,
    token_data: dict[str, Any],
) -> dict[str, Any]:
    """Create/update the Slack workspace account. Keyed by team id, which is
    stored in history_id (a Slack account has no email; display_name holds the
    workspace name). Bot tokens don't expire or refresh."""
    team = token_data.get("team") or {}
    team_id = team.get("id")
    team_name = team.get("name")
    access_token = token_data.get("access_token")  # bot token (xoxb-...)
    # The user who authorized the install — used to detect "self" for direction.
    authed_user_id = (token_data.get("authed_user") or {}).get("id")

    if not team_id or not access_token:
        raise RuntimeError("Slack OAuth response missing team id or access token")

    access_token_encrypted = encrypt_token(access_token)

    existing = (
        await db.execute(
            text(
                """
                SELECT id FROM accounts
                WHERE provider = 'slack' AND history_id = :team_id
                LIMIT 1
                """
            ),
            {"team_id": team_id},
        )
    ).mappings().first()

    if existing:
        result = await db.execute(
            text(
                """
                UPDATE accounts
                SET display_name = :display_name,
                    access_token_encrypted = :access_token_encrypted,
                    provider_user_id = COALESCE(:provider_user_id, provider_user_id),
                    sync_status = 'active'
                WHERE id = :account_id
                RETURNING id, provider, display_name, history_id
                """
            ),
            {
                "account_id": existing["id"],
                "display_name": team_name,
                "access_token_encrypted": access_token_encrypted,
                "provider_user_id": authed_user_id,
            },
        )
        return dict(result.mappings().one())

    result = await db.execute(
        text(
            """
            INSERT INTO accounts (
                provider, email_address, display_name,
                access_token_encrypted, history_id, provider_user_id, sync_status
            )
            VALUES ('slack', NULL, :display_name, :access_token_encrypted,
                    :team_id, :provider_user_id, 'active')
            RETURNING id, provider, display_name, history_id
            """
        ),
        {
            "display_name": team_name,
            "access_token_encrypted": access_token_encrypted,
            "team_id": team_id,
            "provider_user_id": authed_user_id,
        },
    )
    return dict(result.mappings().one())
