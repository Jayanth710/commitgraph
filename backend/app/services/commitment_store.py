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
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


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
            INSERT INTO evidence_links (
                commitment_id,
                normalized_item_id,
                evidence_type,
                extracted_snippet
            )
            VALUES (
                :commitment_id,
                :normalized_item_id,
                :evidence_type,
                :extracted_snippet
            )
            RETURNING id
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
            INSERT INTO review_queue (
                commitment_id,
                reason,
                suggested_action
            )
            VALUES (
                :commitment_id,
                :reason,
                :suggested_action
            )
            RETURNING id
            """
        ),
        {
            "commitment_id": commitment_id,
            "reason": reason,
            "suggested_action": suggested_action,
        },
    )
    return dict(result.mappings().one())
