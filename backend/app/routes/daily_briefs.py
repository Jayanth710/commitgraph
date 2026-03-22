from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user
from app.services.daily_briefs import (
    create_daily_brief_run,
    get_daily_brief_run,
    get_latest_daily_brief_run,
    list_daily_brief_runs,
)

router = APIRouter(prefix="/api", tags=["daily-briefs"])


@router.get("/daily-briefs")
async def list_briefs(
    user: dict = Depends(get_current_user),
    brief_type: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    limit: int = Query(default=20, le=50),
):
    user_id = str(user["id"])
    async with AsyncSessionLocal() as db:
        runs = await list_daily_brief_runs(
            db,
            user_id=user_id,
            brief_type=brief_type,
            account_id=account_id,
            limit=limit,
        )
    return {"runs": runs, "total": len(runs)}


@router.get("/daily-briefs/latest")
async def latest_brief(
    user: dict = Depends(get_current_user),
    brief_type: str = Query(..., pattern="^(morning|night)$"),
    account_id: str | None = Query(default=None),
):
    user_id = str(user["id"])
    async with AsyncSessionLocal() as db:
        run = await get_latest_daily_brief_run(
            db,
            user_id=user_id,
            brief_type=brief_type,
            account_id=account_id,
        )
    return {"run": run}


@router.get("/daily-briefs/{brief_run_id}")
async def get_brief(
    brief_run_id: str,
    user: dict = Depends(get_current_user),
):
    user_id = str(user["id"])
    async with AsyncSessionLocal() as db:
        run = await get_daily_brief_run(db, user_id=user_id, brief_run_id=brief_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Daily brief not found")
    return {"run": run}


@router.post("/daily-briefs/generate")
async def generate_brief(
    body: dict,
    user: dict = Depends(get_current_user),
):
    user_id = str(user["id"])
    brief_type = body.get("brief_type")
    if brief_type not in {"morning", "night"}:
        raise HTTPException(status_code=400, detail="brief_type must be 'morning' or 'night'")

    account_id = body.get("account_id")
    brief_date_value = body.get("brief_date")
    brief_date = date.fromisoformat(brief_date_value) if brief_date_value else date.today()

    async with AsyncSessionLocal() as db:
        async with db.begin():
            run = await create_daily_brief_run(
                db,
                user_id=user_id,
                brief_type=brief_type,
                brief_date=brief_date,
                account_id=account_id,
            )

    return {"run": run}
