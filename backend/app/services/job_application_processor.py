from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.agents.job_extraction import extract_job_applications
from app.services.job_application_store import upsert_job_application

logger = logging.getLogger(__name__)


async def process_job_application_item(
    *,
    normalized_item_id: str,
    account_id: str,
) -> dict[str, Any]:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT
                    n.id,
                    n.account_id,
                    n.subject,
                    n.body_text,
                    n.sender_email,
                    n.sender_name,
                    n.sent_at,
                    n.thread_id,
                    a.email_address as account_email,
                    a.user_id
                FROM normalized_items n
                JOIN accounts a ON a.id = n.account_id
                WHERE n.id = :nid
                LIMIT 1
                """
            ),
            {"nid": normalized_item_id},
        )
        row = result.mappings().first()
        if not row:
            return {"status": "skipped", "reason": "not_found"}

        if not row.get("subject") and not row.get("body_text"):
            return {"status": "skipped", "reason": "no_content"}

    extraction = await extract_job_applications(
        account_owner_email=row["account_email"] or "",
        sender_email=row.get("sender_email") or "",
        sender_name=row.get("sender_name"),
        subject=row.get("subject"),
        body_text=row.get("body_text"),
        sent_date=row["sent_at"].strftime("%Y-%m-%d") if row.get("sent_at") else None,
    )

    extracted = extraction.job_applications
    if not extracted:
        return {"status": "processed", "applications_detected": 0}

    stored_ids: list[str] = []
    async with AsyncSessionLocal() as db:
        async with db.begin():
            for item in extracted:
                stored = await upsert_job_application(
                    db,
                    user_id=str(row["user_id"]),
                    account_id=account_id,
                    normalized_item_id=normalized_item_id,
                    thread_id=row.get("thread_id"),
                    company_name=item.company_name,
                    role_title=item.role_title,
                    status=item.status,
                    summary=item.summary,
                    raw_text=item.raw_text,
                    date_applied=item.date_applied.isoformat() if item.date_applied else None,
                    event_date=item.event_date.isoformat() if item.event_date else None,
                    confidence_score=item.confidence_score,
                )
                if stored.get("status") == "skipped_deleted":
                    logger.info(
                        "Skipped recreating deleted job application for normalized_item=%s company=%s role=%s",
                        normalized_item_id,
                        item.company_name,
                        item.role_title,
                    )
                    continue
                stored_ids.append(str(stored["id"]))

    logger.info(
        "Processed %d job application updates for normalized_item=%s",
        len(stored_ids),
        normalized_item_id,
    )

    return {"status": "processed", "applications_detected": len(stored_ids), "job_application_ids": stored_ids}
