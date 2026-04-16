from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_token
from app.services.gmail_api import GmailApiError, _refresh_access_token

settings = get_settings()
logger = logging.getLogger(__name__)

WATCH_SCOPES = {
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.metadata",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
}


def _validate_watch_config() -> str:
    if not settings.gcp_project_id:
        raise GmailApiError(
            "Gmail watch is not configured: missing GCP_PROJECT_ID",
            upstream_status_code=400,
            user_message=(
                "Gmail watch is not configured on the server yet. "
                "Set GCP_PROJECT_ID and try again."
            ),
        )

    if not settings.gcp_pubsub_topic:
        raise GmailApiError(
            "Gmail watch is not configured: missing GCP_PUBSUB_TOPIC",
            upstream_status_code=400,
            user_message=(
                "Gmail watch is not configured on the server yet. "
                "Set GCP_PUBSUB_TOPIC and try again."
            ),
        )

    configured_scopes = set(settings.google_oauth_scope.split())
    if configured_scopes and not configured_scopes.intersection(WATCH_SCOPES):
        raise GmailApiError(
            "Gmail watch is not configured: GOOGLE_OAUTH_SCOPE is missing a watch-compatible scope",
            upstream_status_code=400,
            user_message=(
                "Gmail watch requires a Gmail read or modify scope. "
                "Update GOOGLE_OAUTH_SCOPE, reconnect the Gmail account, and try again."
            ),
        )

    return f"projects/{settings.gcp_project_id}/topics/{settings.gcp_pubsub_topic}"


def _extract_google_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or "Unknown Gmail API error"

    error = payload.get("error")
    if not isinstance(error, dict):
        return response.text.strip() or "Unknown Gmail API error"

    message = str(error.get("message") or "").strip()
    errors = error.get("errors")
    if isinstance(errors, list):
        reasons = [
            str(item.get("reason")).strip()
            for item in errors
            if isinstance(item, dict) and item.get("reason")
        ]
        if reasons:
            unique_reasons = ", ".join(dict.fromkeys(reasons))
            if message:
                return f"{message} (reason={unique_reasons})"
            return f"reason={unique_reasons}"

    return message or response.text.strip() or "Unknown Gmail API error"


def _build_user_message(response: httpx.Response, raw_message: str) -> str:
    lowered = raw_message.lower()

    if response.status_code in {400, 403} and any(
        token in lowered for token in ("topic", "pubsub", "publish", "publisher")
    ):
        return (
            "Gmail rejected the Pub/Sub topic. Verify the topic exists, that it uses "
            "the same Google project as the OAuth client, and that "
            "gmail-api-push@system.gserviceaccount.com can publish to it."
        )

    if response.status_code in {401, 403} and any(
        token in lowered
        for token in ("scope", "insufficient", "permission", "unauthorized")
    ):
        return (
            "The connected Gmail account cannot start a watch with its current "
            "authorization. Reconnect the account and approve Gmail access again."
        )

    if response.status_code == 401:
        return "Stored Gmail credentials are no longer valid. Reconnect the Gmail account."

    return raw_message


def _raise_watch_error(response: httpx.Response, account_id: Any) -> None:
    raw_message = _extract_google_error_message(response)
    logger.error(
        "Gmail watch start failed for account=%s status=%s detail=%s",
        account_id,
        response.status_code,
        raw_message,
    )
    raise GmailApiError(
        f"Gmail watch start failed for account={account_id}: {response.status_code} {raw_message}",
        upstream_status_code=response.status_code,
        user_message=_build_user_message(response, raw_message),
    )


async def start_gmail_watch(db: AsyncSession, account: dict[str, Any]) -> dict:
    topic_name = _validate_watch_config()
    access_token = decrypt_token(account["access_token_encrypted"])

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "topicName": topic_name,
        "labelIds": ["INBOX"],
        "labelFilterBehavior": "INCLUDE",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/watch",
            headers=headers,
            json=payload,
        )

        if response.status_code == 401:
            if not account.get("refresh_token_encrypted"):
                logger.warning(
                    "Gmail watch cannot refresh token for account=%s: missing refresh token",
                    account["id"],
                )
                raise GmailApiError(
                    f"Gmail watch refresh failed for account={account['id']}: missing refresh token",
                    upstream_status_code=401,
                    user_message=(
                        "Stored Gmail credentials are incomplete. Reconnect the Gmail "
                        "account and try again."
                    ),
                )

            try:
                await _refresh_access_token(db, account)
            except GmailApiError as exc:
                logger.warning(
                    "Failed to refresh Gmail access token before watch start for account=%s: %s",
                    account["id"],
                    exc,
                )
                raise GmailApiError(
                    str(exc),
                    upstream_status_code=exc.upstream_status_code,
                    user_message=(
                        "Failed to refresh Gmail credentials. Reconnect the Gmail "
                        "account and try again."
                    ),
                ) from exc

            access_token = decrypt_token(account["access_token_encrypted"])
            headers["Authorization"] = f"Bearer {access_token}"
            response = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/watch",
                headers=headers,
                json=payload,
            )

        if response.is_error:
            _raise_watch_error(response, account["id"])

        return response.json()
