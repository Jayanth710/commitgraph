from fastapi import APIRouter

from app.db.session import AsyncSessionLocal
from app.services.gmail_normalize import backfill_gmail_normalized_items

router = APIRouter(prefix="/gmail/normalize", tags=["gmail-normalize"])


@router.post("/backfill")
async def gmail_normalize_backfill(limit: int = 100):
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await backfill_gmail_normalized_items(
                session,
                limit=limit,
            )

    return {
        "message": "Gmail normalization backfill complete",
        **result,
    }