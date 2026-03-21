"""
Outlook email normalization.

Takes a Microsoft Graph message object and stores it as
source_item + normalized_item, using the same canonical schema as Gmail.

Key differences from Gmail normalization:
    - Body is direct HTML (not base64 encoded)
    - From is {emailAddress: {name, address}} not a header string
    - Recipients are toRecipients/ccRecipients arrays
    - Threading uses conversationId
    - Dates are ISO 8601 strings (not Unix timestamps)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _html_to_text(html: str | None) -> str | None:
    """Strip HTML tags to plain text (same logic as Gmail normalizer)."""
    if not html:
        return None

    text_content = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text_content = re.sub(r"(?i)<br\s*/?>", "\n", text_content)
    text_content = re.sub(r"(?i)</p>", "\n", text_content)
    text_content = re.sub(r"(?is)<[^>]+>", " ", text_content)
    text_content = unescape(text_content)
    text_content = text_content.replace("\r\n", "\n").replace("\r", "\n")
    text_content = re.sub(r"[ \t]+", " ", text_content)
    text_content = re.sub(r"\n{3,}", "\n\n", text_content)
    text_content = re.sub(r" *\n *", "\n", text_content)
    return text_content.strip() or None


def _parse_iso_date(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string from Microsoft Graph."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _extract_sender(message: dict) -> tuple[str | None, str | None]:
    """Extract sender name and email from a Graph message."""
    from_obj = message.get("from", {}).get("emailAddress", {})
    name = (from_obj.get("name") or "").strip() or None
    email = (from_obj.get("address") or "").strip().lower() or None
    return name, email


def _extract_recipients(message: dict) -> list[dict[str, str | None]]:
    """Extract all recipients from a Graph message."""
    recipients = []

    for recipient_type, field_name in [
        ("to", "toRecipients"),
        ("cc", "ccRecipients"),
        ("bcc", "bccRecipients"),
    ]:
        for r in message.get(field_name, []):
            addr = r.get("emailAddress", {})
            email = (addr.get("address") or "").strip().lower()
            if not email:
                continue
            recipients.append({
                "type": recipient_type,
                "name": (addr.get("name") or "").strip() or None,
                "email": email,
            })

    return recipients


def _extract_body(message: dict) -> tuple[str | None, str | None]:
    """Extract body text and HTML from a Graph message."""
    body = message.get("body", {})
    content_type = body.get("contentType", "").lower()
    content = body.get("content", "")

    if content_type == "html":
        body_html = content
        body_text = _html_to_text(content)
    else:
        body_html = None
        body_text = content.strip() if content else None

    return body_text, body_html


async def normalize_outlook_message(
    db: AsyncSession,
    *,
    account_id: str,
    message: dict[str, Any],
) -> dict[str, Any]:
    """Store an Outlook email as source_item + normalized_item.

    Returns dict with status ('created', 'exists', or 'skipped').
    """
    message_id = message.get("id")
    if not message_id:
        return {"status": "skipped", "reason": "no_message_id"}

    idempotency_key = f"outlook:{account_id}:{message_id}"

    # Check if already stored.
    existing = await db.execute(
        text("SELECT id FROM source_items WHERE idempotency_key = :key LIMIT 1"),
        {"key": idempotency_key},
    )
    if existing.scalar_one_or_none():
        return {"status": "exists", "idempotency_key": idempotency_key}

    # Insert source_item.
    source_result = await db.execute(
        text(
            """
            INSERT INTO source_items (account_id, provider, provider_id, provider_data, idempotency_key)
            VALUES (:account_id, 'outlook', :provider_id, CAST(:provider_data AS JSONB), :idempotency_key)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """
        ),
        {
            "account_id": account_id,
            "provider_id": message_id,
            "provider_data": json.dumps(message),
            "idempotency_key": idempotency_key,
        },
    )
    source_item_id = source_result.scalar_one_or_none()
    if not source_item_id:
        return {"status": "exists", "idempotency_key": idempotency_key}

    # Parse message fields.
    sender_name, sender_email = _extract_sender(message)
    recipients = _extract_recipients(message)
    body_text, body_html = _extract_body(message)
    subject = message.get("subject")
    conversation_id = message.get("conversationId")
    received_at = _parse_iso_date(message.get("receivedDateTime"))
    sent_at = _parse_iso_date(message.get("sentDateTime")) or received_at

    # Insert normalized_item.
    ni_result = await db.execute(
        text(
            """
            INSERT INTO normalized_items (
                source_item_id, account_id, item_type,
                subject, body_text, body_html,
                sender_email, sender_name, recipients,
                thread_id, sent_at, received_at,
                processing_status
            )
            VALUES (
                :source_item_id, :account_id, 'email',
                :subject, :body_text, :body_html,
                :sender_email, :sender_name, CAST(:recipients AS JSONB),
                :thread_id, :sent_at, :received_at,
                'pending'
            )
            RETURNING id
            """
        ),
        {
            "source_item_id": str(source_item_id),
            "account_id": account_id,
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "recipients": json.dumps(recipients),
            "thread_id": conversation_id,
            "sent_at": sent_at,
            "received_at": received_at,
        },
    )
    normalized_item_id = str(ni_result.scalar_one())

    logger.info(
        "Normalized Outlook email: %s → %s (%s)",
        message_id[:20],
        normalized_item_id,
        subject,
    )

    return {
        "status": "created",
        "source_item_id": str(source_item_id),
        "normalized_item_id": normalized_item_id,
        "subject": subject,
        "thread_id": conversation_id,
    }