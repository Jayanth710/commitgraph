"""
Authentication service.

Handles:
- Password hashing with bcrypt
- JWT token creation and verification
- User creation (email+password and Google OAuth)
- User lookup
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------
def create_access_token(user_id: str, email: str) -> str:
    """Create a JWT token with user_id and email in the payload."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and verify a JWT token. Returns payload or None if invalid."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------
async def create_user_email(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    name: str | None = None,
) -> dict[str, Any]:
    """Create a new user with email + password."""
    hashed = hash_password(password)

    result = await db.execute(
        text(
            """
            INSERT INTO users (email, name, password_hash, auth_provider)
            VALUES (:email, :name, :password_hash, 'email')
            RETURNING id, email, name, auth_provider, avatar_url, created_at
            """
        ),
        {"email": email.strip().lower(), "name": name, "password_hash": hashed},
    )
    return dict(result.mappings().one())


async def create_or_get_google_user(
    db: AsyncSession,
    *,
    email: str,
    name: str | None = None,
    avatar_url: str | None = None,
) -> dict[str, Any]:
    """Find or create a user from Google OAuth login."""
    email = email.strip().lower()

    # Check if user exists.
    result = await db.execute(
        text("SELECT id, email, name, auth_provider, avatar_url, created_at FROM users WHERE email = :email"),
        {"email": email},
    )
    existing = result.mappings().first()

    if existing:
        # Update last login and name/avatar if available.
        await db.execute(
            text(
                """
                UPDATE users
                SET last_login_at = now(),
                    name = COALESCE(:name, name),
                    avatar_url = COALESCE(:avatar_url, avatar_url)
                WHERE email = :email
                """
            ),
            {"email": email, "name": name, "avatar_url": avatar_url},
        )
        return dict(existing)

    # Create new Google user (no password).
    result = await db.execute(
        text(
            """
            INSERT INTO users (email, name, auth_provider, avatar_url, last_login_at)
            VALUES (:email, :name, 'google', :avatar_url, now())
            RETURNING id, email, name, auth_provider, avatar_url, created_at
            """
        ),
        {"email": email, "name": name, "avatar_url": avatar_url},
    )
    return dict(result.mappings().one())


async def get_user_by_email(db: AsyncSession, email: str) -> dict[str, Any] | None:
    """Look up a user by email."""
    result = await db.execute(
        text("SELECT id, email, name, password_hash, auth_provider, avatar_url, created_at FROM users WHERE email = :email"),
        {"email": email.strip().lower()},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_user_by_id(db: AsyncSession, user_id: str) -> dict[str, Any] | None:
    """Look up a user by ID."""
    result = await db.execute(
        text("SELECT id, email, name, auth_provider, avatar_url, created_at FROM users WHERE id = :uid"),
        {"uid": user_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None