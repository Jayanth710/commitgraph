"""
Inline email processor for production.

Runs the full pipeline (normalize → extract → store) in a single
function call, without Redis queuing or separate workers.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.pipeline import extraction_graph
from app.core.config import get_settings
# from app.services.gcal_create import create_commitment_event

settings = get_settings()
logger = logging.getLogger(__name__)


async def process_normalized_item_inline(
    *,
    normalized_item_id: str,
    account_id: str,
) -> dict[str, Any]:
    """Run the extraction pipeline on a single normalized item."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT id, subject, body_text, sender_email, sender_name,
                       recipients, sent_at, thread_id, account_id
                FROM normalized_items WHERE id = :nid
                """
            ),
            {"nid": normalized_item_id},
        )
        ni = result.mappings().first()

        if not ni:
            return {"status": "skipped", "reason": "not_found"}

        if not ni.get("body_text"):
            return {"status": "skipped", "reason": "no_body"}

        acct_result = await db.execute(
            text("SELECT email_address FROM accounts WHERE id = :aid OR user_id = (SELECT user_id FROM accounts WHERE id = :aid)"),
            {"aid": account_id},
        )
        account_emails = [r["email_address"] for r in acct_result.mappings().all()]

    # Get the primary account email
    primary_email = account_emails[0] if account_emails else ""

    initial_state = {
        "normalized_item_id": str(ni["id"]),
        "account_id": str(ni["account_id"]),
        "account_owner_emails": account_emails,
        "account_owner_email": primary_email,
        "subject": ni.get("subject") or "",
        "body_text": ni["body_text"],
        "sender_email": ni.get("sender_email") or "",
        "sender_name": ni.get("sender_name"),
        "recipients": ni.get("recipients") or [],
        "sent_date": (
            ni["sent_at"].strftime("%Y-%m-%d")
            if ni.get("sent_at")
            else None
        ),
        "thread_id": ni.get("thread_id") or "",
        "extracted_commitments": [],
        "resolved_commitments": [],
        "stored_commitment_ids": [],
        "review_items_created": [],
        "deduplicated_count": 0,
    }

    try:
        graph_result = await extraction_graph.ainvoke(initial_state)
        commitments_stored = len(graph_result.get("stored_commitment_ids", []))
        review_items = graph_result.get("review_items_created", 0)

        review_count = len(review_items) if isinstance(review_items, list) else review_items

        logger.info(
            "Inline extraction for %s: %d commitments, %d review items",
            normalized_item_id, 
            commitments_stored, 
            review_count, 
        )

        async with AsyncSessionLocal() as db:
            async with db.begin():
                await db.execute(
                    text("UPDATE normalized_items SET processing_status = 'processed' WHERE id = :nid"),
                    {"nid": normalized_item_id},
                )
        
        # # Create calendar events for commitments with due dates.
        # try:
        #     stored_ids = graph_result.get("stored_commitment_ids", [])
        #     if stored_ids:
        #         async with AsyncSessionLocal() as db2:
        #             for cid in stored_ids:
        #                 row = await db2.execute(
        #                     text(
        #                         """
        #                         SELECT c.summary, c.due_date, c.direction,
        #                                p_owner.email_addresses[1] as owner_email,
        #                                p_target.email_addresses[1] as target_email
        #                         FROM commitments c
        #                         JOIN persons p_owner ON p_owner.id = c.owner_person_id
        #                         LEFT JOIN persons p_target ON p_target.id = c.target_person_id
        #                         WHERE c.id = :cid AND c.due_date IS NOT NULL
        #                         """
        #                     ),
        #                     {"cid": cid},
        #                 )
        #                 commitment = row.mappings().first()

        #                 if commitment and commitment["due_date"]:
        #                     await create_commitment_event(
        #                         account_id=account_id,
        #                         summary=commitment["summary"],
        #                         due_date=str(commitment["due_date"]),
        #                         direction=commitment["direction"],
        #                         owner_email=commitment.get("owner_email"),
        #                         target_email=commitment.get("target_email"),
        #                         commitment_id=cid,
        #                     )
        # except Exception:
        #     logger.exception("Calendar event creation failed")

        return {"status": "processed", "commitments_stored": commitments_stored, "review_items": review_items}

    except Exception as exc:
        logger.exception("Extraction failed for %s", normalized_item_id)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await db.execute(
                    text("UPDATE normalized_items SET processing_status = 'error' WHERE id = :nid"),
                    {"nid": normalized_item_id},
                )
        return {"status": "error", "error": str(exc)}