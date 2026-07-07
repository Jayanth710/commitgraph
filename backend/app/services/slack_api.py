"""Minimal Slack Web API helpers."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_USERS_INFO_URL = "https://slack.com/api/users.info"
_CONVERSATIONS_LIST_URL = "https://slack.com/api/conversations.list"
_CONVERSATIONS_JOIN_URL = "https://slack.com/api/conversations.join"

# In-process cache: Slack user id -> display name. Avoids re-calling users.info
# for the same person on every message.
_name_cache: dict[str, str] = {}


async def get_slack_user_name(access_token: str, user_id: str) -> str | None:
    """Resolve a Slack user id (e.g. U0123) to a human display name."""
    if not access_token or not user_id:
        return None
    if user_id in _name_cache:
        return _name_cache[user_id]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _USERS_INFO_URL,
                params={"user": user_id},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        data = resp.json()
    except Exception as exc:
        logger.warning("Slack users.info failed for %s: %s", user_id, exc)
        return None

    if not data.get("ok"):
        logger.warning("Slack users.info not ok for %s: %s", user_id, data.get("error"))
        return None

    user = data.get("user") or {}
    profile = user.get("profile") or {}
    name = (
        profile.get("display_name")
        or profile.get("real_name")
        or user.get("real_name")
        or user.get("name")
    )
    if name:
        _name_cache[user_id] = name
    return name or None


async def join_channel(access_token: str, channel_id: str) -> bool:
    """Join a single public channel. True if joined or already a member."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _CONVERSATIONS_JOIN_URL,
                data={"channel": channel_id},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        data = resp.json()
    except Exception as exc:
        logger.warning("conversations.join error for %s: %s", channel_id, exc)
        return False
    if data.get("ok") or data.get("error") == "already_in_channel":
        return True
    logger.warning("conversations.join %s failed: %s", channel_id, data.get("error"))
    return False


async def _list_public_channel_ids(access_token: str) -> list[str]:
    """List all non-archived public channel ids (paginated)."""
    ids: list[str] = []
    cursor: str | None = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(50):  # safety cap on pages
            params = {
                "types": "public_channel",
                "limit": "200",
                "exclude_archived": "true",
            }
            if cursor:
                params["cursor"] = cursor
            try:
                resp = await client.get(
                    _CONVERSATIONS_LIST_URL,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                data = resp.json()
            except Exception as exc:
                logger.warning("conversations.list failed: %s", exc)
                break
            if not data.get("ok"):
                logger.warning("conversations.list not ok: %s", data.get("error"))
                break
            ids.extend(ch["id"] for ch in data.get("channels", []) if ch.get("id"))
            cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
    return ids


async def join_all_public_channels(access_token: str) -> dict[str, int]:
    """Join every public channel so the bot receives their messages.

    Channels the bot is already in are counted but not re-joined. Best-effort:
    individual failures (e.g. missing channels:join scope) are logged, not raised.
    """
    channel_ids = await _list_public_channel_ids(access_token)
    joined = already_in = failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for channel_id in channel_ids:
            try:
                resp = await client.post(
                    _CONVERSATIONS_JOIN_URL,
                    data={"channel": channel_id},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                data = resp.json()
            except Exception as exc:
                failed += 1
                logger.warning("conversations.join error for %s: %s", channel_id, exc)
                continue
            if data.get("ok"):
                joined += 1
            elif data.get("error") in ("already_in_channel", "is_archived"):
                already_in += 1
            else:
                failed += 1
                logger.warning("conversations.join %s failed: %s", channel_id, data.get("error"))

    result = {
        "joined": joined,
        "already_in": already_in,
        "failed": failed,
        "total": len(channel_ids),
    }
    logger.info("Slack auto-join public channels: %s", result)
    return result
