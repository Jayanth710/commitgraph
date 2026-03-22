from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _serialize_row(row) -> dict[str, Any]:
    data = dict(row)
    for key, value in data.items():
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
        elif isinstance(value, bytes):
            data[key] = None
    return data


def _build_scope(account_id: str | None) -> tuple[dict[str, Any], str]:
    params: dict[str, Any] = {}
    extra_condition = ""
    if account_id:
        extra_condition = " AND a.id = :account_id "
        params["account_id"] = account_id
    return params, extra_condition


def _section(title: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return f"- {title}: none"

    lines = [f"- {title} ({len(items)}):"]
    for item in items[:3]:
        detail = item.get("title") or item.get("summary") or item.get("company_name") or "Untitled"
        lines.append(f"  - {detail}")
    return "\n".join(lines)


async def build_daily_brief_payload(
    db: AsyncSession,
    *,
    user_id: str,
    brief_type: str,
    brief_date: date,
    account_id: str | None = None,
) -> dict[str, Any]:
    scope_params, extra_condition = _build_scope(account_id)
    job_extra_condition = " AND ja.account_id = :account_id " if account_id else ""
    params: dict[str, Any] = {
        "user_id": user_id,
        "brief_date": brief_date,
        "tomorrow": brief_date + timedelta(days=1),
        **scope_params,
    }

    new_commitments_result = await db.execute(
        text(
            f"""
            SELECT DISTINCT ON (c.id)
                c.id,
                c.summary,
                c.direction,
                c.detected_at,
                p_target.email_addresses[1] as target_email
            FROM commitments c
            LEFT JOIN persons p_target ON p_target.id = c.target_person_id
            JOIN evidence_links el ON el.commitment_id = c.id
            JOIN normalized_items ni ON ni.id = el.normalized_item_id
            JOIN accounts a ON a.id = ni.account_id
            WHERE a.user_id = :user_id
              AND c.detected_at::date = :brief_date
              {extra_condition}
            ORDER BY c.id, c.detected_at DESC
            """
        ),
        params,
    )
    new_commitments = [_serialize_row(row) for row in new_commitments_result.mappings().all()]

    completed_result = await db.execute(
        text(
            f"""
            SELECT DISTINCT ON (c.id)
                c.id,
                c.summary,
                c.completed_at,
                p_target.email_addresses[1] as target_email
            FROM commitments c
            LEFT JOIN persons p_target ON p_target.id = c.target_person_id
            JOIN evidence_links el ON el.commitment_id = c.id
            JOIN normalized_items ni ON ni.id = el.normalized_item_id
            JOIN accounts a ON a.id = ni.account_id
            WHERE a.user_id = :user_id
              AND c.completed_at::date = :brief_date
              {extra_condition}
            ORDER BY c.id, c.completed_at DESC
            """
        ),
        params,
    )
    completed_today = [_serialize_row(row) for row in completed_result.mappings().all()]

    overdue_result = await db.execute(
        text(
            f"""
            SELECT DISTINCT ON (c.id)
                c.id,
                c.summary,
                c.direction,
                c.due_date,
                p_target.email_addresses[1] as target_email
            FROM commitments c
            LEFT JOIN persons p_target ON p_target.id = c.target_person_id
            JOIN evidence_links el ON el.commitment_id = c.id
            JOIN normalized_items ni ON ni.id = el.normalized_item_id
            JOIN accounts a ON a.id = ni.account_id
            WHERE a.user_id = :user_id
              AND c.status = 'overdue'
              {extra_condition}
            ORDER BY c.id, c.due_date ASC NULLS LAST
            """
        ),
        params,
    )
    overdue = [_serialize_row(row) for row in overdue_result.mappings().all()]

    due_today_result = await db.execute(
        text(
            f"""
            SELECT DISTINCT ON (c.id)
                c.id,
                c.summary,
                c.direction,
                c.due_date,
                p_target.email_addresses[1] as target_email
            FROM commitments c
            LEFT JOIN persons p_target ON p_target.id = c.target_person_id
            JOIN evidence_links el ON el.commitment_id = c.id
            JOIN normalized_items ni ON ni.id = el.normalized_item_id
            JOIN accounts a ON a.id = ni.account_id
            WHERE a.user_id = :user_id
              AND c.due_date::date = :brief_date
              AND c.status NOT IN ('completed', 'abandoned')
              {extra_condition}
            ORDER BY c.id, c.due_date ASC
            """
        ),
        params,
    )
    due_today = [_serialize_row(row) for row in due_today_result.mappings().all()]

    tomorrow_result = await db.execute(
        text(
            f"""
            SELECT DISTINCT ON (c.id)
                c.id,
                c.summary,
                c.direction,
                c.due_date,
                p_target.email_addresses[1] as target_email
            FROM commitments c
            LEFT JOIN persons p_target ON p_target.id = c.target_person_id
            JOIN evidence_links el ON el.commitment_id = c.id
            JOIN normalized_items ni ON ni.id = el.normalized_item_id
            JOIN accounts a ON a.id = ni.account_id
            WHERE a.user_id = :user_id
              AND c.due_date::date = :tomorrow
              AND c.status NOT IN ('completed', 'abandoned')
              {extra_condition}
            ORDER BY c.id, c.due_date ASC
            """
        ),
        params,
    )
    due_tomorrow = [_serialize_row(row) for row in tomorrow_result.mappings().all()]

    followups_result = await db.execute(
        text(
            f"""
            SELECT DISTINCT ON (c.id)
                c.id,
                c.summary,
                c.direction,
                c.due_date,
                p_owner.email_addresses[1] as owner_email
            FROM commitments c
            JOIN persons p_owner ON p_owner.id = c.owner_person_id
            JOIN evidence_links el ON el.commitment_id = c.id
            JOIN normalized_items ni ON ni.id = el.normalized_item_id
            JOIN accounts a ON a.id = ni.account_id
            WHERE a.user_id = :user_id
              AND c.direction = 'inbound'
              AND c.status NOT IN ('completed', 'abandoned')
              {extra_condition}
            ORDER BY c.id, c.due_date ASC NULLS LAST, c.created_at DESC
            LIMIT 5
            """
        ),
        params,
    )
    important_followups = [_serialize_row(row) for row in followups_result.mappings().all()]

    review_result = await db.execute(
        text(
            f"""
            SELECT
                rq.id,
                rq.reason,
                c.id as commitment_id,
                c.summary,
                n.subject,
                n.sender_email
            FROM review_queue rq
            JOIN commitments c ON c.id = rq.commitment_id
            LEFT JOIN evidence_links el ON el.commitment_id = c.id
            LEFT JOIN normalized_items n ON n.id = el.normalized_item_id
            LEFT JOIN accounts a ON a.id = n.account_id
            WHERE rq.status = 'pending'
              AND a.user_id = :user_id
              {extra_condition}
            ORDER BY rq.created_at DESC
            LIMIT 5
            """
        ),
        params,
    )
    review_items = [_serialize_row(row) for row in review_result.mappings().all()]

    job_updates_result = await db.execute(
        text(
            f"""
            SELECT
                ja.id as job_application_id,
                ja.company_name,
                ja.role_title,
                ja.status,
                ja.summary,
                ja.account_id,
                a.email_address as account_email,
                jae.event_type,
                jae.event_date,
                jae.summary as event_summary
            FROM job_application_events jae
            JOIN job_applications ja ON ja.id = jae.job_application_id
            LEFT JOIN accounts a ON a.id = ja.account_id
            WHERE ja.user_id = :user_id
              AND COALESCE(jae.event_date::date, jae.created_at::date) = :brief_date
              {job_extra_condition}
            ORDER BY COALESCE(jae.event_date, jae.created_at) DESC
            LIMIT 10
            """
        ),
        params,
    )
    job_updates = [_serialize_row(row) for row in job_updates_result.mappings().all()]

    job_actions_result = await db.execute(
        text(
            f"""
            SELECT
                ja.id,
                ja.company_name,
                ja.role_title,
                ja.status,
                ja.summary,
                ja.last_status_at,
                a.email_address as account_email
            FROM job_applications ja
            LEFT JOIN accounts a ON a.id = ja.account_id
            WHERE ja.user_id = :user_id
              AND ja.status IN ('assessment', 'interview')
              {job_extra_condition}
            ORDER BY COALESCE(ja.last_status_at, ja.updated_at, ja.created_at) DESC
            LIMIT 10
            """
        ),
        params,
    )
    job_actions = [_serialize_row(row) for row in job_actions_result.mappings().all()]

    sections: list[dict[str, Any]]
    if brief_type == "morning":
        sections = [
            {"key": "due_today", "title": "Due today", "items": due_today},
            {"key": "overdue", "title": "Overdue carryover", "items": overdue},
            {"key": "followups", "title": "Important follow-ups", "items": important_followups},
            {"key": "job_actions", "title": "Job application actions", "items": job_actions},
        ]
    else:
        sections = [
            {"key": "new_commitments", "title": "New commitments detected today", "items": new_commitments},
            {"key": "completed", "title": "Commitments completed today", "items": completed_today},
            {"key": "overdue", "title": "Overdue items still open", "items": overdue},
            {"key": "review", "title": "Important emails needing attention", "items": review_items},
            {"key": "job_updates", "title": "Job application updates", "items": job_updates},
            {"key": "tomorrow", "title": "Tomorrow's deadlines", "items": due_tomorrow},
        ]

    stats = {
        "new_commitments_count": len(new_commitments),
        "completed_today_count": len(completed_today),
        "overdue_count": len(overdue),
        "due_today_count": len(due_today),
        "due_tomorrow_count": len(due_tomorrow),
        "review_count": len(review_items),
        "job_updates_count": len(job_updates),
        "job_actions_count": len(job_actions),
    }

    headline = (
        f"{brief_type.title()} brief for {brief_date.isoformat()}\n\n"
        f"Open priorities: {len(overdue)} overdue, {len(due_today)} due today, {len(job_actions)} active job actions."
        if brief_type == "morning"
        else f"{brief_type.title()} brief for {brief_date.isoformat()}\n\n"
        f"Today wrapped with {len(new_commitments)} new commitments, {len(completed_today)} completions, and {len(job_updates)} job updates."
    )

    summary_markdown = "\n\n".join(
        [headline] + [_section(section["title"], section["items"]) for section in sections]
    )

    return {
        "brief_type": brief_type,
        "brief_date": brief_date.isoformat(),
        "summary_markdown": summary_markdown,
        "stats": stats,
        "sections": sections,
    }


async def create_daily_brief_run(
    db: AsyncSession,
    *,
    user_id: str,
    brief_type: str,
    brief_date: date,
    account_id: str | None = None,
) -> dict[str, Any]:
    payload = await build_daily_brief_payload(
        db,
        user_id=user_id,
        brief_type=brief_type,
        brief_date=brief_date,
        account_id=account_id,
    )

    result = await db.execute(
        text(
            """
            INSERT INTO daily_brief_runs (
                user_id,
                account_id,
                brief_type,
                brief_date,
                summary_markdown,
                stats_json,
                updated_at
            )
            VALUES (
                :user_id,
                :account_id,
                :brief_type,
                :brief_date,
                :summary_markdown,
                CAST(:stats_json AS JSONB),
                now()
            )
            RETURNING id, user_id, account_id, brief_type, brief_date, summary_markdown, stats_json, created_at, updated_at
            """
        ),
        {
            "user_id": user_id,
            "account_id": account_id,
            "brief_type": brief_type,
            "brief_date": brief_date,
            "summary_markdown": payload["summary_markdown"],
            "stats_json": json.dumps(payload["stats"]),
        },
    )
    run = _serialize_row(result.mappings().one())

    order_index = 0
    for section in payload["sections"]:
        for item in section["items"]:
            order_index += 1
            related_commitment_id = item.get("id") if ("summary" in item and "direction" in item) else item.get("commitment_id")
            related_job_application_id = item.get("job_application_id") or (item.get("id") if item.get("company_name") else None)
            await db.execute(
                text(
                    """
                    INSERT INTO daily_brief_items (
                        brief_run_id,
                        section,
                        title,
                        body,
                        item_kind,
                        order_index,
                        related_commitment_id,
                        related_job_application_id,
                        related_normalized_item_id
                    )
                    VALUES (
                        :brief_run_id,
                        :section,
                        :title,
                        :body,
                        :item_kind,
                        :order_index,
                        :related_commitment_id,
                        :related_job_application_id,
                        :related_normalized_item_id
                    )
                    """
                ),
                {
                    "brief_run_id": run["id"],
                    "section": section["key"],
                    "title": item.get("summary")
                    or item.get("event_summary")
                    or item.get("title")
                    or item.get("company_name")
                    or "Untitled item",
                    "body": item.get("raw_text")
                    or item.get("reason")
                    or item.get("subject")
                    or item.get("role_title"),
                    "item_kind": section["key"],
                    "order_index": order_index,
                    "related_commitment_id": related_commitment_id,
                    "related_job_application_id": related_job_application_id,
                    "related_normalized_item_id": item.get("normalized_item_id"),
                },
            )

    return {
        **run,
        "stats": payload["stats"],
        "sections": payload["sections"],
    }


async def list_daily_brief_runs(
    db: AsyncSession,
    *,
    user_id: str,
    brief_type: str | None = None,
    account_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    conditions = ["user_id = :user_id"]
    params: dict[str, Any] = {"user_id": user_id, "limit": limit}

    if brief_type:
        conditions.append("brief_type = :brief_type")
        params["brief_type"] = brief_type
    if account_id:
        conditions.append("account_id = :account_id")
        params["account_id"] = account_id

    where_clause = "WHERE " + " AND ".join(conditions)
    result = await db.execute(
        text(
            f"""
            SELECT id, user_id, account_id, brief_type, brief_date, summary_markdown, stats_json, created_at, updated_at
            FROM daily_brief_runs
            {where_clause}
            ORDER BY brief_date DESC, created_at DESC
            LIMIT :limit
            """
        ),
        params,
    )
    return [_serialize_row(row) for row in result.mappings().all()]


async def get_daily_brief_run(
    db: AsyncSession,
    *,
    user_id: str,
    brief_run_id: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT id, user_id, account_id, brief_type, brief_date, summary_markdown, stats_json, created_at, updated_at
            FROM daily_brief_runs
            WHERE id = :brief_run_id
              AND user_id = :user_id
            LIMIT 1
            """
        ),
        {"brief_run_id": brief_run_id, "user_id": user_id},
    )
    run = result.mappings().first()
    if not run:
        return None

    item_result = await db.execute(
        text(
            """
            SELECT
                id,
                section,
                title,
                body,
                item_kind,
                order_index,
                related_commitment_id,
                related_job_application_id,
                related_normalized_item_id,
                created_at
            FROM daily_brief_items
            WHERE brief_run_id = :brief_run_id
            ORDER BY order_index ASC, created_at ASC
            """
        ),
        {"brief_run_id": brief_run_id},
    )
    items = [_serialize_row(row) for row in item_result.mappings().all()]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item["section"]].append(item)

    run_data = _serialize_row(run)
    run_data["items"] = items
    run_data["sections"] = dict(grouped)
    run_data["stats"] = run_data.get("stats_json")
    return run_data


async def get_latest_daily_brief_run(
    db: AsyncSession,
    *,
    user_id: str,
    brief_type: str,
    account_id: str | None = None,
) -> dict[str, Any] | None:
    conditions = ["user_id = :user_id", "brief_type = :brief_type"]
    params: dict[str, Any] = {"user_id": user_id, "brief_type": brief_type}
    if account_id:
        conditions.append("account_id = :account_id")
        params["account_id"] = account_id

    where_clause = "WHERE " + " AND ".join(conditions)
    result = await db.execute(
        text(
            f"""
            SELECT id
            FROM daily_brief_runs
            {where_clause}
            ORDER BY brief_date DESC, created_at DESC
            LIMIT 1
            """
        ),
        params,
    )
    row = result.mappings().first()
    if not row:
        return None
    return await get_daily_brief_run(db, user_id=user_id, brief_run_id=str(row["id"]))
