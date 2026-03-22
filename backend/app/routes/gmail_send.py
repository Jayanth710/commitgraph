"""
Gmail send endpoint — reply to emails from the CommitGraph dashboard.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db.session import AsyncSessionLocal
from app.middleware.auth import get_current_user
from app.services.email_sender import send_email_via_gmail

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

    async with AsyncSessionLocal() as db:
        try:
            result_data = await send_email_via_gmail(
                db,
                user_id=user_id,
                to=body.to,
                subject=body.subject,
                body=body.body,
                account_email=body.account_email,
                thread_id=body.thread_id,
                in_reply_to=body.in_reply_to,
            )
        except RuntimeError as exc:
            detail = str(exc)
            status_code = 404 if "No Gmail account" in detail else 500
            raise HTTPException(status_code=status_code, detail=detail) from exc

    logger.info("Email sent: id=%s threadId=%s", result_data.get("message_id"), result_data.get("thread_id"))

    return {
        "message": "Email sent",
        "message_id": result_data.get("message_id"),
        "thread_id": result_data.get("thread_id"),
    }
