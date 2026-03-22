from __future__ import annotations

from fastapi import APIRouter, Depends

from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user
from app.services.brief_delivery import (
    get_or_create_delivery_preference,
    list_delivery_runs,
    update_delivery_preference,
)

router = APIRouter(prefix="/api", tags=["brief-delivery"])


def _serialize_row(row: dict) -> dict:
    data = dict(row)
    for key, value in data.items():
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
    return data


@router.get("/brief-delivery/preferences")
async def get_preferences(user: dict = Depends(get_current_user)):
    user_id = str(user["id"])
    async with AsyncSessionLocal() as db:
        async with db.begin():
            preference = await get_or_create_delivery_preference(db, user_id=user_id)
    return {"preference": _serialize_row(preference)}


@router.put("/brief-delivery/preferences")
async def put_preferences(body: dict, user: dict = Depends(get_current_user)):
    user_id = str(user["id"])
    async with AsyncSessionLocal() as db:
        async with db.begin():
            preference = await update_delivery_preference(db, user_id=user_id, body=body)
    return {"preference": _serialize_row(preference)}


@router.get("/brief-delivery/runs")
async def get_delivery_runs(user: dict = Depends(get_current_user)):
    user_id = str(user["id"])
    async with AsyncSessionLocal() as db:
        runs = await list_delivery_runs(db, user_id=user_id)
    return {"runs": [_serialize_row(run) for run in runs], "total": len(runs)}
