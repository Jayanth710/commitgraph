"""
Entity resolution: map email addresses to person records.

This module resolves raw email addresses into persons table entries.
It handles:
    - Exact email match → link to existing person
    - Gmail dot normalization (j.doe@gmail.com = jdoe@gmail.com)
    - Plus-tag stripping (user+tag@gmail.com = user@gmail.com)
    - Detection of the user's own accounts (is_self=true)
    - Creating new person records for unknown emails

No LLM is used here — this is purely deterministic logic.

Why entity resolution matters:
    If Sarah emails you from sarah@work.com and sarah.chen@gmail.com,
    those should be the SAME person in the persons table. Without
    entity resolution, you'd have two "Sarah" entries and commitments
    from each would look unrelated.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Email normalization
# ---------------------------------------------------------------------------
def normalize_email(email: str) -> str:
    """Lowercase and strip whitespace."""
    return email.strip().lower()


def normalize_gmail_dots(email: str) -> str:
    """Remove dots from the local part of Gmail addresses.

    Gmail ignores dots: j.doe@gmail.com == jdoe@gmail.com == j.d.o.e@gmail.com
    This only applies to @gmail.com — not to Google Workspace or other providers.
    """
    local, domain = email.split("@", 1)
    if domain == "gmail.com":
        local = local.replace(".", "")
    return f"{local}@{domain}"


def strip_plus_tag(email: str) -> str:
    """Remove plus-tag aliases: user+tag@gmail.com → user@gmail.com.

    Most email providers support this. The part after + is ignored for delivery.
    """
    local, domain = email.split("@", 1)
    local = re.sub(r"\+.*$", "", local)
    return f"{local}@{domain}"


def canonical_email(email: str) -> str:
    """Apply all normalization rules to get the canonical form of an email.

    This is used for matching — two emails with the same canonical form
    belong to the same person.
    """
    normalized = normalize_email(email)
    # Non-email identifiers (e.g. Slack/Discord user ids like "slack:U123") have
    # no "@" — skip the email-specific normalization and match on them as-is.
    if "@" not in normalized:
        return normalized
    normalized = strip_plus_tag(normalized)
    normalized = normalize_gmail_dots(normalized)
    return normalized


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------
async def find_person_by_email(
    db: AsyncSession,
    email: str,
) -> dict[str, Any] | None:
    """Look up a person by any of their known email addresses.

    The persons table stores email_addresses as a TEXT[] array.
    The GIN index on this column makes array containment checks fast.
    """
    result = await db.execute(
        text(
            """
            SELECT id, display_name, email_addresses, is_self
            FROM persons
            WHERE :email = ANY(email_addresses)
            LIMIT 1
            """
        ),
        {"email": email},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def find_person_by_canonical_email(
    db: AsyncSession,
    email: str,
) -> dict[str, Any] | None:
    """Try to find a person using canonical (normalized) email matching.

    If exact match fails, we try canonical forms to catch:
    - Gmail dot variants (j.doe@gmail.com vs jdoe@gmail.com)
    - Plus-tag variants (user+tag@gmail.com vs user@gmail.com)

    This scans all persons and normalizes their stored emails.
    For a single-user app with hundreds of persons, this is fine.
    A production multi-user system would store canonical_email as a column.
    """
    canon = canonical_email(email)

    result = await db.execute(
        text("SELECT id, display_name, email_addresses, is_self FROM persons")
    )
    rows = result.mappings().all()

    for row in rows:
        for stored_email in row["email_addresses"]:
            if canonical_email(stored_email) == canon:
                return dict(row)

    return None


async def create_person(
    db: AsyncSession,
    *,
    email: str,
    display_name: str | None = None,
    is_self: bool = False,
) -> dict[str, Any]:
    """Create a new person record with a single email address."""
    result = await db.execute(
        text(
            """
            INSERT INTO persons (display_name, email_addresses, is_self)
            VALUES (:display_name, ARRAY[:email]::TEXT[], :is_self)
            RETURNING id, display_name, email_addresses, is_self
            """
        ),
        {
            "display_name": display_name,
            "email": email,
            "is_self": is_self,
        },
    )
    return dict(result.mappings().one())


async def add_email_to_person(
    db: AsyncSession,
    *,
    person_id: str,
    email: str,
) -> None:
    """Add a new email alias to an existing person record.

    Uses array_append + check to avoid adding duplicates.
    """
    await db.execute(
        text(
            """
            UPDATE persons
            SET email_addresses = array_append(email_addresses, :email),
                last_seen_at = now()
            WHERE id = :person_id
              AND NOT (:email = ANY(email_addresses))
            """
        ),
        {"person_id": person_id, "email": email},
    )


async def update_person_last_seen(
    db: AsyncSession,
    person_id: str,
) -> None:
    """Touch the last_seen_at timestamp."""
    await db.execute(
        text("UPDATE persons SET last_seen_at = now() WHERE id = :person_id"),
        {"person_id": person_id},
    )


async def _backfill_display_name(
    db: AsyncSession,
    person: dict[str, Any],
    display_name: str | None,
) -> None:
    """Set a person's display name if we now have one and they had none."""
    if display_name and not person.get("display_name"):
        await db.execute(
            text("UPDATE persons SET display_name = :name WHERE id = :pid"),
            {"name": display_name, "pid": person["id"]},
        )
        person["display_name"] = display_name


