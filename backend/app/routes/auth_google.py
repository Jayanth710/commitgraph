import secrets

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.db.session import AsyncSessionLocal
from app.services.google_oauth import (
    build_google_auth_url,
    exchange_code_for_tokens,
    fetch_gmail_profile,
    upsert_gmail_account,
)

router = APIRouter(prefix="/auth/google", tags=["google-auth"])


@router.get("/start")
async def google_auth_start():
    state = secrets.token_urlsafe(32)
    auth_url = build_google_auth_url(state)

    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key="google_oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=600,
    )
    return response


@router.get("/callback")
async def google_auth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    cookie_state = request.cookies.get("google_oauth_state")
    if not state or not cookie_state or state != cookie_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    token_data = await exchange_code_for_tokens(code)

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token returned by Google")

    profile = await fetch_gmail_profile(access_token)
    email_address = profile.get("emailAddress")
    if not email_address:
        raise HTTPException(status_code=400, detail="Could not determine Gmail address")

    async with AsyncSessionLocal() as session:
        async with session.begin():
            account = await upsert_gmail_account(
                session,
                tokens=token_data,
                gmail_profile=profile,
            )

    response = JSONResponse(
        {
            "message": "Google account connected successfully",
            "account_id": str(account["id"]),
            "email_address": account["email_address"],
            "history_id": account["history_id"],
            "watch_expiry": account["watch_expiry"],
            "scope": token_data.get("scope"),
            "token_type": token_data.get("token_type"),
        }
    )
    response.delete_cookie("google_oauth_state")
    return response