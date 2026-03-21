from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user
from app.services.reprocessing import (
    reprocess_account_items_for_user,
    reprocess_normalized_item_for_user,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reprocess/normalized-item")
async def reprocess_normalized_item(
    body: dict,
    user: dict = Depends(get_current_user),
):
    normalized_item_id = body.get("normalized_item_id")
    if not normalized_item_id:
        raise HTTPException(status_code=400, detail="normalized_item_id is required")

    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        result = await reprocess_normalized_item_for_user(
            db,
            user_id=user_id,
            normalized_item_id=normalized_item_id,
        )

    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Normalized item not found")

    return result


@router.post("/reprocess/account")
async def reprocess_account(
    body: dict,
    user: dict = Depends(get_current_user),
):
    account_id = body.get("account_id")
    limit = int(body.get("limit", 25))

    if not account_id:
        raise HTTPException(status_code=400, detail="account_id is required")

    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")

    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        return await reprocess_account_items_for_user(
            db,
            user_id=user_id,
            account_id=account_id,
            limit=limit,
        )