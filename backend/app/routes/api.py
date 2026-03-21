"""
REST API endpoints for the CommitGraph dashboard.
All endpoints are user-scoped — each user sees only their own data.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api", tags=["dashboard-api"])
logger = logging.getLogger(__name__)


@router.get("/commitments")
async def list_commitments(
    user: dict = Depends(get_current_user),
    status: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    user_id = str(user["id"])
    conditions = ["a.user_id = :user_id"]
    params: dict[str, Any] = {"limit": limit, "offset": offset, "user_id": user_id}

    if status:
        conditions.append("c.status = :status")
        params["status"] = status
    if direction:
        conditions.append("c.direction = :direction")
        params["direction"] = direction

    where_clause = "WHERE " + " AND ".join(conditions)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                f"""
                SELECT
                    c.id, c.summary, c.direction, c.status,
                    c.commitment_type, c.confidence_score,
                    c.due_date, c.created_at, c.updated_at,
                    c.completed_at, c.detected_at, c.calendar_event_id,
                    p_owner.display_name as owner_name,
                    p_owner.email_addresses[1] as owner_email,
                    p_owner.is_self as owner_is_self,
                    p_target.display_name as target_name,
                    p_target.email_addresses[1] as target_email
                FROM commitments c
                JOIN persons p_owner ON p_owner.id = c.owner_person_id
                LEFT JOIN persons p_target ON p_target.id = c.target_person_id
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                {where_clause}
                GROUP BY c.id, p_owner.id, p_target.id
                ORDER BY
                    CASE c.status
                        WHEN 'overdue' THEN 0
                        WHEN 'confirmed' THEN 1
                        WHEN 'in_progress' THEN 2
                        WHEN 'detected' THEN 3
                        ELSE 4
                    END,
                    c.due_date ASC NULLS LAST,
                    c.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        rows = result.mappings().all()

        count_result = await db.execute(
            text(
                f"""
                SELECT count(DISTINCT c.id)
                FROM commitments c
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                {where_clause}
                """
            ),
            params,
        )
        total = count_result.scalar()

    return {
        "commitments": [_serialize_row(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }

@router.patch("/commitments/reorder")
async def reorder_commitments(body: dict, user: dict = Depends(get_current_user)):
    """Update priority order for a list of commitment IDs."""
    order = body.get("order", [])  # List of { id, priority }

    if not order:
        raise HTTPException(status_code=400, detail="No order provided")

    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        async with db.begin():
            for item in order:
                await db.execute(
                    text(
                        """
                        UPDATE commitments SET priority = :priority, updated_at = now()
                        WHERE id = :cid
                        AND id IN (
                            SELECT c.id FROM commitments c
                            JOIN evidence_links el ON el.commitment_id = c.id
                            JOIN normalized_items ni ON ni.id = el.normalized_item_id
                            JOIN accounts a ON a.id = ni.account_id
                            WHERE a.user_id = :user_id
                        )
                        """
                    ),
                    {"cid": item["id"], "priority": item["priority"], "user_id": user_id},
                )

    return {"message": "Reordered", "count": len(order)}

@router.get("/commitments/{commitment_id}")
async def get_commitment(commitment_id: str, user: dict = Depends(get_current_user)):
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT
                    c.id, c.summary, c.raw_text, c.direction, c.status,
                    c.commitment_type, c.confidence_score,
                    c.due_date, c.due_date_confidence,
                    c.created_at, c.updated_at, c.completed_at, c.detected_at, c.calendar_event_id,
                    p_owner.display_name as owner_name,
                    p_owner.email_addresses[1] as owner_email,
                    p_owner.is_self as owner_is_self,
                    p_target.display_name as target_name,
                    p_target.email_addresses[1] as target_email
                FROM commitments c
                JOIN persons p_owner ON p_owner.id = c.owner_person_id
                LEFT JOIN persons p_target ON p_target.id = c.target_person_id
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE c.id = :cid AND a.user_id = :user_id
                LIMIT 1
                """
            ),
            {"cid": commitment_id, "user_id": user_id},
        )
        commitment = result.mappings().first()
        if not commitment:
            raise HTTPException(status_code=404, detail="Commitment not found")

        evidence_result = await db.execute(
            text(
                """
                SELECT
                    e.id, e.evidence_type, e.extracted_snippet, e.linked_at,
                    n.subject, n.sender_email, n.sender_name,
                    n.item_type, n.sent_at, n.received_at,
                    n.event_start, n.event_end,
                    n.body_text, n.recipients
                FROM evidence_links e
                JOIN normalized_items n ON n.id = e.normalized_item_id
                WHERE e.commitment_id = :cid
                ORDER BY e.linked_at ASC
                """
            ),
            {"cid": commitment_id},
        )
        evidence = evidence_result.mappings().all()

    return {
        "commitment": _serialize_row(commitment),
        "evidence": [_serialize_row(e) for e in evidence],
    }


@router.patch("/commitments/{commitment_id}")
async def update_commitment_status(
    commitment_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
):
    user_id = str(user["id"])
    new_status = body.get("status")
    valid_statuses = {"confirmed", "in_progress", "completed", "abandoned", "delegated"}

    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # Verify ownership.
            ownership = await db.execute(
                text(
                    """
                    SELECT c.status FROM commitments c
                    JOIN evidence_links el ON el.commitment_id = c.id
                    JOIN normalized_items ni ON ni.id = el.normalized_item_id
                    JOIN accounts a ON a.id = ni.account_id
                    WHERE c.id = :cid AND a.user_id = :user_id
                    LIMIT 1
                    """
                ),
                {"cid": commitment_id, "user_id": user_id},
            )
            row = ownership.scalar_one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="Commitment not found")

            terminal = {"completed", "abandoned"}
            if row in terminal and new_status not in {"confirmed", "in_progress"}:
                raise HTTPException(status_code=400, detail=f"Can only revert '{row}' to 'confirmed' or 'in_progress'")

            update_fields = "status = :new_status, status_changed_at = now(), updated_at = now()"
            if new_status == "completed":
                update_fields += ", completed_at = now()"
            elif new_status in ("confirmed", "in_progress") and row in ("completed", "abandoned"):
                update_fields += ", completed_at = NULL"

            await db.execute(
                text(f"UPDATE commitments SET {update_fields} WHERE id = :cid"),
                {"cid": commitment_id, "new_status": new_status},
            )

    return {"commitment_id": commitment_id, "status": new_status}

@router.get("/commitments/search")
async def search_commitments(
    user: dict = Depends(get_current_user),
    q: str = Query(default="", min_length=0),
    status: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    user_id = str(user["id"])
    conditions = ["a.user_id = :user_id"]
    params: dict[str, Any] = {"user_id": user_id, "limit": limit}

    if q:
        conditions.append("(c.summary ILIKE :q OR c.raw_text ILIKE :q)")
        params["q"] = f"%{q}%"
    if status:
        conditions.append("c.status = :status")
        params["status"] = status
    if direction:
        conditions.append("c.direction = :direction")
        params["direction"] = direction

    where_clause = "WHERE " + " AND ".join(conditions)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                f"""
                SELECT DISTINCT ON (c.id)
                    c.id, c.summary, c.direction, c.status,
                    c.commitment_type, c.confidence_score,
                    c.due_date, c.created_at,
                    p_owner.display_name as owner_name,
                    p_owner.email_addresses[1] as owner_email,
                    p_owner.is_self as owner_is_self,
                    p_target.display_name as target_name,
                    p_target.email_addresses[1] as target_email
                FROM commitments c
                JOIN persons p_owner ON p_owner.id = c.owner_person_id
                LEFT JOIN persons p_target ON p_target.id = c.target_person_id
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                {where_clause}
                ORDER BY c.id, c.created_at DESC
                LIMIT :limit
                """
            ),
            params,
        )
        rows = result.mappings().all()

    return {"commitments": [_serialize_row(r) for r in rows], "total": len(rows)}

@router.get("/review-queue")
async def list_review_queue(user: dict = Depends(get_current_user)):
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT
                    rq.id, rq.reason, rq.suggested_action, rq.status as review_status,
                    rq.created_at as review_created_at,
                    c.id as commitment_id, c.summary, c.raw_text,
                    c.direction, c.confidence_score, c.due_date,
                    c.commitment_type,
                    p_owner.email_addresses[1] as owner_email,
                    p_target.email_addresses[1] as target_email,
                    n.subject as source_subject, n.sender_email as source_sender,
                    n.body_text as source_body
                FROM review_queue rq
                JOIN commitments c ON c.id = rq.commitment_id
                JOIN persons p_owner ON p_owner.id = c.owner_person_id
                LEFT JOIN persons p_target ON p_target.id = c.target_person_id
                LEFT JOIN evidence_links e ON e.commitment_id = c.id AND e.evidence_type = 'origin'
                LEFT JOIN normalized_items n ON n.id = e.normalized_item_id
                LEFT JOIN accounts a ON a.id = n.account_id
                WHERE rq.status = 'pending' AND a.user_id = :user_id
                ORDER BY rq.created_at DESC
                """
            ),
            {"user_id": user_id},
        )
        rows = result.mappings().all()

    return {"review_items": [_serialize_row(r) for r in rows], "total": len(rows)}


