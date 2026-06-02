"""
Commitment storage: persist extracted commitments to the database.

Handles:
    - Inserting commitments with all fields
    - Creating evidence_links connecting commitments to their source emails
    - Creating review_queue entries for low-confidence items
    - Commitment status transitions
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def commitment_has_evidence_for_item(
    db: AsyncSession,
    *,
    commitment_id: str,
    normalized_item_id: str,
) -> bool:
    """Return whether this commitment is already linked to the normalized item.

    This prevents the same email from appearing once as Source and again as
    Follow-up when duplicate Gmail notifications re-trigger extraction.
    """
    result = await db.execute(
        text(
            """
            SELECT 1
            FROM evidence_links
            WHERE commitment_id = :commitment_id
              AND normalized_item_id = :normalized_item_id
            LIMIT 1
            """
        ),
        {
            "commitment_id": commitment_id,
            "normalized_item_id": normalized_item_id,
        },
    )
    return result.scalar() is not None


async def insert_commitment(
    db: AsyncSession,
    *,
    owner_person_id: str,
    target_person_id: str | None,
    direction: str,
    summary: str,
    raw_text: str,
    commitment_type: str,
    due_date: datetime | None,
    due_date_confidence: float,
    confidence_score: float,
    status: str = "detected",
) -> dict[str, Any]:
    """Insert a new commitment into the commitments table.

    Returns the full commitment row as a dict.
    """
    result = await db.execute(
        text(
            """
            INSERT INTO commitments (
                owner_person_id,
                target_person_id,
                direction,
                summary,
                raw_text,
                commitment_type,
                due_date,
                due_date_confidence,
                confidence_score,
                status,
                status_changed_at
            )
            VALUES (
                :owner_person_id,
                :target_person_id,
                :direction,
                :summary,
                :raw_text,
                :commitment_type,
                :due_date,
                :due_date_confidence,
                :confidence_score,
                :status,
                now()
            )
            RETURNING id, status, confidence_score
            """
        ),
        {
            "owner_person_id": owner_person_id,
            "target_person_id": target_person_id,
            "direction": direction,
            "summary": summary,
            "raw_text": raw_text,
            "commitment_type": commitment_type,
            "due_date": due_date,
            "due_date_confidence": due_date_confidence,
            "confidence_score": confidence_score,
            "status": status,
        },
    )
    return dict(result.mappings().one())


async def insert_evidence_link(
    db: AsyncSession,
    *,
    commitment_id: str,
    normalized_item_id: str,
    evidence_type: str = "origin",
    extracted_snippet: str | None = None,
) -> dict[str, Any]:
    """Link a commitment to the source email/event that generated it."""
    result = await db.execute(
        text(
            """
            WITH existing AS (
                SELECT id
                FROM evidence_links
                WHERE commitment_id = :commitment_id
                  AND normalized_item_id = :normalized_item_id
                  AND evidence_type = :evidence_type
                  AND COALESCE(extracted_snippet, '') = COALESCE(:extracted_snippet, '')
                LIMIT 1
            ),
            inserted AS (
                INSERT INTO evidence_links (
                    commitment_id,
                    normalized_item_id,
                    evidence_type,
                    extracted_snippet
                )
                SELECT
                    :commitment_id,
                    :normalized_item_id,
                    :evidence_type,
                    :extracted_snippet
                WHERE NOT EXISTS (SELECT 1 FROM existing)
                RETURNING id
            )
            SELECT id FROM inserted
            UNION ALL
            SELECT id FROM existing
            LIMIT 1
            """
        ),
        {
            "commitment_id": commitment_id,
            "normalized_item_id": normalized_item_id,
            "evidence_type": evidence_type,
            "extracted_snippet": extracted_snippet,
        },
    )
    return dict(result.mappings().one())


async def get_commitment_due_date(
    db: AsyncSession,
    commitment_id: str,
) -> datetime | None:
    """Return a commitment's current due_date (or None)."""
    result = await db.execute(
        text("SELECT due_date FROM commitments WHERE id = :id"),
        {"id": commitment_id},
    )
    row = result.first()
    return row[0] if row else None


async def update_commitment_due_date(
    db: AsyncSession,
    commitment_id: str,
    due_date: datetime | None,
) -> None:
    """Update a commitment's due date (e.g. when a re-stated commitment changes it)."""
    await db.execute(
        text(
            "UPDATE commitments SET due_date = :due_date, updated_at = now() WHERE id = :id"
        ),
        {"due_date": due_date, "id": commitment_id},
    )


async def insert_review_queue_item(
    db: AsyncSession,
    *,
    commitment_id: str,
    reason: str,
    suggested_action: str = "confirm",
) -> dict[str, Any]:
    """Add a commitment to the human review queue.

    This is called when confidence_score < threshold.
    The user sees these in the dashboard and decides: confirm, reject, merge, or edit.
    """
    result = await db.execute(
        text(
            """
            WITH existing AS (
                SELECT id
                FROM review_queue
                WHERE commitment_id = :commitment_id
                  AND status = 'pending'
                ORDER BY created_at ASC, id ASC
                LIMIT 1
            ),
            inserted AS (
                INSERT INTO review_queue (
                    commitment_id,
                    reason,
                    suggested_action
                )
                SELECT
                    :commitment_id,
                    :reason,
                    :suggested_action
                WHERE NOT EXISTS (SELECT 1 FROM existing)
                RETURNING id
            )
            SELECT id FROM inserted
            UNION ALL
            SELECT id FROM existing
            LIMIT 1
            """
        ),
        {
            "commitment_id": commitment_id,
            "reason": reason,
            "suggested_action": suggested_action,
        },
    )
    return dict(result.mappings().one())
