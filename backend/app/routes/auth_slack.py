"""
Slack connect flow — links a Slack workspace as a *source* under the logged-in
user (not a login method). Mirrors the Gmail connect flow in auth_google.py:
the logged-in user_id is carried through the OAuth `state`, and the account is
linked to that user after the workspace is connected.

Redirect URI is env-driven (settings.slack_redirect_uri), so prod (Cloud Run)
and local use different URLs — register both in the Slack app.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from starlette.background import BackgroundTask

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.slack_api import join_all_public_channels
from app.services.slack_oauth import (
    build_slack_auth_url,
    exchange_slack_code,
    upsert_slack_account,
)

router = APIRouter(prefix="/auth/slack", tags=["slack-auth"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("/start")
async def slack_auth_start(request: Request):
    user_id = request.query_params.get("user_id", "")
    state_data = json.dumps({"token": secrets.token_urlsafe(32), "user_id": user_id})
    state = base64.urlsafe_b64encode(state_data.encode()).decode()
    return RedirectResponse(url=build_slack_auth_url(state), status_code=302)


@router.get("/callback")
async def slack_auth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    settings_frontend = settings.frontend_url

    if error:
        return RedirectResponse(url=f"{settings_frontend}/settings?error={error}", status_code=302)
    if not code:
        return RedirectResponse(url=f"{settings_frontend}/settings?error=missing_code", status_code=302)
    if not state:
        return RedirectResponse(url=f"{settings_frontend}/settings?error=missing_state", status_code=302)

    try:
        state_data = json.loads(base64.urlsafe_b64decode(state).decode())
        user_id = state_data.get("user_id", "")
    except Exception:
        return RedirectResponse(url=f"{settings_frontend}/settings?error=invalid_state", status_code=302)

    try:
        token_data = await exchange_slack_code(code)
    except Exception as exc:
        logger.warning("Slack OAuth exchange failed: %s", exc)
        return RedirectResponse(url=f"{settings_frontend}/settings?error=slack_oauth_failed", status_code=302)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            account = await upsert_slack_account(session, token_data=token_data)
            if user_id:
                await session.execute(
                    text("UPDATE accounts SET user_id = :uid WHERE id = :id AND user_id IS NULL"),
                    {"uid": user_id, "id": account["id"]},
                )

    response = RedirectResponse(
        url=f"{settings_frontend}/settings?connected=slack",
        status_code=302,
    )
    # Auto-join all public channels in the background so the redirect stays fast.
    bot_token = token_data.get("access_token")
    if bot_token:
        response.background = BackgroundTask(join_all_public_channels, bot_token)
    return response
