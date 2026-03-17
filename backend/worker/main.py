import argparse
import asyncio
import logging

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.services.gmail_ingest import process_gmail_push_notification
from app.services.redis_streams import ensure_stream_groups, get_redis_client

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger("commitgraph.worker")


def _has_messages(entries) -> bool:
    if not entries:
        return False

    for _stream, messages in entries:
        if messages:
            return True
    return False


async def _read_pending(redis, *, stream_name: str, group_name: str, consumer_name: str):
    return await redis.xreadgroup(
        groupname=group_name,
        consumername=consumer_name,
        streams={stream_name: "0"},
        count=settings.stream_read_count,
    )


async def _read_new(redis, *, stream_name: str, group_name: str, consumer_name: str):
    return await redis.xreadgroup(
        groupname=group_name,
        consumername=consumer_name,
        streams={stream_name: ">"},
        count=settings.stream_read_count,
        block=settings.stream_block_ms,
    )


async def run_normalizer_worker() -> None:
    redis = get_redis_client()
    await ensure_stream_groups(redis)

    stream_name = settings.stream_ingest_raw
    group_name = settings.stream_normalizer_group
    consumer_name = settings.stream_normalizer_consumer

    logger.info(
        "normalizer worker started stream=%s group=%s consumer=%s",
        stream_name,
        group_name,
        consumer_name,
    )

    try:
        while True:
            entries = await _read_pending(
                redis,
                stream_name=stream_name,
                group_name=group_name,
                consumer_name=consumer_name,
            )

            if not _has_messages(entries):
                entries = await _read_new(
                    redis,
                    stream_name=stream_name,
                    group_name=group_name,
                    consumer_name=consumer_name,
                )

            if not _has_messages(entries):
                continue

            for _stream, messages in entries:
                for message_id, fields in messages:
                    logger.info(
                        "normalizer received stream_id=%s fields=%s",
                        message_id,
                        fields,
                    )
                    try:
                        async with AsyncSessionLocal() as session:
                            result = await process_gmail_push_notification(
                                session,
                                redis,
                                email_address=fields["email_address"],
                                latest_history_id=fields["history_id"],
                            )

                        if settings.stream_debug_crash_before_ack:
                            raise RuntimeError("Intentional crash before XACK")

                        await redis.xack(stream_name, group_name, message_id)
                        logger.info(
                            "normalizer acked stream_id=%s result=%s",
                            message_id,
                            result,
                        )
                    except Exception:
                        logger.exception(
                            "normalizer failed stream_id=%s; leaving unacked",
                            message_id,
                        )
                        if settings.stream_debug_crash_before_ack:
                            raise
    finally:
        await redis.aclose()


async def run_extractor_worker() -> None:
    redis = get_redis_client()
    await ensure_stream_groups(redis)

    stream_name = settings.stream_process_normalized
    group_name = settings.stream_extractor_group
    consumer_name = settings.stream_extractor_consumer

    logger.info(
        "extractor worker started stream=%s group=%s consumer=%s",
        stream_name,
        group_name,
        consumer_name,
    )

    try:
        while True:
            entries = await _read_pending(
                redis,
                stream_name=stream_name,
                group_name=group_name,
                consumer_name=consumer_name,
            )

            if not _has_messages(entries):
                entries = await _read_new(
                    redis,
                    stream_name=stream_name,
                    group_name=group_name,
                    consumer_name=consumer_name,
                )

            if not _has_messages(entries):
                continue

            for _stream, messages in entries:
                for message_id, fields in messages:
                    logger.info(
                        "extractor stub received stream_id=%s fields=%s",
                        message_id,
                        fields,
                    )
                    try:
                        await asyncio.sleep(0)

                        if settings.stream_debug_crash_before_ack:
                            raise RuntimeError("Intentional crash before XACK")

                        await redis.xack(stream_name, group_name, message_id)
                        logger.info("extractor acked stream_id=%s", message_id)
                    except Exception:
                        logger.exception(
                            "extractor failed stream_id=%s; leaving unacked",
                            message_id,
                        )
                        if settings.stream_debug_crash_before_ack:
                            raise
    finally:
        await redis.aclose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("worker", choices=["normalizer", "extractor"])
    args = parser.parse_args()

    if args.worker == "normalizer":
        asyncio.run(run_normalizer_worker())
    else:
        asyncio.run(run_extractor_worker())


if __name__ == "__main__":
    main()