@router.patch("/review-queue/{review_id}")
async def review_action(review_id: str, body: dict, user: dict = Depends(get_current_user)):
    action = body.get("action")
    if action not in {"confirm", "reject", "dismiss"}:
        raise HTTPException(status_code=400, detail="Action must be: confirm, reject, dismiss")

    async with AsyncSessionLocal() as db:
        async with db.begin():
            rq_result = await db.execute(
                text("SELECT commitment_id FROM review_queue WHERE id = :rid AND status = 'pending'"),
                {"rid": review_id},
            )
            rq_row = rq_result.mappings().first()
            if not rq_row:
                raise HTTPException(status_code=404, detail="Review item not found or already reviewed")

            commitment_id = rq_row["commitment_id"]

            if action == "confirm":
                await db.execute(
                    text("UPDATE commitments SET status = 'confirmed', status_changed_at = now(), updated_at = now() WHERE id = :cid"),
                    {"cid": commitment_id},
                )
                await db.execute(
                    text("UPDATE review_queue SET status = 'reviewed', reviewed_at = now(), user_decision = 'confirmed' WHERE id = :rid"),
                    {"rid": review_id},
                )
            elif action == "reject":
                await db.execute(text("DELETE FROM commitments WHERE id = :cid"), {"cid": commitment_id})
                await db.execute(
                    text("UPDATE review_queue SET status = 'dismissed', reviewed_at = now(), user_decision = 'rejected' WHERE id = :rid"),
                    {"rid": review_id},
                )
            else:
                await db.execute(
                    text("UPDATE review_queue SET status = 'dismissed', reviewed_at = now(), user_decision = 'dismissed' WHERE id = :rid"),
                    {"rid": review_id},
                )

    return {"review_id": review_id, "action": action, "commitment_id": str(commitment_id)}


