"""
Redis Streams service.

Uses standard redis library locally, Upstash REST client in production.
Provides a unified interface for both.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Detect which client to use based on environment.
USE_UPSTASH_REST = bool(settings.upstash_redis_rest_url and settings.upstash_redis_rest_token)


if USE_UPSTASH_REST:
    from upstash_redis import Redis as UpstashSync
    from upstash_redis.asyncio import Redis as UpstashAsync

    _upstash_sync = UpstashSync(
        url=settings.upstash_redis_rest_url,
        token=settings.upstash_redis_rest_token,
    )
    _upstash_async = UpstashAsync(
        url=settings.upstash_redis_rest_url,
        token=settings.upstash_redis_rest_token,
    )
else:
    from redis.asyncio import Redis


class UpstashRedisAdapter:
    """Wraps Upstash REST client to provide the same interface as redis.asyncio.Redis.
    
    Only implements the methods our codebase actually uses.
    """

    def __init__(self):
        self._client = _upstash_async

    async def ping(self) -> bool:
        result = await self._client.ping()
        return result == "PONG" or result is True

    async def xadd(self, stream: str, fields: dict, id: str = "*", **kwargs) -> str:
        """Add an entry to a stream."""
        result = await self._client.xadd(stream, id, fields)
        return result or ""

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str] | None = None,
        count: int | None = None,
        block: int | None = None,
        **kwargs,
    ) -> list:
        """Read from a consumer group."""
        if not streams:
            return []

        stream_keys = list(streams.keys())
        stream_ids = list(streams.values())

        try:
            result = await self._client.xreadgroup(
                groupname,
                consumername,
                {k: v for k, v in zip(stream_keys, stream_ids)},
                count=count,
                block=block,
            )
        except Exception as exc:
            # Upstash returns error if group doesn't exist or stream is empty.
            logger.debug("xreadgroup returned: %s", exc)
            return []

        if not result:
            return []

        # Convert Upstash format to redis-py format.
        # Upstash returns: [[stream_name, [[id, {fields}], ...]]]
        # redis-py returns: [(stream_name, [(id, {fields}), ...])]
        formatted = []
        for stream_data in result:
            if isinstance(stream_data, (list, tuple)) and len(stream_data) >= 2:
                stream_name = stream_data[0]
                messages = []
                for msg in stream_data[1]:
                    if isinstance(msg, (list, tuple)) and len(msg) >= 2:
                        messages.append((msg[0], msg[1] if isinstance(msg[1], dict) else {}))
                formatted.append((stream_name, messages))
        return formatted

    async def xack(self, stream: str, group: str, *ids: str) -> int:
        """Acknowledge messages in a consumer group."""
        result = await self._client.xack(stream, group, *ids)
        return result or 0

    async def xgroup_create(self, name: str, groupname: str, id: str = "0", mkstream: bool = False) -> bool:
        """Create a consumer group."""
        try:
            await self._client.xgroup_create(name, groupname, id, mkstream=mkstream)
            return True
        except Exception as exc:
            if "BUSYGROUP" in str(exc):
                return True  # Group already exists.
            raise

    async def execute_command(self, *args, **kwargs):
        """Execute a raw Redis command via REST."""
        return await self._client.execute(list(args))

    async def set(self, key: str, value: str, **kwargs) -> bool:
        result = await self._client.set(key, value)
        return bool(result)

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def eval(self, script: str, numkeys: int, *keys_and_args) -> Any:
        """Execute a Lua script."""
        keys = list(keys_and_args[:numkeys])
        args = list(keys_and_args[numkeys:])
        return await self._client.eval(script, keys, args)

    async def aclose(self):
        """No-op for REST client — no persistent connection."""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def get_redis_client():
    """Get a Redis client — Upstash REST in production, standard redis locally."""
    if USE_UPSTASH_REST:
        return UpstashRedisAdapter()
    else:
        return Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )


async def check_redis_health() -> bool:
    """Health check for Redis."""
    if USE_UPSTASH_REST:
        try:
            result = _upstash_sync.ping()
            logger.info("Upstash REST ping result: %s (type: %s)", result, type(result))
            return True
        except Exception as exc:
            logger.error("Upstash REST ping failed: %s", exc)
            raise
    else:
        try:
            client = get_redis_client()
            result = await client.ping()
            await client.aclose()
            logger.info("Redis TCP ping result: %s", result)
            return result
        except Exception as exc:
            logger.error("Redis TCP ping failed: %s", exc)
            raise


async def ensure_stream_groups(redis=None) -> None:
    """Create consumer groups if they don't exist.

    Accepts an optional existing client (the workers pass theirs); only closes
    the client if this function created it.
    """
    client = redis or get_redis_client()
    owns_client = redis is None
    try:
        for stream, group in [
            (settings.stream_ingest_raw, settings.stream_normalizer_group),
            (settings.stream_process_normalized, settings.stream_extractor_group),
        ]:
            try:
                await client.xgroup_create(stream, group, id="0", mkstream=True)
                logger.info("Created consumer group %s on stream %s", group, stream)
            except Exception as exc:
                if "BUSYGROUP" in str(exc):
                    logger.info("Consumer group %s already exists on %s", group, stream)
                else:
                    raise
    finally:
        if owns_client:
            await client.aclose()


async def publish_ingest_raw_event(
    redis_client,
    *,
    provider: str,
    email_address: str,
    history_id: str,
) -> dict[str, Any]:
    """Publish an event to the ingest:raw stream."""
    fields = {
        "provider": provider,
        "email_address": email_address,
        "history_id": history_id,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    }
    stream_id = await redis_client.xadd(settings.stream_ingest_raw, fields)
    return {"stream_id": stream_id, "fields": fields}


async def publish_normalized_event_once(
    redis_client,
    *,
    normalized_item_id: str,
    source_item_id: str,
    account_id: str,
    email_address: str,
    provider_id: str,
    thread_id: str | None = None,
) -> dict[str, str]:
    """Publish to process:normalized with dedup via Lua script."""
    dedup_key = f"dedup:normalized:{normalized_item_id}"

    lua_script = """
    if redis.call('EXISTS', KEYS[1]) == 0 then
        redis.call('SET', KEYS[1], '1', 'EX', 86400)
        redis.call('XADD', KEYS[2], '*',
            'normalized_item_id', ARGV[1],
            'source_item_id', ARGV[2],
            'account_id', ARGV[3],
            'email_address', ARGV[4],
            'provider_id', ARGV[5],
            'thread_id', ARGV[6],
            'enqueued_at', ARGV[7]
        )
        return 1
    end
    return 0
    """

    try:
        result = await redis_client.eval(
            lua_script,
            2,
            dedup_key,
            settings.stream_process_normalized,
            normalized_item_id,
            source_item_id,
            account_id,
            email_address,
            provider_id,
            thread_id or "",
            datetime.now(timezone.utc).isoformat(),
        )

        if result == 1:
            return {"status": "published", "normalized_item_id": normalized_item_id}
        else:
            return {"status": "duplicate", "normalized_item_id": normalized_item_id}
    except Exception as exc:
        # Fallback: just XADD without dedup.
        logger.warning("Lua dedup failed, falling back to plain XADD: %s", exc)
        await redis_client.xadd(
            settings.stream_process_normalized,
            {
                "normalized_item_id": normalized_item_id,
                "source_item_id": source_item_id,
                "account_id": account_id,
                "email_address": email_address,
                "provider_id": provider_id,
                "thread_id": thread_id or "",
                "enqueued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"status": "published_no_dedup", "normalized_item_id": normalized_item_id}