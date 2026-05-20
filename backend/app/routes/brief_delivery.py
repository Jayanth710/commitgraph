from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends
from fastapi import HTTPException

from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user
from app.services.brief_delivery import (
    get_or_create_delivery_preference,
    list_delivery_runs,
    send_brief_delivery_now,
    update_delivery_preference,
)

router = APIRouter(prefix="/api", tags=["brief-delivery"])
logger = logging.getLogger(__name__)


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


@router.post("/brief-delivery/send-now")
async def post_send_now(body: dict, user: dict = Depends(get_current_user)):
    user_id = str(user["id"])
    brief_type = body.get("brief_type")
    if brief_type not in {"morning", "night"}:
        raise HTTPException(status_code=400, detail="brief_type must be 'morning' or 'night'")

    brief_date_value = body.get("brief_date")
    try:
        brief_date = date.fromisoformat(brief_date_value) if brief_date_value else date.today()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="brief_date must be YYYY-MM-DD") from exc

    force = bool(body.get("force", True))

    async with AsyncSessionLocal() as db:
        async with db.begin():
            try:
                result = await send_brief_delivery_now(
                    db,
                    user_id=user_id,
                    user_email=user.get("email"),
                    brief_type=brief_type,
                    brief_date=brief_date,
                    force=force,
                )
            except ValueError as exc:
                logger.warning(
                    "Manual brief send rejected for user=%s brief_type=%s: %s",
                    user_id,
                    brief_type,
                    exc,
                )
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                logger.error(
                    "Manual brief send failed for user=%s brief_type=%s: %s",
                    user_id,
                    brief_type,
                    exc,
                )
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result
