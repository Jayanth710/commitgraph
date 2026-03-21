"""
Google Sign-In routes (authentication only, NOT Gmail linking).

This is separate from /auth/google/start which links Gmail accounts.
This flow only asks for 'openid email profile' — just enough to know
who the user is. No email reading permissions.

Flow:
    /auth/google-signin/start    → redirect to Google consent
    /auth/google-signin/callback → exchange code, create/find user, redirect to frontend with JWT
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.auth import create_access_token, create_or_get_google_user

router = APIRouter(prefix="/auth/google-signin", tags=["google-signin"])
settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@router.get("/start")
async def google_signin_start():
    """Redirect to Google consent page for sign-in only."""
    state = secrets.token_urlsafe(32)

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_signin_redirect_uri,
        "response_type": "code",
        "scope": settings.google_signin_scope,
        "access_type": "online",  # No refresh token needed for sign-in
        "prompt": "select_account",  # Let user pick which Google account
        "state": state,
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key="google_signin_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=600,
    )
    return response


@router.get("/callback")
async def google_signin_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    """Handle Google's OAuth callback for sign-in."""
    if error:
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error={error}",
            status_code=302,
        )

    if not code:
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=missing_code",
            status_code=302,
        )

    cookie_state = request.cookies.get("google_signin_state")
    if not state or not cookie_state or state != cookie_state:
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=invalid_state",
            status_code=302,
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_signin_redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if token_response.is_error:
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=token_exchange_failed",
            status_code=302,
        )

    token_data = token_response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=no_access_token",
            status_code=302,
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_response.is_error:
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=userinfo_failed",
            status_code=302,
        )

    userinfo = userinfo_response.json()
    email = userinfo.get("email")
    name = userinfo.get("name")
    avatar_url = userinfo.get("picture")

    if not email:
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=no_email",
            status_code=302,
        )

    async with AsyncSessionLocal() as db:
        async with db.begin():
            user = await create_or_get_google_user(
                db,
                email=email,
                name=name,
                avatar_url=avatar_url,
            )

    jwt_token = create_access_token(str(user["id"]), user["email"])

    response = RedirectResponse(
        url=f"{settings.frontend_url}/auth/callback?token={jwt_token}",
        status_code=302,
    )
    response.delete_cookie("google_signin_state")
    return response