@router.get("/timeline")
async def list_timeline(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    account_id: str | None = Query(default=None),
):
    user_id = str(user["id"])
    conditions = ["a.user_id = :user_id"]
    params: dict[str, Any] = {"limit": limit, "offset": offset, "user_id": user_id}

    if account_id:
        conditions.append("n.account_id = :account_id")
        params["account_id"] = account_id

    where_clause = "WHERE " + " AND ".join(conditions)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                f"""
                SELECT
                    n.id, n.item_type, n.subject, n.sender_email, n.sender_name,
                    n.sent_at, n.received_at, n.event_start, n.event_end,
                    n.account_id, n.processing_status,
                    a.provider, a.email_address as account_email
                FROM normalized_items n
                JOIN source_items s ON s.id = n.source_item_id
                JOIN accounts a ON a.id = n.account_id
                {where_clause}
                ORDER BY COALESCE(n.received_at, n.sent_at, n.event_start) DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        rows = result.mappings().all()

    return {"items": [_serialize_row(r) for r in rows], "total": len(rows)}


@router.get("/persons")
async def list_persons(user: dict = Depends(get_current_user)):
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT
                    p.id, p.display_name, p.email_addresses, p.is_self,
                    p.first_seen_at, p.last_seen_at,
                    count(DISTINCT c.id) as commitment_count
                FROM persons p
                LEFT JOIN commitments c ON c.owner_person_id = p.id OR c.target_person_id = p.id
                LEFT JOIN evidence_links el ON el.commitment_id = c.id
                LEFT JOIN normalized_items ni ON ni.id = el.normalized_item_id
                LEFT JOIN accounts a ON a.id = ni.account_id
                WHERE a.user_id = :user_id
                GROUP BY p.id
                HAVING count(DISTINCT c.id) > 0
                ORDER BY count(DISTINCT c.id) DESC, p.last_seen_at DESC
                """
            ),
            {"user_id": user_id},
        )
        rows = result.mappings().all()

    return {"persons": [_serialize_row(r) for r in rows]}


