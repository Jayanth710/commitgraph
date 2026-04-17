from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api", tags=["job-applications"])


def _serialize_row(row) -> dict[str, Any]:
    data = dict(row)
    for key, value in data.items():
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
        elif isinstance(value, bytes):
            data[key] = None
    return data


@router.get("/job-applications")
async def list_job_applications(
    user: dict = Depends(get_current_user),
    status: str | None = Query(default=None),
    q: str = Query(default="", min_length=0),
    account_id: str | None = Query(default=None),
):
    user_id = str(user["id"])
    conditions = ["ja.user_id = :user_id"]
    params: dict[str, Any] = {"user_id": user_id}

    if status:
        conditions.append("ja.status = :status")
        params["status"] = status
    if q:
        conditions.append(
            "(ja.company_name ILIKE :q OR COALESCE(ja.role_title, '') ILIKE :q OR ja.summary ILIKE :q)"
        )
        params["q"] = f"%{q}%"
    if account_id:
        conditions.append("ja.account_id = :account_id")
        params["account_id"] = account_id

    where_clause = "WHERE " + " AND ".join(conditions)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                f"""
                SELECT
                    ja.id,
                    ja.company_name,
                    ja.role_title,
                    ja.status,
                    ja.summary,
                    ja.raw_text,
                    ja.date_applied,
                    ja.last_status_at,
                    ja.confidence_score,
                    ja.created_at,
                    ja.updated_at,
                    ja.source_thread_id,
                    ja.account_id,
                    a.email_address as account_email
                FROM job_applications ja
                LEFT JOIN accounts a ON a.id = ja.account_id
                {where_clause}
                ORDER BY
                    CASE ja.status
                        WHEN 'interview' THEN 0
                        WHEN 'offer' THEN 1
                        WHEN 'assessment' THEN 2
                        WHEN 'applied' THEN 3
                        WHEN 'rejected' THEN 4
                        ELSE 5
                    END,
                    COALESCE(ja.last_status_at, ja.updated_at, ja.created_at) DESC
                """
            ),
            params,
        )
        rows = result.mappings().all()

    return {"job_applications": [_serialize_row(row) for row in rows], "total": len(rows)}


@router.get("/job-applications/{job_application_id}")
async def get_job_application(
    job_application_id: str,
    user: dict = Depends(get_current_user),
):
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        app_result = await db.execute(
            text(
                """
                SELECT
                    ja.id,
                    ja.company_name,
                    ja.role_title,
                    ja.status,
                    ja.summary,
                    ja.raw_text,
                    ja.date_applied,
                    ja.last_status_at,
                    ja.confidence_score,
                    ja.created_at,
                    ja.updated_at,
                    ja.source_thread_id,
                    ja.account_id,
                    a.email_address as account_email
                FROM job_applications ja
                LEFT JOIN accounts a ON a.id = ja.account_id
                WHERE ja.id = :job_application_id
                  AND ja.user_id = :user_id
                LIMIT 1
                """
            ),
            {"job_application_id": job_application_id, "user_id": user_id},
        )
        application = app_result.mappings().first()
        if not application:
            raise HTTPException(status_code=404, detail="Job application not found")

        event_result = await db.execute(
            text(
                """
                SELECT
                    jae.id,
                    jae.event_type,
                    jae.status,
                    jae.event_date,
                    jae.summary,
                    jae.raw_text,
                    jae.created_at,
                    n.subject,
                    n.sender_email
                FROM job_application_events jae
                LEFT JOIN normalized_items n ON n.id = jae.normalized_item_id
                WHERE jae.job_application_id = :job_application_id
                ORDER BY COALESCE(jae.event_date, jae.created_at) DESC
                """
            ),
            {"job_application_id": job_application_id},
        )
        events = event_result.mappings().all()

    return {
        "job_application": _serialize_row(application),
        "events": [_serialize_row(event) for event in events],
    }


@router.patch("/job-applications/{job_application_id}")
async def update_job_application(
    job_application_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
):
    user_id = str(user["id"])
    allowed_statuses = {"applied", "assessment", "interview", "rejected", "offer", "withdrawn", "closed"}
    status = body.get("status")

    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {sorted(allowed_statuses)}")

    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                text(
                    """
                    UPDATE job_applications
                    SET status = :status,
                        last_status_at = now(),
                        updated_at = now()
                    WHERE id = :job_application_id
                      AND user_id = :user_id
                    RETURNING
                        id,
                        company_name,
                        role_title,
                        status,
                        summary,
                        raw_text,
                        date_applied,
                        last_status_at,
                        confidence_score,
                        updated_at,
                        account_id
                    """
                ),
                {
                    "job_application_id": job_application_id,
                    "user_id": user_id,
                    "status": status,
                },
            )
            row = result.mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Job application not found")

            await db.execute(
                text(
                    """
                    INSERT INTO job_application_events (
                        job_application_id,
                        event_type,
                        status,
                        event_date,
                        summary
                    )
                    VALUES (
                        :job_application_id,
                        'status_change',
                        :status,
                        now(),
                        :summary
                    )
                    """
                ),
                {
                    "job_application_id": job_application_id,
                    "status": status,
                    "summary": f"Status updated to {status}",
                },
            )

    return {"job_application": _serialize_row(row)}


@router.delete("/job-applications/{job_application_id}")
async def delete_job_application(
    job_application_id: str,
    user: dict = Depends(get_current_user),
):
    user_id = str(user["id"])

    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                text(
                    """
                    DELETE FROM job_applications
                    WHERE id = :job_application_id
                      AND user_id = :user_id
                    RETURNING id, company_name, role_title
                    """
                ),
                {
                    "job_application_id": job_application_id,
                    "user_id": user_id,
                },
            )
            row = result.mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Job application not found")

    return {
        "deleted": True,
        "job_application": _serialize_row(row),
    }
