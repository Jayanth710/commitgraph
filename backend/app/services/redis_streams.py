from __future__ import annotations

from datetime import datetime, timezone

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.core.config import get_settings

settings = get_settings()


def get_redis_client() -> Redis:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        health_check_interval=30,
    )


async def ensure_stream_groups(redis: Redis) -> None:
    groups = [
        (settings.stream_ingest_raw, settings.stream_normalizer_group),
        (settings.stream_process_normalized, settings.stream_extractor_group),
    ]

    for stream_name, group_name in groups:
        try:
            await redis.xgroup_create(
                name=stream_name,
                groupname=group_name,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise


async def publish_ingest_raw_event(
    redis: Redis,
    *,
    email_address: str,
    history_id: str,
) -> str:
    return await redis.xadd(
        settings.stream_ingest_raw,
        {
            "provider": "gmail",
            "email_address": email_address,
            "history_id": str(history_id),
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        },
    )


async def publish_normalized_event_once(
    redis: Redis,
    *,
    normalized_item_id: str,
    source_item_id: str,
    account_id: str,
    email_address: str,
    provider_id: str,
    thread_id: str | None,
) -> dict[str, str]:
    """
    Atomically:
      - check whether this normalized_item_id was already emitted
      - if not, XADD to process:normalized and remember the stream entry id
      - if yes, return the original stream entry id

    This prevents duplicate downstream events when Worker 1 replays.
    """

    dedupe_key = f"dedupe:{settings.stream_process_normalized}:{normalized_item_id}"
    enqueued_at = datetime.now(timezone.utc).isoformat()

    lua = """
    local dedupe_key = KEYS[1]
    local stream_key = KEYS[2]

    local existing_id = redis.call('GET', dedupe_key)
    if existing_id then
        return {'existing', existing_id}
    end

    local stream_id = redis.call(
        'XADD', stream_key, '*',
        'provider', ARGV[1],
        'normalized_item_id', ARGV[2],
        'source_item_id', ARGV[3],
        'account_id', ARGV[4],
        'email_address', ARGV[5],
        'provider_id', ARGV[6],
        'thread_id', ARGV[7],
        'enqueued_at', ARGV[8]
    )

    redis.call('SET', dedupe_key, stream_id)
    return {'created', stream_id}
    """

    result = await redis.eval(
        lua,
        2,
        dedupe_key,
        settings.stream_process_normalized,
        "gmail",
        normalized_item_id,
        source_item_id,
        account_id,
        email_address,
        provider_id,
        thread_id or "",
        enqueued_at,
    )

    return {
        "status": result[0],
        "stream_id": result[1],
    }