@router.get("/accounts")
async def list_accounts(user: dict = Depends(get_current_user)):
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT id, provider, email_address, display_name,
                       sync_status, last_sync_at, watch_expiry, created_at
                FROM accounts
                WHERE user_id = :user_id
                ORDER BY created_at ASC
                """
            ),
            {"user_id": user_id},
        )
        rows = result.mappings().all()

    return {"accounts": [_serialize_row(r) for r in rows]}


@router.delete("/accounts/{account_id}")
async def disconnect_account(account_id: str, user: dict = Depends(get_current_user)):
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                text("SELECT id, email_address, provider FROM accounts WHERE id = :aid AND user_id = :uid"),
                {"aid": account_id, "uid": user_id},
            )
            account = result.mappings().first()
            if not account:
                raise HTTPException(status_code=404, detail="Account not found")

            await db.execute(
                text("DELETE FROM evidence_links WHERE normalized_item_id IN (SELECT id FROM normalized_items WHERE account_id = :aid)"),
                {"aid": account_id},
            )
            await db.execute(
                text("DELETE FROM review_queue WHERE commitment_id IN (SELECT c.id FROM commitments c JOIN evidence_links e ON e.commitment_id = c.id JOIN normalized_items n ON n.id = e.normalized_item_id WHERE n.account_id = :aid)"),
                {"aid": account_id},
            )
            await db.execute(text("DELETE FROM normalized_items WHERE account_id = :aid"), {"aid": account_id})
            await db.execute(text("DELETE FROM source_items WHERE account_id = :aid"), {"aid": account_id})
            await db.execute(text("DELETE FROM accounts WHERE id = :aid"), {"aid": account_id})

    return {"message": "Account disconnected", "account_id": account_id, "email_address": account["email_address"], "provider": account["provider"]}


@router.get("/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT
                    count(DISTINCT c.id) FILTER (WHERE c.status NOT IN ('completed', 'abandoned')) as open_count,
                    count(DISTINCT c.id) FILTER (WHERE c.status = 'overdue') as overdue_count,
                    count(DISTINCT c.id) FILTER (WHERE c.status = 'completed') as completed_count,
                    count(DISTINCT c.id) FILTER (WHERE c.direction = 'outbound' AND c.status NOT IN ('completed', 'abandoned')) as i_owe_count,
                    count(DISTINCT c.id) FILTER (WHERE c.direction = 'inbound' AND c.status NOT IN ('completed', 'abandoned')) as owed_to_me_count
                FROM commitments c
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE a.user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        stats = result.mappings().first()

        review_result = await db.execute(
            text(
                """
                SELECT count(*) FROM review_queue rq
                JOIN commitments c ON c.id = rq.commitment_id
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE rq.status = 'pending' AND a.user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        review_count = review_result.scalar()

    return {**_serialize_row(stats), "review_queue_count": review_count}


