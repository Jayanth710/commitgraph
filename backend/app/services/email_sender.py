from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_token
from app.services.gmail_api import GmailApiError, _refresh_access_token

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
        "SELECT id, email_address, access_token_encrypted, refresh_token_encrypted "
        "FROM accounts "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY created_at ASC LIMIT 1"
    )
    result = await db.execute(text(query), params)
    account = result.mappings().first()
    if not account:
        raise RuntimeError("No Gmail account available for sending delivery email")

    try:
        access_token = decrypt_token(account["access_token_encrypted"])
    except ValueError as exc:
        raise RuntimeError(
            "Stored Gmail credentials could not be decrypted. "
            "Your backend SECRET_KEY does not match the key used when this account was connected. "
            "Use the same SECRET_KEY as the environment that connected the account, or use a separate dev database."
        ) from exc

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

        if response.status_code == 401 and account.get("refresh_token_encrypted"):
            try:
                await _refresh_access_token(db, dict(account))
            except GmailApiError as exc:
                logger.warning(
                    "Failed to refresh Gmail send token for %s: %s",
                    account["email_address"],
                    exc,
                )
            else:
                refreshed_account_result = await db.execute(
                    text(
                        """
                        SELECT id, email_address, access_token_encrypted, refresh_token_encrypted
                        FROM accounts
                        WHERE id = :account_id
                        LIMIT 1
                        """
                    ),
                    {"account_id": account["id"]},
                )
                refreshed_account = refreshed_account_result.mappings().first()
                if refreshed_account:
                    account = refreshed_account
                    try:
                        access_token = decrypt_token(account["access_token_encrypted"])
                    except ValueError as exc:
                        raise RuntimeError(
                            "Stored Gmail credentials could not be decrypted after refresh. "
                            "Your backend SECRET_KEY does not match the key used when this account was connected. "
                            "Use the same SECRET_KEY as the environment that connected the account, or use a separate dev database."
                        ) from exc
                    response = await client.post(
                        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                        headers={"Authorization": f"Bearer {access_token}"},
                        json=gmail_body,
                    )

    if response.is_error:
        logger.error("Gmail send failed for %s: %s", account["email_address"], response.text)
        raise RuntimeError(
            f"Failed to send email via Gmail ({response.status_code}): {response.text}"
        )

    payload = response.json()
    return {
        "message_id": payload.get("id"),
        "thread_id": payload.get("threadId"),
        "account_email": account["email_address"],
    }
