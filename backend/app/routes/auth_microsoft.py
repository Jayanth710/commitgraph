"""
Microsoft OAuth routes for connecting Outlook accounts.

Same pattern as Google OAuth:
    /auth/microsoft/start    → redirect to Microsoft consent page
    /auth/microsoft/callback → exchange code for tokens, store account
"""

import secrets

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.db.session import AsyncSessionLocal
from app.services.microsoft_oauth import (
    build_microsoft_auth_url,
    exchange_microsoft_code,
    fetch_microsoft_profile,
    upsert_outlook_account,
)

router = APIRouter(prefix="/auth/microsoft", tags=["microsoft-auth"])


@router.get("/start")
async def microsoft_auth_start():
    state = secrets.token_urlsafe(32)
    auth_url = build_microsoft_auth_url(state)

    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key="ms_oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=600,
    )
    return response


@router.get("/callback")
async def microsoft_auth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Microsoft OAuth error: {error} — {error_description}",
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    cookie_state = request.cookies.get("ms_oauth_state")
    if not state or not cookie_state or state != cookie_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    token_data = await exchange_microsoft_code(code)

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token returned by Microsoft")

    profile = await fetch_microsoft_profile(access_token)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            account = await upsert_outlook_account(
                session,
                tokens=token_data,
                profile=profile,
            )

    response = JSONResponse({
        "message": "Microsoft account connected successfully",
        "account_id": str(account["id"]),
        "email_address": account["email_address"],
        "provider": "outlook",
    })
    response.delete_cookie("ms_oauth_state")
    return response