def _serialize_row(row) -> dict:
    d = dict(row)
    for key, value in d.items():
        if hasattr(value, "isoformat"):
            d[key] = value.isoformat()
        elif isinstance(value, (list, dict)):
            pass
        elif isinstance(value, bytes):
            d[key] = None
    return d

@router.get("/stats/chart")
async def get_chart_data(user: dict = Depends(get_current_user)):
    """Commitments over time for the past 30 days."""
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT
                    date_trunc('day', c.detected_at)::date as day,
                    count(DISTINCT c.id) FILTER (WHERE c.direction = 'outbound') as outbound,
                    count(DISTINCT c.id) FILTER (WHERE c.direction = 'inbound') as inbound
                FROM commitments c
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE a.user_id = :user_id
                  AND c.detected_at >= now() - interval '30 days'
                GROUP BY date_trunc('day', c.detected_at)::date
                ORDER BY day ASC
                """
            ),
            {"user_id": user_id},
        )
        rows = result.mappings().all()

    return {"chart_data": [_serialize_row(r) for r in rows]}

@router.get("/digest/weekly")
async def weekly_digest(user: dict = Depends(get_current_user)):
    """Generate a weekly summary of commitment activity."""
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        # This week's stats.
        result = await db.execute(
            text(
                """
                SELECT
                    count(DISTINCT c.id) FILTER (WHERE c.detected_at >= now() - interval '7 days') as new_this_week,
                    count(DISTINCT c.id) FILTER (WHERE c.completed_at >= now() - interval '7 days') as completed_this_week,
                    count(DISTINCT c.id) FILTER (WHERE c.status = 'overdue') as currently_overdue,
                    count(DISTINCT c.id) FILTER (WHERE c.due_date >= now() AND c.due_date < now() + interval '7 days' AND c.status NOT IN ('completed', 'abandoned')) as due_this_week,
                    count(DISTINCT c.id) FILTER (WHERE c.status NOT IN ('completed', 'abandoned')) as total_open
                FROM commitments c
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE a.user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        stats = result.mappings().first()

        # Commitments due this week.
        due_result = await db.execute(
            text(
                """
                SELECT DISTINCT ON (c.id)
                    c.id, c.summary, c.direction, c.status, c.due_date, c.confidence_score,
                    p_owner.email_addresses[1] as owner_email,
                    p_owner.is_self as owner_is_self,
                    p_target.email_addresses[1] as target_email
                FROM commitments c
                JOIN persons p_owner ON p_owner.id = c.owner_person_id
                LEFT JOIN persons p_target ON p_target.id = c.target_person_id
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE a.user_id = :user_id
                  AND c.due_date >= now()
                  AND c.due_date < now() + interval '7 days'
                  AND c.status NOT IN ('completed', 'abandoned')
                ORDER BY c.id, c.due_date ASC
                """
            ),
            {"user_id": user_id},
        )
        due_this_week = due_result.mappings().all()

        # Recently completed.
        completed_result = await db.execute(
            text(
                """
                SELECT DISTINCT ON (c.id)
                    c.id, c.summary, c.direction, c.completed_at,
                    p_target.email_addresses[1] as target_email
                FROM commitments c
                LEFT JOIN persons p_target ON p_target.id = c.target_person_id
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE a.user_id = :user_id
                  AND c.completed_at >= now() - interval '7 days'
                ORDER BY c.id, c.completed_at DESC
                """
            ),
            {"user_id": user_id},
        )
        recently_completed = completed_result.mappings().all()

        # Overdue items.
        overdue_result = await db.execute(
            text(
                """
                SELECT DISTINCT ON (c.id)
                    c.id, c.summary, c.direction, c.due_date, c.status,
                    p_target.email_addresses[1] as target_email
                FROM commitments c
                LEFT JOIN persons p_target ON p_target.id = c.target_person_id
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE a.user_id = :user_id
                  AND c.status = 'overdue'
                ORDER BY c.id, c.due_date ASC
                """
            ),
            {"user_id": user_id},
        )
        overdue_items = overdue_result.mappings().all()

    return {
        "stats": _serialize_row(stats),
        "due_this_week": [_serialize_row(r) for r in due_this_week],
        "recently_completed": [_serialize_row(r) for r in recently_completed],
        "overdue": [_serialize_row(r) for r in overdue_items],
    }

