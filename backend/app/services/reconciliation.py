"""
Commitment reconciliation: detect duplicates before storing.

When the same email thread generates multiple notifications (retries, 
multiple accounts seeing the same thread, follow-up emails about the 
same commitment), the extraction pipeline can produce duplicate commitments.

This module checks for existing commitments that match a candidate before
storing it. The matching logic uses multiple signals:

    1. Same thread_id + same owner → very likely duplicate
    2. Same owner + same target + similar summary text → probable duplicate
    3. Same owner + similar summary within 7 days → possible duplicate

If a duplicate is found:
    - Add an evidence_link (type='update') to the existing commitment
    - Do NOT create a new commitment row
    - Return the existing commitment ID

If ambiguous:
    - Create a review_queue entry with reason='possible_duplicate'
    - Let the user decide

If no match:
    - Proceed with normal storage (new commitment row)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _word_set(text_str: str) -> set[str]:
    """Extract a set of lowercase words for overlap comparison.
    
    Strips common filler words to focus on meaningful content.
    """
    if not text_str:
        return set()
    
    stop_words = {
        "i", "me", "my", "the", "a", "an", "to", "for", "of", "and",
        "will", "by", "you", "your", "it", "in", "on", "is", "be",
        "that", "this", "with", "have", "also", "them", "their",
    }
    words = set(re.findall(r"[a-z0-9']+", text_str.lower()))
    return words - stop_words


def compute_similarity(summary_a: str, summary_b: str) -> float:
    """Compute word-overlap similarity between two summaries.
    
    Returns a float between 0.0 and 1.0.
    Uses Jaccard similarity: |intersection| / |union|
    
    This is intentionally simple. For v1, keyword overlap catches
    the obvious duplicates ("Send Q3 proposal" vs "Send Q3 proposal to Sarah").
    A future version could use embedding similarity via pgvector.
    """
    words_a = _word_set(summary_a)
    words_b = _word_set(summary_b)
    
    if not words_a or not words_b:
        return 0.0
    
    intersection = words_a & words_b
    union = words_a | words_b
    
    return len(intersection) / len(union)


def compute_containment(summary_a: str, summary_b: str) -> float:
    """Measure whether the shorter summary is mostly contained in the longer one.

    This helps catch review-queue duplicates where a later extraction adds
    hedge words or timing context, e.g.:
    - "Send the deck"
    - "Send the deck sometime next week"
    """
    words_a = _word_set(summary_a)
    words_b = _word_set(summary_b)

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    smaller = min(len(words_a), len(words_b))
    if smaller == 0:
        return 0.0

    return len(intersection) / smaller


def compute_overlap_count(summary_a: str, summary_b: str) -> int:
    return len(_word_set(summary_a) & _word_set(summary_b))


async def find_duplicate_commitment(
    db: AsyncSession,
    *,
    owner_person_id: str,
    target_person_id: str | None,
    direction: str,
    summary: str,
    normalized_item_id: str | None,
    thread_id: str | None,
    similarity_threshold: float = 0.6,
) -> dict[str, Any] | None:
    """Search for an existing commitment that matches the candidate.
    
    Matching priority:
    1. Same thread + same owner → check summary similarity
    2. Same owner + same target + similar summary within 14 days
    
    Returns the matching commitment dict if found, None otherwise.
    """
    
    # Strategy 0: Same normalized email + same owner/direction.
    # This is the strongest duplicate signal for "same email, different heading"
    # cases caused by slightly different LLM summaries from a single message.
    if normalized_item_id:
        result = await db.execute(
            text(
                """
                SELECT c.id, c.summary, c.status, c.confidence_score
                FROM commitments c
                JOIN evidence_links e ON e.commitment_id = c.id
                WHERE c.owner_person_id = :owner_person_id
                  AND c.direction = :direction
                  AND e.normalized_item_id = :normalized_item_id
                  AND c.status NOT IN ('abandoned')
                ORDER BY c.created_at DESC
                LIMIT 10
                """
            ),
            {
                "owner_person_id": owner_person_id,
                "direction": direction,
                "normalized_item_id": normalized_item_id,
            },
        )

        for row in result.mappings().all():
            sim = compute_similarity(summary, row["summary"])
            containment = compute_containment(summary, row["summary"])
            overlap = compute_overlap_count(summary, row["summary"])
            if sim >= 0.45 or (containment >= 0.8 and overlap >= 3):
                logger.info(
                    "Duplicate found (same normalized item): existing=%s similarity=%.2f containment=%.2f overlap=%d",
                    row["id"], sim, containment, overlap,
                )
                return dict(row)

    # Strategy 1: Same thread + same owner.
    # This is the strongest signal — same email thread, same person committing.
    if thread_id:
        result = await db.execute(
            text(
                """
                SELECT c.id, c.summary, c.status, c.confidence_score
                FROM commitments c
                JOIN evidence_links e ON e.commitment_id = c.id
                JOIN normalized_items n ON n.id = e.normalized_item_id
                WHERE c.owner_person_id = :owner_person_id
                  AND c.direction = :direction
                  AND n.thread_id = :thread_id
                  AND c.status NOT IN ('abandoned')
                ORDER BY c.created_at DESC
                LIMIT 10
                """
            ),
            {
                "owner_person_id": owner_person_id,
                "direction": direction,
                "thread_id": thread_id,
            },
        )
        
        for row in result.mappings().all():
            sim = compute_similarity(summary, row["summary"])
            containment = compute_containment(summary, row["summary"])
            if sim >= similarity_threshold or containment >= 0.8:
                logger.info(
                    "Duplicate found (thread match): existing=%s similarity=%.2f containment=%.2f",
                    row["id"], sim, containment,
                )
                return dict(row)
    
    # Strategy 2: Same owner + same target + similar summary, recent.
    # Catches cross-thread duplicates (e.g., forwarded email about same topic).
    if target_person_id:
        result = await db.execute(
            text(
                """
                SELECT id, summary, status, confidence_score
                FROM commitments
                WHERE owner_person_id = :owner_person_id
                  AND direction = :direction
                  AND target_person_id = :target_person_id
                  AND status NOT IN ('abandoned')
                  AND created_at > now() - interval '14 days'
                ORDER BY created_at DESC
                LIMIT 10
                """
            ),
            {
                "owner_person_id": owner_person_id,
                "direction": direction,
                "target_person_id": target_person_id,
            },
        )
        
        for row in result.mappings().all():
            sim = compute_similarity(summary, row["summary"])
            if sim >= similarity_threshold:
                logger.info(
                    "Duplicate found (owner+target match): existing=%s similarity=%.2f",
                    row["id"], sim,
                )
                return dict(row)

    # Strategy 3: Same owner + same direction + very strong summary containment.
    # This catches repeated low-confidence review items with slightly expanded phrasing
    # even when the target is missing or changed between extractions.
    result = await db.execute(
        text(
            """
            SELECT id, summary, status, confidence_score
            FROM commitments
            WHERE owner_person_id = :owner_person_id
              AND direction = :direction
              AND status NOT IN ('abandoned')
              AND created_at > now() - interval '14 days'
            ORDER BY created_at DESC
            LIMIT 20
            """
        ),
        {
            "owner_person_id": owner_person_id,
            "direction": direction,
        },
    )

    for row in result.mappings().all():
        overlap = _word_set(summary) & _word_set(row["summary"])
        containment = compute_containment(summary, row["summary"])
        if containment >= 0.9 and len(overlap) >= 3:
            logger.info(
                "Duplicate found (owner containment match): existing=%s containment=%.2f overlap=%d",
                row["id"], containment, len(overlap),
            )
            return dict(row)
    
    return None
