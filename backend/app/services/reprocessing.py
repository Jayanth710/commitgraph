from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inline_processor import process_normalized_item_inline


async def reprocess_normalized_item_for_user(
    db: AsyncSession,
    *,
    user_id: str,
    normalized_item_id: str,
) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            SELECT n.id as normalized_item_id, n.account_id
            FROM normalized_items n
            JOIN accounts a ON a.id = n.account_id
            WHERE n.id = :nid AND a.user_id = :uid
            LIMIT 1
            """
        ),
        {"nid": normalized_item_id, "uid": user_id},
    )
    row = result.mappings().first()
    if not row:
        return {"status": "not_found"}

    return await process_normalized_item_inline(
        normalized_item_id=str(row["normalized_item_id"]),
        account_id=str(row["account_id"]),
    )


async def reprocess_account_items_for_user(
    db: AsyncSession,
    *,
    user_id: str,
    account_id: str,
    limit: int = 25,
) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            SELECT n.id as normalized_item_id, n.account_id
            FROM normalized_items n
            JOIN accounts a ON a.id = n.account_id
            WHERE n.account_id = :aid
              AND a.user_id = :uid
            ORDER BY COALESCE(n.received_at, n.sent_at, n.normalized_at) DESC
            LIMIT :limit
            """
        ),
        {"aid": account_id, "uid": user_id, "limit": limit},
    )
    rows = result.mappings().all()

    processed = []
    for row in rows:
        processed.append(
            await process_normalized_item_inline(
                normalized_item_id=str(row["normalized_item_id"]),
                account_id=str(row["account_id"]),
            )
        )

    return {
        "status": "processed",
        "count": len(processed),
        "results": processed,
    }