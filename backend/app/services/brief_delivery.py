from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.daily_briefs import create_daily_brief_run
from app.services.email_sender import send_email_via_gmail
from app.services.sms_sender import send_sms_message


def _brief_subject(brief_type: str, brief_date: date) -> str:
    return f"CommitGraph {brief_type.title()} Brief - {brief_date.isoformat()}"


def _brief_sms_text(summary: str, brief_type: str, brief_date: date) -> str:
    lines = [f"{brief_type.title()} brief {brief_date.isoformat()}"]
    for line in summary.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
        if len("\n".join(lines)) > 420:
            break
    return "\n".join(lines)[:480]


async def get_or_create_delivery_preference(db: AsyncSession, *, user_id: str) -> dict:
    result = await db.execute(
        text(
            """
            SELECT *
            FROM brief_delivery_preferences
            WHERE user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().first()
    if row:
        return dict(row)

    insert_result = await db.execute(
        text(
            """
            INSERT INTO brief_delivery_preferences (
                user_id,
                channel,
                destination,
                timezone,
                morning_enabled,
                morning_time,
                night_enabled,
                night_time,
                is_active
            )
            VALUES (
                :user_id,
                'email',
                (SELECT email FROM users WHERE id = :user_id),
                'America/Denver',
                true,
                '08:00',
                false,
                '20:00',
                true
            )
            RETURNING *
            """
        ),
        {"user_id": user_id},
    )
    return dict(insert_result.mappings().one())


async def update_delivery_preference(
    db: AsyncSession,
    *,
    user_id: str,
    body: dict,
) -> dict:
    current = await get_or_create_delivery_preference(db, user_id=user_id)
    updates = {
        "channel": body.get("channel", current["channel"]),
        "destination": body.get("destination", current["destination"]),
        "timezone": body.get("timezone", current["timezone"]),
        "morning_enabled": body.get("morning_enabled", current["morning_enabled"]),
        "morning_time": body.get("morning_time", current["morning_time"]),
        "night_enabled": body.get("night_enabled", current["night_enabled"]),
        "night_time": body.get("night_time", current["night_time"]),
        "sender_account_id": body.get("sender_account_id", current["sender_account_id"]),
        "account_id": body.get("account_id", current["account_id"]),
        "is_active": body.get("is_active", current["is_active"]),
    }

    result = await db.execute(
        text(
            """
            UPDATE brief_delivery_preferences
            SET channel = :channel,
                destination = :destination,
                timezone = :timezone,
                morning_enabled = :morning_enabled,
                morning_time = :morning_time,
                night_enabled = :night_enabled,
                night_time = :night_time,
                sender_account_id = :sender_account_id,
                account_id = :account_id,
                is_active = :is_active,
                updated_at = now()
            WHERE user_id = :user_id
            RETURNING *
            """
        ),
        {"user_id": user_id, **updates},
    )
    return dict(result.mappings().one())


async def list_delivery_runs(db: AsyncSession, *, user_id: str, limit: int = 20) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT *
            FROM brief_delivery_runs
            WHERE user_id = :user_id
            ORDER BY brief_date DESC, created_at DESC
            LIMIT :limit
            """
        ),
        {"user_id": user_id, "limit": limit},
    )
    return [dict(row) for row in result.mappings().all()]


async def _already_sent(
    db: AsyncSession,
    *,
    user_id: str,
    channel: str,
    brief_type: str,
    brief_date: date,
) -> bool:
    result = await db.execute(
        text(
            """
            SELECT 1
            FROM brief_delivery_runs
            WHERE user_id = :user_id
              AND channel = :channel
              AND brief_type = :brief_type
              AND brief_date = :brief_date
              AND status = 'sent'
            LIMIT 1
            """
        ),
        {
            "user_id": user_id,
            "channel": channel,
            "brief_type": brief_type,
            "brief_date": brief_date,
        },
    )
    return result.scalar() is not None


