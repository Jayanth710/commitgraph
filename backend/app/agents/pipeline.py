"""
LangGraph extraction pipeline.

This is the brain of CommitGraph. It orchestrates:

    normalized_item (email)
         │
         ▼
    ┌─────────┐     ┌─────────────┐     ┌───────────────┐
    │ EXTRACT │────▶│   RESOLVE   │────▶│  ROUTE + STORE │
    │         │     │  ENTITIES   │     │               │
    └─────────┘     └─────────────┘     └───────────────┘
      LLM call        DB lookups        confidence check
      (gpt-4o-mini)   (no LLM)         ├── ≥0.8 → store as confirmed
                                        └── <0.8 → store as detected
                                                   + review queue

How LangGraph works (the 60-second version):
    1. You define a State (TypedDict) — a bag of data that flows through the graph.
    2. You define nodes — async Python functions that read from state and write back.
    3. You define edges — which node runs after which.
    4. Conditional edges — pick the next node based on state values.
    5. graph.compile() gives you a runnable. Call it with initial state → get final state.

Each node receives the ENTIRE state dict, reads what it needs, and returns
only the keys it wants to update. LangGraph merges the updates.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.extraction import extract_commitments
from app.core.config import get_settings
from app.services.commitment_store import (
    insert_commitment,
    insert_evidence_link,
    insert_review_queue_item,
)
from app.services.entity_resolution import resolve_person
from app.services.schemas import ExtractedCommitment

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# State schema
#
# This TypedDict defines EVERY piece of data that flows through the graph.
# Each node reads what it needs and writes what it produces.
# LangGraph manages the state — you never pass it manually between nodes.
# ---------------------------------------------------------------------------
class ExtractionState(TypedDict, total=False):
    """State that flows through the extraction pipeline.

    Fields are populated incrementally:
    - Inputs (set before graph runs): normalized_item_id, email content, account info
    - After EXTRACT node: extracted_commitments
    - After RESOLVE node: resolved_commitments
    - After STORE node: stored_commitment_ids, review_items_created
    """

    # --- Inputs (set by the caller before invoking the graph) ---
    normalized_item_id: str
    account_id: str
    account_owner_email: str
    account_owner_emails: list[str]   # All connected account emails (for is_self detection)

    # Email content (from normalized_items table)
    sender_email: str
    sender_name: str | None
    recipients: list[dict]
    subject: str | None
    body_text: str | None
    sent_date: str | None
    thread_id: str | None

    # --- Populated by extract node ---
    extracted_commitments: list[dict[str, Any]]

    # --- Populated by resolve node ---
    resolved_commitments: list[dict[str, Any]]

    # --- Populated by store node ---
    stored_commitment_ids: list[str]
    review_items_created: list[str]
    deduplicated_count: int


# ---------------------------------------------------------------------------
# Node 1: EXTRACT — Call the LLM to find commitments
# ---------------------------------------------------------------------------
async def extract_node(state: ExtractionState) -> dict:
    """Call the LLM to extract commitments from the email.

    Reads: email content fields from state
    Writes: extracted_commitments (list of dicts from Pydantic models)
    """
    result = await extract_commitments(
        account_owner_email=state["account_owner_email"],
        sender_email=state["sender_email"],
        sender_name=state.get("sender_name"),
        recipients=state.get("recipients", []),
        subject=state.get("subject"),
        body_text=state.get("body_text"),
        sent_date=state.get("sent_date"),
    )

    # Convert Pydantic models to dicts for state serialization.
    commitments = [c.model_dump() for c in result.commitments]

    logger.info(
        "Extract node: found %d commitments in email subject=%r",
        len(commitments),
        state.get("subject"),
    )

    return {"extracted_commitments": commitments}


# ---------------------------------------------------------------------------
# Node 2: RESOLVE ENTITIES — Map email addresses to person records
# ---------------------------------------------------------------------------
async def resolve_node(state: ExtractionState) -> dict:
    """Resolve email addresses in extracted commitments to person records.

    For each commitment:
    - Resolve owner_email → persons row (create if new)
    - Resolve target_email → persons row (create if new)
    - Determine direction from the account owner's perspective

    Reads: extracted_commitments, account_owner_emails, db_session
    Writes: resolved_commitments (same list but with person IDs added)
    """
    # Import here to avoid circular imports with the session module.
    from app.db.session import AsyncSessionLocal

    extracted = state.get("extracted_commitments", [])
    if not extracted:
        return {"resolved_commitments": []}

    owner_emails = state.get("account_owner_emails", [])
    resolved = []

    async with AsyncSessionLocal() as db:
        async with db.begin():
            for commitment in extracted:
                owner_email = commitment["owner_email"]
                target_email = commitment.get("target_email")

                # Resolve the owner (who made the commitment).
                owner_person = await resolve_person(
                    db,
                    email=owner_email,
                    display_name=None,
                    account_owner_emails=owner_emails,
                )

                # Resolve the target (who it's directed at), if any.
                target_person = None
                if target_email:
                    target_person = await resolve_person(
                        db,
                        email=target_email,
                        display_name=None,
                        account_owner_emails=owner_emails,
                    )

                resolved.append({
                    **commitment,
                    "owner_person_id": str(owner_person["id"]),
                    "owner_is_self": owner_person["is_self"],
                    "target_person_id": str(target_person["id"]) if target_person else None,
                    "target_is_self": target_person["is_self"] if target_person else False,
                })

    logger.info("Resolve node: resolved %d commitments", len(resolved))
    return {"resolved_commitments": resolved}


# ---------------------------------------------------------------------------
# Node 3: STORE — Reconcile duplicates, then persist + route by confidence
# ---------------------------------------------------------------------------
async def store_node(state: ExtractionState) -> dict:
    """Store resolved commitments in the database, with duplicate detection.

    For each commitment:
    1. Check if a similar commitment already exists (reconciliation)
       - If duplicate found → add evidence_link to existing, skip creation
       - If no match → create new commitment
    2. Route by confidence:
       - confidence_score >= threshold → status = 'confirmed'
       - confidence_score < threshold  → status = 'detected' + review_queue

    Reads: resolved_commitments, normalized_item_id, thread_id
    Writes: stored_commitment_ids, review_items_created, deduplicated_count
    """
    from app.db.session import AsyncSessionLocal
    from app.services.reconciliation import find_duplicate_commitment

    resolved = state.get("resolved_commitments", [])
    if not resolved:
        return {"stored_commitment_ids": [], "review_items_created": [], "deduplicated_count": 0}

    threshold = settings.commitment_confidence_threshold
    normalized_item_id = state["normalized_item_id"]
    thread_id = state.get("thread_id")
    stored_ids: list[str] = []
    review_ids: list[str] = []
    deduplicated = 0

    async with AsyncSessionLocal() as db:
        async with db.begin():
            for commitment in resolved:
                confidence = commitment["confidence_score"]

                # --- Reconciliation: check for duplicates FIRST ---
                existing = await find_duplicate_commitment(
                    db,
                    owner_person_id=commitment["owner_person_id"],
                    target_person_id=commitment.get("target_person_id"),
                    summary=commitment["summary"],
                    thread_id=thread_id,
                )

                if existing:
                    # Duplicate found — don't create a new commitment.
                    # Instead, link this email as additional evidence.
                    existing_id = str(existing["id"])

                    await insert_evidence_link(
                        db,
                        commitment_id=existing_id,
                        normalized_item_id=normalized_item_id,
                        evidence_type="update",
                        extracted_snippet=commitment.get("raw_text"),
                    )

                    deduplicated += 1
                    logger.info(
                        "Deduplicated: new summary=%r matched existing=%s summary=%r. "
                        "Added evidence_link instead of new commitment.",
                        commitment["summary"],
                        existing_id,
                        existing["summary"],
                    )
                    continue

                # --- No duplicate: create new commitment ---
                status = "confirmed" if confidence >= threshold else "detected"

                # Parse due_date from string to date if present.
                due_date = None
                raw_due_date = commitment.get("due_date")
                if raw_due_date:
                    try:
                        if isinstance(raw_due_date, str):
                            parsed = date.fromisoformat(raw_due_date)
                            due_date = datetime(
                                parsed.year, parsed.month, parsed.day,
                                tzinfo=timezone.utc,
                            )
                        elif isinstance(raw_due_date, date):
                            due_date = datetime(
                                raw_due_date.year, raw_due_date.month, raw_due_date.day,
                                tzinfo=timezone.utc,
                            )
                    except (ValueError, TypeError):
                        logger.warning("Invalid due_date: %r", raw_due_date)

                # Insert the commitment.
                commitment_row = await insert_commitment(
                    db,
                    owner_person_id=commitment["owner_person_id"],
                    target_person_id=commitment.get("target_person_id"),
                    direction=commitment["direction"],
                    summary=commitment["summary"],
                    raw_text=commitment["raw_text"],
                    commitment_type=commitment["commitment_type"],
                    due_date=due_date,
                    due_date_confidence=commitment.get("due_date_confidence", 0.0),
                    confidence_score=confidence,
                    status=status,
                )

                commitment_id = str(commitment_row["id"])
                stored_ids.append(commitment_id)

                # Link commitment to the source email.
                await insert_evidence_link(
                    db,
                    commitment_id=commitment_id,
                    normalized_item_id=normalized_item_id,
                    evidence_type="origin",
                    extracted_snippet=commitment.get("raw_text"),
                )

                # If low confidence, add to review queue.
                if status == "detected":
                    review_row = await insert_review_queue_item(
                        db,
                        commitment_id=commitment_id,
                        reason="low_confidence",
                        suggested_action="confirm",
                    )
                    review_ids.append(str(review_row["id"]))

                logger.info(
                    "Stored commitment %s status=%s confidence=%.2f summary=%r",
                    commitment_id,
                    status,
                    confidence,
                    commitment["summary"],
                )

    if deduplicated:
        logger.info(
            "Reconciliation: %d new, %d deduplicated",
            len(stored_ids),
            deduplicated,
        )

    return {
        "stored_commitment_ids": stored_ids,
        "review_items_created": review_ids,
        "deduplicated_count": deduplicated,
    }


# ---------------------------------------------------------------------------
# Conditional edge: skip store if no commitments
# ---------------------------------------------------------------------------
def should_resolve(state: ExtractionState) -> str:
    """After extraction, decide whether to continue or stop.

    If the LLM found zero commitments, there's nothing to resolve or store.
    """
    extracted = state.get("extracted_commitments", [])
    if not extracted:
        return "end"
    return "resolve"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------
def build_extraction_graph() -> Any:
    """Construct and compile the LangGraph extraction pipeline.

    Returns a compiled graph that can be invoked with:
        result = await graph.ainvoke(initial_state)
    """
    graph = StateGraph(ExtractionState)

    # Add nodes — each is an async function that transforms state.
    graph.add_node("extract", extract_node)
    graph.add_node("resolve", resolve_node)
    graph.add_node("store", store_node)

    # Set the entry point — where the graph starts.
    graph.set_entry_point("extract")

    # Conditional edge after extract: if no commitments, skip to END.
    graph.add_conditional_edges(
        "extract",
        should_resolve,
        {
            "resolve": "resolve",
            "end": END,
        },
    )

    # Linear edges for the rest.
    graph.add_edge("resolve", "store")
    graph.add_edge("store", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Module-level compiled graph — reused across all invocations
# ---------------------------------------------------------------------------
extraction_graph = build_extraction_graph()
