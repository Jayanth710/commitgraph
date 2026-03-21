import secrets
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.services.google_oauth import (
    build_google_auth_url,
    exchange_code_for_tokens,
    fetch_gmail_profile,
    upsert_gmail_account,
)

from app.core.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/google", tags=["google-auth"])


@router.get("/start")
async def google_auth_start(request: Request):
    import json, base64

    state_token = secrets.token_urlsafe(32)
    
    # Get user_id from query param
    user_id = request.query_params.get("user_id", "")
    
    # Encode both into the state parameter
    state_data = json.dumps({"token": state_token, "user_id": user_id})
    state = base64.urlsafe_b64encode(state_data.encode()).decode()

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": settings.google_oauth_scope,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback")
async def google_auth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    import json, base64

    if error:
        return RedirectResponse(url=f"{settings.frontend_url}/settings?error={error}", status_code=302)

    if not code:
        return RedirectResponse(url=f"{settings.frontend_url}/settings?error=missing_code", status_code=302)

    if not state:
        return RedirectResponse(url=f"{settings.frontend_url}/settings?error=missing_state", status_code=302)

    # Decode state
    try:
        state_data = json.loads(base64.urlsafe_b64decode(state).decode())
        user_id = state_data.get("user_id", "")
    except Exception:
        return RedirectResponse(url=f"{settings.frontend_url}/settings?error=invalid_state", status_code=302)

    token_data = await exchange_code_for_tokens(code)

    access_token = token_data.get("access_token")
    if not access_token:
        return RedirectResponse(url=f"{settings.frontend_url}/settings?error=no_token", status_code=302)

    profile = await fetch_gmail_profile(access_token)
    email_address = profile.get("emailAddress")
    if not email_address:
        return RedirectResponse(url=f"{settings.frontend_url}/settings?error=no_email", status_code=302)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            account = await upsert_gmail_account(
                session,
                tokens=token_data,
                gmail_profile=profile,
            )

    # Link account to user
    if user_id:
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await session.execute(
                        text("UPDATE accounts SET user_id = :uid WHERE email_address = :email AND user_id IS NULL"),
                        {"uid": user_id, "email": account["email_address"]},
                    )
        except Exception as e:
            logger.error("Failed to link account to user: %s", e)

    response = RedirectResponse(
        url=f"{settings.frontend_url}/settings?connected={account['email_address']}",
        status_code=302,
    )
    return response