async def _record_delivery(
    db: AsyncSession,
    *,
    user_id: str,
    preference_id: str | None,
    brief_run_id: str | None,
    channel: str,
    destination: str | None,
    brief_type: str,
    brief_date: date,
    status: str,
    error_message: str | None = None,
) -> None:
    await db.execute(
        text(
            """
            INSERT INTO brief_delivery_runs (
                brief_run_id,
                user_id,
                preference_id,
                channel,
                destination,
                brief_type,
                brief_date,
                status,
                error_message,
                sent_at
            )
            VALUES (
                :brief_run_id,
                :user_id,
                :preference_id,
                :channel,
                :destination,
                :brief_type,
                :brief_date,
                :status,
                :error_message,
                CASE WHEN :status = 'sent' THEN now() ELSE NULL END
            )
            ON CONFLICT (user_id, channel, brief_type, brief_date)
            DO UPDATE SET
                brief_run_id = EXCLUDED.brief_run_id,
                preference_id = EXCLUDED.preference_id,
                destination = EXCLUDED.destination,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                sent_at = CASE WHEN EXCLUDED.status = 'sent' THEN now() ELSE brief_delivery_runs.sent_at END
            """
        ),
        {
            "brief_run_id": brief_run_id,
            "user_id": user_id,
            "preference_id": preference_id,
            "channel": channel,
            "destination": destination,
            "brief_type": brief_type,
            "brief_date": brief_date,
            "status": status,
            "error_message": error_message,
        },
    )


async def run_due_brief_deliveries(db: AsyncSession) -> dict[str, int]:
    now_utc = datetime.now(timezone.utc)
    result = await db.execute(
        text(
            """
            SELECT
                p.*,
                u.email as user_email
            FROM brief_delivery_preferences p
            JOIN users u ON u.id = p.user_id
            WHERE p.is_active = true
            """
        )
    )
    preferences = result.mappings().all()

    sent = 0
    failed = 0
    skipped = 0

    for pref in preferences:
        tz = ZoneInfo(pref["timezone"] or "America/Denver")
        local_now = now_utc.astimezone(tz)
        local_date = local_now.date()
        current_hm = local_now.strftime("%H:%M")
        due_types: list[str] = []

        if pref["morning_enabled"] and str(pref["morning_time"])[:5] == current_hm:
            due_types.append("morning")
        if pref["night_enabled"] and str(pref["night_time"])[:5] == current_hm:
            due_types.append("night")

        if not due_types:
            continue

        destination = pref["destination"] or pref["user_email"]
        if not destination:
            skipped += 1
            continue

        for brief_type in due_types:
            if await _already_sent(
                db,
                user_id=str(pref["user_id"]),
                channel=pref["channel"],
                brief_type=brief_type,
                brief_date=local_date,
            ):
                skipped += 1
                continue

            try:
                brief_run = await create_daily_brief_run(
                    db,
                    user_id=str(pref["user_id"]),
                    brief_type=brief_type,
                    brief_date=local_date,
                    account_id=str(pref["account_id"]) if pref["account_id"] else None,
                )

                if pref["channel"] == "email":
                    await send_email_via_gmail(
                        db,
                        user_id=str(pref["user_id"]),
                        to=destination,
                        subject=_brief_subject(brief_type, local_date),
                        body=brief_run["summary_markdown"],
                        account_id=str(pref["sender_account_id"]) if pref["sender_account_id"] else None,
                    )
                else:
                    await send_sms_message(
                        to=destination,
                        body=_brief_sms_text(brief_run["summary_markdown"], brief_type, local_date),
                    )

                await _record_delivery(
                    db,
                    user_id=str(pref["user_id"]),
                    preference_id=str(pref["id"]),
                    brief_run_id=brief_run["id"],
                    channel=pref["channel"],
                    destination=destination,
                    brief_type=brief_type,
                    brief_date=local_date,
                    status="sent",
                )
                sent += 1
            except Exception as exc:
                await _record_delivery(
                    db,
                    user_id=str(pref["user_id"]),
                    preference_id=str(pref["id"]),
                    brief_run_id=None,
                    channel=pref["channel"],
                    destination=destination,
                    brief_type=brief_type,
                    brief_date=local_date,
                    status="failed",
                    error_message=str(exc),
                )
                failed += 1

    return {"sent": sent, "failed": failed, "skipped": skipped}
