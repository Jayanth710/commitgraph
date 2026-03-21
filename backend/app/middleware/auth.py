"""
JWT authentication dependency for FastAPI.

Usage in routes:
    @router.get("/something")
    async def my_route(user: dict = Depends(get_current_user)):
        user_id = user["id"]
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.db.session import AsyncSessionLocal
from app.services.auth import decode_access_token, get_user_by_id


async def get_current_user(request: Request) -> dict:
    """Extract and verify JWT from Authorization header.

    Returns the user dict if valid, raises 401 if not.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ", 1)[1]
    payload = decode_access_token(token)

    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    async with AsyncSessionLocal() as db:
        user = await get_user_by_id(db, payload["sub"])

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user