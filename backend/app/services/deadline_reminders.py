"""
Deadline reminders.

The scheduler calls run_due_deadline_reminders every cycle. For each user with
deadline reminders enabled, it emails (or texts) a heads-up ~1 day and ~3 hours
before each outbound commitment's due date — earlier than the calendar's
last-minute popup. Reuses the user's brief-delivery channel/destination.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.email_sender import send_email_via_gmail
from app.services.sms_sender import send_sms_message

logger = logging.getLogger(__name__)

# Ordered most-urgent first. A commitment maps to the smallest lead it's under,
# so only one reminder is active at a time (no double-send when catching up).
LEADS: list[tuple[str, int, str]] = [
    ("3_hours", 3, "3 hours"),
    ("1_day", 24, "1 day"),
]
HORIZON_HOURS = max(hrs for _, hrs, _ in LEADS)


def _current_lead(hours_until_due: float) -> tuple[str | None, str | None]:
    for label, hrs, human in LEADS:
        if 0 < hours_until_due <= hrs:
            return label, human
    return None, None


def _short(summary: str, limit: int = 70) -> str:
    summary = (summary or "Commitment").strip()
    return summary if len(summary) <= limit else summary[: limit - 1] + "…"


async def run_due_deadline_reminders(db: AsyncSession) -> dict[str, int]:
    now_utc = datetime.now(timezone.utc)
    horizon = now_utc + timedelta(hours=HORIZON_HOURS)

    prefs = (
        await db.execute(
            text(
                """
                SELECT p.*, u.email AS user_email
                FROM brief_delivery_preferences p
                JOIN users u ON u.id = p.user_id
                WHERE p.is_active = true
                  AND p.deadline_reminders_enabled = true
                """
            )
        )
    ).mappings().all()

    sent = failed = skipped = 0

    for pref in prefs:
        tz = ZoneInfo(pref["timezone"] or "America/Denver")
        destination = pref["destination"] or pref["user_email"]
        if not destination:
            continue

        commitments = (
            await db.execute(
                text(
                    """
                    SELECT DISTINCT ON (c.id) c.id, c.summary, c.due_date
                    FROM commitments c
                    JOIN evidence_links el ON el.commitment_id = c.id
                    JOIN normalized_items ni ON ni.id = el.normalized_item_id
                    JOIN accounts a ON a.id = ni.account_id
                    WHERE a.user_id = :uid
                      AND c.direction = 'outbound'
                      AND c.status NOT IN ('completed', 'abandoned')
                      AND c.due_date IS NOT NULL
                      AND c.due_date > :now
                      AND c.due_date <= :horizon
                    ORDER BY c.id, c.due_date ASC
                    """
                ),
                {"uid": str(pref["user_id"]), "now": now_utc, "horizon": horizon},
            )
        ).mappings().all()

        for c in commitments:
            due = c["due_date"]
            hours_until = (due - now_utc).total_seconds() / 3600
            label, human = _current_lead(hours_until)
            if not label:
                continue

            already = (
                await db.execute(
                    text(
                        """
                        SELECT 1 FROM deadline_reminders
                        WHERE commitment_id = :cid AND lead_label = :lbl AND due_date = :due
                        LIMIT 1
                        """
                    ),
                    {"cid": str(c["id"]), "lbl": label, "due": due},
                )
            ).scalar()
            if already:
                skipped += 1
                continue

            due_local = due.astimezone(tz)
            subject = f'Reminder: "{_short(c["summary"])}" due in {human}'
            body = (
                f"Heads up — this is due in about {human}:\n\n"
                f"{c['summary']}\n\n"
                f"Due: {due_local.strftime('%a %b %d, %Y at %I:%M %p %Z')}\n\n"
                f"— CommitGraph"
            )

            status, err = "sent", None
            try:
                if pref["channel"] == "email":
                    await send_email_via_gmail(
                        db,
                        user_id=str(pref["user_id"]),
                        to=destination,
                        subject=subject,
                        body=body,
                        account_id=str(pref["sender_account_id"])
                        if pref["sender_account_id"]
                        else None,
                    )
                else:
                    await send_sms_message(
                        to=destination,
                        body=f"{subject}\nDue {due_local.strftime('%b %d, %I:%M %p')}",
                    )
                sent += 1
            except Exception as exc:  # noqa: BLE001
                status, err = "failed", str(exc)
                failed += 1

            await db.execute(
                text(
                    """
                    INSERT INTO deadline_reminders (
                        user_id, commitment_id, lead_label, due_date,
                        channel, destination, status, error_message, sent_at
                    )
                    VALUES (
                        :uid, :cid, :lbl, :due,
                        :ch, :dest, :st, :err,
                        CASE WHEN :st = 'sent' THEN now() ELSE NULL END
                    )
                    ON CONFLICT (commitment_id, lead_label, due_date) DO NOTHING
                    """
                ),
                {
                    "uid": str(pref["user_id"]),
                    "cid": str(c["id"]),
                    "lbl": label,
                    "due": due,
                    "ch": pref["channel"],
                    "dest": destination,
                    "st": status,
                    "err": err,
                },
            )

    return {"sent": sent, "failed": failed, "skipped": skipped}
