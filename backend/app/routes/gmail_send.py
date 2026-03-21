"""
Gmail send endpoint — reply to emails from the CommitGraph dashboard.
"""

from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.core.security import decrypt_token
from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/email", tags=["email-send"])
logger = logging.getLogger(__name__)


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: str | None = None
    in_reply_to: str | None = None
    account_email: str


@router.post("/send")
async def send_email(body: SendEmailRequest, user: dict = Depends(get_current_user)):
    """Send an email via Gmail API on behalf of the user."""
    user_id = str(user["id"])

    # Get the Gmail account.
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT id, access_token_encrypted
                FROM accounts
                WHERE provider = 'gmail' AND email_address = :email AND user_id = :uid
                LIMIT 1
                """
            ),
            {"email": body.account_email, "uid": user_id},
        )
        account = result.mappings().first()

    if not account:
        raise HTTPException(status_code=404, detail="Gmail account not found")

    access_token = decrypt_token(account["access_token_encrypted"])

    # Build the email.
    message = MIMEText(body.body, "plain")
    message["to"] = body.to
    message["subject"] = body.subject

    if body.in_reply_to:
        message["In-Reply-To"] = body.in_reply_to
        message["References"] = body.in_reply_to

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    # Build the Gmail API request.
    gmail_body: dict = {"raw": raw}
    if body.thread_id:
        gmail_body["threadId"] = body.thread_id

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json=gmail_body,
        )

    if response.is_error:
        logger.error("Gmail send failed: %s", response.text)
        raise HTTPException(status_code=response.status_code, detail="Failed to send email")

    result_data = response.json()
    logger.info("Email sent: id=%s threadId=%s", result_data.get("id"), result_data.get("threadId"))

    return {
        "message": "Email sent",
        "message_id": result_data.get("id"),
        "thread_id": result_data.get("threadId"),
    }