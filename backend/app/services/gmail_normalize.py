from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from html import unescape
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _decode_base64url_to_text(data: str | None) -> str | None:
    if not data:
        return None

    padded = data + ("=" * (-len(data) % 4))
    decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
    return decoded.decode("utf-8", errors="replace")


def _parse_header_date(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        dt = parsedate_to_datetime(value)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_internal_date(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except Exception:
        return None


def _headers_map(message: dict[str, Any]) -> dict[str, str]:
    payload = message.get("payload") or {}
    headers = payload.get("headers") or []

    out: dict[str, str] = {}
    for header in headers:
        name = header.get("name")
        value = header.get("value")
        if name and value:
            out[name.lower()] = value
    return out


def _extract_sender(from_header: str | None) -> tuple[str | None, str | None]:
    name, email = parseaddr(from_header or "")
    clean_name = name.strip() or None
    clean_email = email.strip().lower() or None
    return clean_name, clean_email


def _extract_recipients(headers: dict[str, str]) -> list[dict[str, str | None]]:
    recipients: list[dict[str, str | None]] = []

    for recipient_type, header_name in (
        ("to", "to"),
        ("cc", "cc"),
        ("bcc", "bcc"),
    ):
        raw_value = headers.get(header_name)
        if not raw_value:
            continue

        for name, email in getaddresses([raw_value]):
            clean_email = (email or "").strip().lower()
            if not clean_email:
                continue

            recipients.append(
                {
                    "type": recipient_type,
                    "name": (name or "").strip() or None,
                    "email": clean_email,
                }
            )

    return recipients


def _collect_mime_bodies(
    part: dict[str, Any],
    plain_chunks: list[str],
    html_chunks: list[str],
) -> None:
    mime_type = (part.get("mimeType") or "").lower()
    body = part.get("body") or {}
    data = body.get("data")

    if mime_type.startswith("text/plain"):
        decoded = _decode_base64url_to_text(data)
        if decoded:
            plain_chunks.append(decoded)

    elif mime_type.startswith("text/html"):
        decoded = _decode_base64url_to_text(data)
        if decoded:
            html_chunks.append(decoded)

    for child in part.get("parts") or []:
        _collect_mime_bodies(child, plain_chunks, html_chunks)


def _html_to_text(html: str | None) -> str | None:
    if not html:
        return None

    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip() or None


def _extract_bodies(message: dict[str, Any]) -> tuple[str | None, str | None]:
    payload = message.get("payload") or {}

    plain_chunks: list[str] = []
    html_chunks: list[str] = []

    _collect_mime_bodies(payload, plain_chunks, html_chunks)

    # Single-part emails can have body.data directly on payload.
    if not plain_chunks and not html_chunks:
        mime_type = (payload.get("mimeType") or "").lower()
        body_data = (payload.get("body") or {}).get("data")

        if mime_type.startswith("text/plain"):
            decoded = _decode_base64url_to_text(body_data)
            if decoded:
                plain_chunks.append(decoded)
        elif mime_type.startswith("text/html"):
            decoded = _decode_base64url_to_text(body_data)
            if decoded:
                html_chunks.append(decoded)

    body_text = "\n\n".join(chunk.strip() for chunk in plain_chunks if chunk.strip()) or None
    body_html = "\n".join(chunk for chunk in html_chunks if chunk.strip()) or None

    if not body_text and body_html:
        body_text = _html_to_text(body_html)

    if not body_text:
        snippet = message.get("snippet")
        if snippet:
            body_text = snippet.strip() or None

    return body_text, body_html


async def normalize_gmail_source_item(
    db: AsyncSession,
    *,
    source_item_id: str,
) -> dict[str, Any]:
    existing = await db.execute(
        text(
            """
            SELECT id
            FROM normalized_items
            WHERE source_item_id = :source_item_id
            LIMIT 1
            """
        ),
        {"source_item_id": source_item_id},
    )
    existing_id = existing.scalar_one_or_none()
    if existing_id:
        return {
            "status": "exists",
            "normalized_item_id": str(existing_id),
            "source_item_id": source_item_id,
        }

    result = await db.execute(
        text(
            """
            SELECT id, account_id, provider_data
            FROM source_items
            WHERE id = :source_item_id
              AND provider = 'gmail'
            LIMIT 1
            """
        ),
        {"source_item_id": source_item_id},
    )
    row = result.mappings().first()

    if not row:
        raise ValueError(f"Gmail source_item not found: {source_item_id}")

    message = row["provider_data"]
    if isinstance(message, str):
        message = json.loads(message)

    headers = _headers_map(message)
    sender_name, sender_email = _extract_sender(headers.get("from"))
    recipients = _extract_recipients(headers)
    body_text, body_html = _extract_bodies(message)

    subject = headers.get("subject")
    thread_id = message.get("threadId")
    in_reply_to = headers.get("in-reply-to")

    received_at = _parse_internal_date(message.get("internalDate"))
    sent_at = _parse_header_date(headers.get("date")) or received_at

    insert_result = await db.execute(
        text(
            """
            INSERT INTO normalized_items (
                source_item_id,
                account_id,
                item_type,
                subject,
                body_text,
                body_html,
                sender_email,
                sender_name,
                recipients,
                thread_id,
                in_reply_to,
                sent_at,
                received_at,
                processing_status
            )
            VALUES (
                :source_item_id,
                :account_id,
                'email',
                :subject,
                :body_text,
                :body_html,
                :sender_email,
                :sender_name,
                CAST(:recipients AS JSONB),
                :thread_id,
                :in_reply_to,
                :sent_at,
                :received_at,
                'pending'
            )
            RETURNING id
            """
        ),
        {
            "source_item_id": str(row["id"]),
            "account_id": str(row["account_id"]),
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "recipients": json.dumps(recipients),
            "thread_id": thread_id,
            "in_reply_to": in_reply_to,
            "sent_at": sent_at,
            "received_at": received_at,
        },
    )

    normalized_item_id = insert_result.scalar_one()

    return {
        "status": "created",
        "normalized_item_id": str(normalized_item_id),
        "source_item_id": source_item_id,
        "subject": subject,
        "thread_id": thread_id,
    }


async def backfill_gmail_normalized_items(
    db: AsyncSession,
    *,
    limit: int = 100,
) -> dict[str, int]:
    result = await db.execute(
        text(
            """
            SELECT s.id
            FROM source_items s
            LEFT JOIN normalized_items n
              ON n.source_item_id = s.id
            WHERE s.provider = 'gmail'
              AND n.id IS NULL
            ORDER BY s.fetched_at ASC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )

    source_item_ids = [str(row[0]) for row in result.fetchall()]

    created = 0
    existing = 0

    for source_item_id in source_item_ids:
        normalization_result = await normalize_gmail_source_item(
            db,
            source_item_id=source_item_id,
        )
        if normalization_result["status"] == "created":
            created += 1
        else:
            existing += 1

    return {
        "created": created,
        "existing": existing,
        "scanned": len(source_item_ids),
    }