# ---------------------------------------------------------------------------
# Main resolution function
# ---------------------------------------------------------------------------
async def resolve_person(
    db: AsyncSession,
    *,
    email: str,
    display_name: str | None = None,
    account_owner_emails: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve an email address to a person record.

    Resolution order:
    1. Exact match in persons.email_addresses → return existing person
    2. Canonical match (dot/plus normalization) → return existing person + add alias
    3. No match → create new person

    If the email belongs to one of the user's own connected accounts,
    the person is created/updated with is_self=True.

    Args:
        db: Database session (must be inside a transaction).
        email: The email address to resolve.
        display_name: Optional name for new person records.
        account_owner_emails: List of the user's own email addresses
            (from connected accounts). Used to detect is_self.

    Returns:
        Person dict with id, display_name, email_addresses, is_self.
    """
    email = normalize_email(email)
    owner_emails = {normalize_email(e) for e in (account_owner_emails or [])}
    is_self = email in owner_emails

    # Step 1: Exact match.
    person = await find_person_by_email(db, email)
    if person:
        await update_person_last_seen(db, person["id"])
        await _backfill_display_name(db, person, display_name)

        # If this person is the account owner but wasn't flagged yet, fix it.
        if is_self and not person["is_self"]:
            await db.execute(
                text("UPDATE persons SET is_self = true WHERE id = :pid"),
                {"pid": person["id"]},
            )
            person["is_self"] = True

        logger.debug("Resolved %s → existing person %s (exact)", email, person["id"])
        return person

    # Step 2: Canonical match (catches gmail dots, plus-tags).
    person = await find_person_by_canonical_email(db, email)
    if person:
        # Same person, different email variant → add this email as alias.
        await add_email_to_person(db, person_id=str(person["id"]), email=email)
        await update_person_last_seen(db, person["id"])
        await _backfill_display_name(db, person, display_name)

        if is_self and not person["is_self"]:
            await db.execute(
                text("UPDATE persons SET is_self = true WHERE id = :pid"),
                {"pid": person["id"]},
            )
            person["is_self"] = True

        logger.info(
            "Resolved %s → existing person %s (canonical match, added alias)",
            email,
            person["id"],
        )
        return person

    # Step 3: Truly new person.
    person = await create_person(
        db,
        email=email,
        display_name=display_name,
        is_self=is_self,
    )
    logger.info("Created new person %s for email %s (is_self=%s)", person["id"], email, is_self)
    return person
