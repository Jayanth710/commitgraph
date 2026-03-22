from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_token

logger = logging.getLogger(__name__)


async def send_email_via_gmail(
    db: AsyncSession,
    *,
    user_id: str,
    to: str,
    subject: str,
    body: str,
    account_email: str | None = None,
    account_id: str | None = None,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
) -> dict[str, Any]:
    clauses = ["provider = 'gmail'", "user_id = :uid"]
    params: dict[str, Any] = {"uid": user_id}

    if account_id:
        clauses.append("id = :account_id")
        params["account_id"] = account_id
    elif account_email:
        clauses.append("email_address = :email")
        params["email"] = account_email

    query = (
        "SELECT id, email_address, access_token_encrypted "
        "FROM accounts "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY created_at ASC LIMIT 1"
    )
    result = await db.execute(text(query), params)
    account = result.mappings().first()
    if not account:
        raise RuntimeError("No Gmail account available for sending delivery email")

    access_token = decrypt_token(account["access_token_encrypted"])

    message = MIMEText(body, "plain")
    message["to"] = to
    message["subject"] = subject
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    gmail_body: dict[str, Any] = {"raw": raw}
    if thread_id:
        gmail_body["threadId"] = thread_id

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json=gmail_body,
        )

    if response.is_error:
        logger.error("Gmail send failed for %s: %s", account["email_address"], response.text)
        raise RuntimeError("Failed to send email via Gmail")

    payload = response.json()
    return {
        "message_id": payload.get("id"),
        "thread_id": payload.get("threadId"),
        "account_email": account["email_address"],
    }
