from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _serialize_row(row) -> dict[str, Any]:
    d = dict(row)
    for key, value in d.items():
        if hasattr(value, "isoformat"):
            d[key] = value.isoformat()
        elif isinstance(value, bytes):
            d[key] = None
    return d


async def get_weekly_digest_data(
    db: AsyncSession,
    *,
    user_id: str,
    account_id: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"user_id": user_id}
    extra_condition = ""

    if account_id:
        extra_condition = " AND a.id = :account_id "
        params["account_id"] = account_id

    stats_result = await db.execute(
        text(
            f"""
            SELECT
                count(DISTINCT c.id) FILTER (WHERE c.detected_at >= now() - interval '7 days') as new_this_week,
                count(DISTINCT c.id) FILTER (WHERE c.completed_at >= now() - interval '7 days') as completed_this_week,
                count(DISTINCT c.id) FILTER (WHERE c.status = 'overdue') as currently_overdue,
                count(DISTINCT c.id) FILTER (
                    WHERE c.due_date >= now()
                      AND c.due_date < now() + interval '7 days'
                      AND c.status NOT IN ('completed', 'abandoned')
                ) as due_this_week,
                count(DISTINCT c.id) FILTER (
                    WHERE c.status NOT IN ('completed', 'abandoned')
                ) as total_open,
                count(DISTINCT c.id) FILTER (
                    WHERE c.direction = 'outbound'
                      AND c.status NOT IN ('completed', 'abandoned')
                ) as outbound_open,
                count(DISTINCT c.id) FILTER (
                    WHERE c.direction = 'inbound'
                      AND c.status NOT IN ('completed', 'abandoned')
                ) as inbound_open
            FROM commitments c
            JOIN evidence_links el ON el.commitment_id = c.id
            JOIN normalized_items ni ON ni.id = el.normalized_item_id
            JOIN accounts a ON a.id = ni.account_id
            WHERE a.user_id = :user_id
            {extra_condition}
            """
        ),
        params,
    )
    stats = stats_result.mappings().first()

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
            {extra_condition}
            ORDER BY c.id, c.due_date ASC
            """
        ),
        params,
    )
    due_rows = [_serialize_row(r) for r in due_result.mappings().all()]

    grouped_due: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in due_rows:
        due_date = row.get("due_date")
        day_key = due_date[:10] if due_date else "No due date"
        grouped_due[day_key].append(row)

    due_groups = [
        {"date": date_key, "items": items}
        for date_key, items in sorted(grouped_due.items(), key=lambda x: x[0])
    ]

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
    completed_rows = [_serialize_row(r) for r in completed_result.mappings().all()]

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
    overdue_rows = [_serialize_row(r) for r in overdue_result.mappings().all()]

    people_result = await db.execute(
        text(
            """
            SELECT
                p.id,
                COALESCE(p.display_name, p.email_addresses[1]) as label,
                p.email_addresses[1] as email,
                count(DISTINCT c.id) as open_commitment_count
            FROM persons p
            JOIN commitments c
              ON c.owner_person_id = p.id OR c.target_person_id = p.id
            JOIN evidence_links el ON el.commitment_id = c.id
            JOIN normalized_items ni ON ni.id = el.normalized_item_id
            JOIN accounts a ON a.id = ni.account_id
            WHERE a.user_id = :user_id
              AND c.status NOT IN ('completed', 'abandoned')
            GROUP BY p.id, label, email
            ORDER BY open_commitment_count DESC, label ASC
            LIMIT 5
            """
        ),
        {"user_id": user_id},
    )
    top_people = [_serialize_row(r) for r in people_result.mappings().all()]

    return {
        "stats": _serialize_row(stats),
        "due_this_week": due_rows,
        "due_groups": due_groups,
        "recently_completed": completed_rows,
        "overdue": overdue_rows,
        "top_people": top_people,
    }


async def get_commitment_calendar_create_payload(
    db: AsyncSession,
    *,
    commitment_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT DISTINCT ON (c.id)
                c.id, c.summary, c.due_date, c.direction,
                c.status, c.confidence_score, c.calendar_event_id, c.calendar_event_link,
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
            ORDER BY c.id
            LIMIT 1
            """
        ),
        {"cid": commitment_id, "uid": user_id},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


async def get_commitment_calendar_delete_payload(
    db: AsyncSession,
    *,
    commitment_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT DISTINCT ON (c.id)
                c.id, c.calendar_event_id, c.calendar_event_link, a.id as account_id
            FROM commitments c
            JOIN evidence_links el ON el.commitment_id = c.id
            JOIN normalized_items ni ON ni.id = el.normalized_item_id
            JOIN accounts a ON a.id = ni.account_id
            WHERE c.id = :cid AND a.user_id = :uid
            ORDER BY c.id
            LIMIT 1
            """
        ),
        {"cid": commitment_id, "uid": user_id},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None