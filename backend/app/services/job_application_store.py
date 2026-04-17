from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(f"{value}T00:00:00+00:00")


async def find_matching_job_application(
    db: AsyncSession,
    *,
    user_id: str,
    thread_id: str | None,
    company_name: str,
    role_title: str | None,
) -> dict[str, Any] | None:
    if thread_id:
        thread_result = await db.execute(
            text(
                """
                SELECT id, company_name, role_title, status
                FROM job_applications
                WHERE user_id = :user_id
                  AND source_thread_id = :thread_id
                  AND deleted_at IS NULL
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id, "thread_id": thread_id},
        )
        row = thread_result.mappings().first()
        if row:
            return dict(row)

    role_clause = ""
    params: dict[str, Any] = {
        "user_id": user_id,
        "company_name": company_name.strip().lower(),
    }
    if role_title:
        role_clause = "AND lower(coalesce(role_title, '')) = :role_title"
        params["role_title"] = role_title.strip().lower()

    result = await db.execute(
        text(
            f"""
            SELECT id, company_name, role_title, status
            FROM job_applications
            WHERE user_id = :user_id
              AND deleted_at IS NULL
              AND lower(company_name) = :company_name
              {role_clause}
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        params,
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def find_deleted_job_application(
    db: AsyncSession,
    *,
    user_id: str,
    thread_id: str | None,
    company_name: str,
    role_title: str | None,
) -> dict[str, Any] | None:
    if thread_id:
        thread_result = await db.execute(
            text(
                """
                SELECT id, company_name, role_title, status
                FROM job_applications
                WHERE user_id = :user_id
                  AND source_thread_id = :thread_id
                  AND deleted_at IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id, "thread_id": thread_id},
        )
        row = thread_result.mappings().first()
        if row:
            return dict(row)

    role_clause = ""
    params: dict[str, Any] = {
        "user_id": user_id,
        "company_name": company_name.strip().lower(),
    }
    if role_title:
        role_clause = "AND lower(coalesce(role_title, '')) = :role_title"
        params["role_title"] = role_title.strip().lower()

    result = await db.execute(
        text(
            f"""
            SELECT id, company_name, role_title, status
            FROM job_applications
            WHERE user_id = :user_id
              AND deleted_at IS NOT NULL
              AND lower(company_name) = :company_name
              {role_clause}
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        params,
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def upsert_job_application(
    db: AsyncSession,
    *,
    user_id: str,
    account_id: str,
    normalized_item_id: str,
    thread_id: str | None,
    company_name: str,
    role_title: str | None,
    status: str,
    summary: str,
    raw_text: str | None,
    date_applied: str | None,
    event_date: str | None,
    confidence_score: float,
) -> dict[str, Any]:
    existing = await find_matching_job_application(
        db,
        user_id=user_id,
        thread_id=thread_id,
        company_name=company_name,
        role_title=role_title,
    )

    if not existing:
        deleted_match = await find_deleted_job_application(
            db,
            user_id=user_id,
            thread_id=thread_id,
            company_name=company_name,
            role_title=role_title,
        )
        if deleted_match:
            return {"status": "skipped_deleted", "id": deleted_match["id"]}

    last_status_at = _parse_dt(event_date) or _parse_dt(date_applied) or datetime.now(timezone.utc)

    if existing:
        result = await db.execute(
            text(
                """
                UPDATE job_applications
                SET account_id = :account_id,
                    status = :status,
                    summary = :summary,
                    raw_text = :raw_text,
                    role_title = COALESCE(:role_title, role_title),
                    date_applied = COALESCE(:date_applied, date_applied),
                    last_status_at = :last_status_at,
                    source_normalized_item_id = :normalized_item_id,
                    source_thread_id = COALESCE(:thread_id, source_thread_id),
                    confidence_score = GREATEST(confidence_score, :confidence_score),
                    updated_at = now()
                WHERE id = :id
                RETURNING id, company_name, role_title, status
                """
            ),
            {
                "id": existing["id"],
                "account_id": account_id,
                "status": status,
                "summary": summary,
                "raw_text": raw_text,
                "role_title": role_title,
                "date_applied": _parse_dt(date_applied),
                "last_status_at": last_status_at,
                "normalized_item_id": normalized_item_id,
                "thread_id": thread_id,
                "confidence_score": confidence_score,
            },
        )
        application = dict(result.mappings().one())
        event_type = "status_change" if existing.get("status") != status else "note"
    else:
        result = await db.execute(
            text(
                """
                INSERT INTO job_applications (
                    user_id,
                    account_id,
                    company_name,
                    role_title,
                    status,
                    summary,
                    raw_text,
                    date_applied,
                    last_status_at,
                    source_normalized_item_id,
                    source_thread_id,
                    confidence_score
                )
                VALUES (
                    :user_id,
                    :account_id,
                    :company_name,
                    :role_title,
                    :status,
                    :summary,
                    :raw_text,
                    :date_applied,
                    :last_status_at,
                    :normalized_item_id,
                    :thread_id,
                    :confidence_score
                )
                RETURNING id, company_name, role_title, status
                """
            ),
            {
                "user_id": user_id,
                "account_id": account_id,
                "company_name": company_name.strip(),
                "role_title": role_title.strip() if role_title else None,
                "status": status,
                "summary": summary,
                "raw_text": raw_text,
                "date_applied": _parse_dt(date_applied),
                "last_status_at": last_status_at,
                "normalized_item_id": normalized_item_id,
                "thread_id": thread_id,
                "confidence_score": confidence_score,
            },
        )
        application = dict(result.mappings().one())
        event_type = "detected"

    await db.execute(
        text(
            """
            INSERT INTO job_application_events (
                job_application_id,
                normalized_item_id,
                event_type,
                status,
                event_date,
                summary,
                raw_text
            )
            VALUES (
                :job_application_id,
                :normalized_item_id,
                :event_type,
                :status,
                :event_date,
                :summary,
                :raw_text
            )
            ON CONFLICT (job_application_id, normalized_item_id, event_type, summary)
            DO NOTHING
            """
        ),
        {
            "job_application_id": application["id"],
            "normalized_item_id": normalized_item_id,
            "event_type": event_type,
            "status": status,
            "event_date": last_status_at,
            "summary": summary,
            "raw_text": raw_text,
        },
    )

    return application