@router.post("/commitments/{commitment_id}/calendar-event")
async def create_calendar_event_for_commitment(
    commitment_id: str,
    user: dict = Depends(get_current_user),
):
    """Create a Google Calendar event for a specific commitment."""
    from app.services.gcal_create import create_commitment_event

    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT c.id, c.summary, c.due_date, c.direction,
                       c.status, c.confidence_score, c.calendar_event_id,
                       p_owner.email_addresses[1] as owner_email,
                       p_target.email_addresses[1] as target_email,
                       a.id as account_id
                FROM commitments c
                JOIN persons p_owner ON p_owner.id = c.owner_person_id
                LEFT JOIN persons p_target ON p_target.id = c.target_person_id
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE c.id = :cid AND a.user_id = :uid
                LIMIT 1
                """
            ),
            {"cid": commitment_id, "uid": user_id},
        )
        row = result.mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Commitment not found")

    if not row["due_date"]:
        raise HTTPException(status_code=400, detail="Commitment has no due date")

    if row["status"] not in {"confirmed", "in_progress"}:
        raise HTTPException(
            status_code=400,
            detail="Only confirmed or in-progress commitments can be added to calendar",
        )

    if (row["confidence_score"] or 0) < 0.8:
        raise HTTPException(
            status_code=400,
            detail="Commitment confidence is too low to add to calendar",
        )

    if row["calendar_event_id"]:
        return {
            "message": "Calendar event already exists",
            "event_id": row["calendar_event_id"],
        }

    event = await create_commitment_event(
        account_id=str(row["account_id"]),
        summary=row["summary"],
        due_date=str(row["due_date"]),
        direction=row["direction"],
        owner_email=row.get("owner_email"),
        target_email=row.get("target_email"),
        commitment_id=commitment_id,
    )

    if not event:
        raise HTTPException(status_code=500, detail="Failed to create calendar event")

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await db.execute(
                text(
                    """
                    UPDATE commitments
                    SET calendar_event_id = :eid,
                        updated_at = now()
                    WHERE id = :cid
                    """
                ),
                {
                    "eid": event.get("id"),
                    "cid": commitment_id,
                },
            )

    return {
        "message": "Calendar event created",
        "event_id": event.get("id"),
    }

@router.delete("/commitments/{commitment_id}/calendar-event")
async def delete_calendar_event_for_commitment(
    commitment_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a Google Calendar event linked to a commitment."""
    from app.services.gcal_delete import delete_commitment_event

    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT c.id, c.calendar_event_id, a.id as account_id
                FROM commitments c
                JOIN evidence_links el ON el.commitment_id = c.id
                JOIN normalized_items ni ON ni.id = el.normalized_item_id
                JOIN accounts a ON a.id = ni.account_id
                WHERE c.id = :cid AND a.user_id = :uid
                LIMIT 1
                """
            ),
            {"cid": commitment_id, "uid": user_id},
        )
        row = result.mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Commitment not found")

    if not row["calendar_event_id"]:
        raise HTTPException(status_code=400, detail="No calendar event linked")

    deleted = await delete_commitment_event(
        account_id=str(row["account_id"]),
        event_id=row["calendar_event_id"],
    )

    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete calendar event")

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await db.execute(
                text(
                    """
                    UPDATE commitments
                    SET calendar_event_id = NULL,
                        updated_at = now()
                    WHERE id = :cid
                    """
                ),
                {"cid": commitment_id},
            )

    return {
        "message": "Calendar event removed",
        "commitment_id": commitment_id,
    }
