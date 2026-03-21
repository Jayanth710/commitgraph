"""
User authentication routes.

POST /auth/signup          - Create account with email + password
POST /auth/login           - Login with email + password
POST /auth/google-login    - Login/signup with Google OAuth token
GET  /auth/me              - Get current user profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user
from app.services.auth import (
    create_access_token,
    create_or_get_google_user,
    create_user_email,
    get_user_by_email,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["user-auth"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class SignupRequest(BaseModel):
    firstname: str | None = None
    lastname: str | None = None
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    email: str
    name: str | None = None
    avatar_url: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/signup")
async def signup(body: SignupRequest):
    """Create a new account with email + password."""
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # Check if email already taken.
            existing = await get_user_by_email(db, body.email)
            if existing:
                raise HTTPException(status_code=409, detail="Email already registered")

            full_name = " ".join(filter(None, [body.firstname, body.lastname])) or None
            user = await create_user_email(
                db,
                email=body.email,
                password=body.password,
                name=full_name,
            )

    token = create_access_token(str(user["id"]), user["email"])

    return {
        "token": token,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "name": user["name"],
            "auth_provider": user["auth_provider"],
        },
    }


@router.post("/login")
async def login(body: LoginRequest):
    """Login with email + password."""
    async with AsyncSessionLocal() as db:
        user = await get_user_by_email(db, body.email)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.get("password_hash"):
        raise HTTPException(
            status_code=401,
            detail="This account uses Google login. Please sign in with Google.",
        )

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last login.
    async with AsyncSessionLocal() as db:
        async with db.begin():
            from sqlalchemy import text
            await db.execute(
                text("UPDATE users SET last_login_at = now() WHERE id = :uid"),
                {"uid": user["id"]},
            )

    token = create_access_token(str(user["id"]), user["email"])

    return {
        "token": token,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "name": user["name"],
            "auth_provider": user["auth_provider"],
        },
    }


@router.post("/google-login")
async def google_login(body: GoogleLoginRequest):
    """Login or signup with Google. Called from frontend after Google OAuth."""
    async with AsyncSessionLocal() as db:
        async with db.begin():
            user = await create_or_get_google_user(
                db,
                email=body.email,
                name=body.name,
                avatar_url=body.avatar_url,
            )

    token = create_access_token(str(user["id"]), user["email"])

    return {
        "token": token,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "name": user["name"],
            "auth_provider": user["auth_provider"],
        },
    }


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "auth_provider": user.get("auth_provider"),
        "avatar_url": user.get("avatar_url"),
    }

@router.delete("/me")
async def delete_user(user: dict = Depends(get_current_user)):
    """Permanently delete the user and all their data."""
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # Delete all user's data in order.
            await db.execute(
                text(
                    """
                    DELETE FROM evidence_links
                    WHERE normalized_item_id IN (
                        SELECT ni.id FROM normalized_items ni
                        JOIN accounts a ON a.id = ni.account_id
                        WHERE a.user_id = :uid
                    )
                    """
                ),
                {"uid": user_id},
            )
            await db.execute(
                text(
                    """
                    DELETE FROM review_queue
                    WHERE commitment_id IN (
                        SELECT c.id FROM commitments c
                        JOIN evidence_links e ON e.commitment_id = c.id
                        JOIN normalized_items n ON n.id = e.normalized_item_id
                        JOIN accounts a ON a.id = n.account_id
                        WHERE a.user_id = :uid
                    )
                    """
                ),
                {"uid": user_id},
            )
            await db.execute(
                text("DELETE FROM normalized_items WHERE account_id IN (SELECT id FROM accounts WHERE user_id = :uid)"),
                {"uid": user_id},
            )
            await db.execute(
                text("DELETE FROM source_items WHERE account_id IN (SELECT id FROM accounts WHERE user_id = :uid)"),
                {"uid": user_id},
            )
            await db.execute(text("DELETE FROM accounts WHERE user_id = :uid"), {"uid": user_id})
            await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})

    return {"message": "Account deleted"}