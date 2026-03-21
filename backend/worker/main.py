import argparse
import asyncio
import logging

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.services.gmail_ingest import process_gmail_push_notification
from app.services.outlook_ingest import process_outlook_notification
from app.services.redis_streams import ensure_stream_groups, get_redis_client
from sqlalchemy import text

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
                        provider = fields.get("provider", "gmail")

                        if provider == "gmail":
                            async with AsyncSessionLocal() as session:
                                result = await process_gmail_push_notification(
                                    session,
                                    redis,
                                    email_address=fields["email_address"],
                                    latest_history_id=fields["history_id"],
                                )
                        elif provider == "outlook":
                            async with AsyncSessionLocal() as session:
                                result = await process_outlook_notification(
                                    session,
                                    redis,
                                    message_id=fields["message_id"],
                                    subscription_id=fields.get("subscription_id", ""),
                                )
                        else:
                            logger.warning("Unknown provider: %s", provider)
                            result = {"status": "ignored", "reason": f"unknown_provider:{provider}"}

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
                        "extractor received stream_id=%s fields=%s",
                        message_id,
                        fields,
                    )
                    try:
                        await _process_extraction(fields)

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


async def _process_extraction(fields: dict[str, str]) -> dict:
    """Run the LangGraph extraction pipeline for one normalized item.

    This function:
    1. Reads the normalized_item from Postgres (to get email content)
    2. Reads the account (to get the owner's email for direction detection)
    3. Gets all connected account emails (for is_self detection)
    4. Builds the LangGraph initial state
    5. Invokes the extraction graph

    Args:
        fields: The Redis stream message fields containing
                normalized_item_id, account_id, email_address, etc.

    Returns:
        The final graph state (with stored_commitment_ids, etc.)
    """
    from app.agents.pipeline import extraction_graph

    normalized_item_id = fields["normalized_item_id"]
    account_id = fields["account_id"]
    account_email = fields["email_address"]

    # Fetch the normalized email content from the database.
    async with AsyncSessionLocal() as db:
        ni_result = await db.execute(
            text(
                """
                SELECT subject, body_text, sender_email, sender_name,
                       recipients, sent_at, thread_id
                FROM normalized_items
                WHERE id = :nid
                """
            ),
            {"nid": normalized_item_id},
        )
        ni_row = ni_result.mappings().first()

        if not ni_row:
            logger.warning("Normalized item not found: %s", normalized_item_id)
            return {}

        # Get all connected account emails for is_self detection.
        accounts_result = await db.execute(
            text("SELECT email_address FROM accounts WHERE provider = 'gmail'")
        )
        all_owner_emails = [
            row["email_address"] for row in accounts_result.mappings().all()
        ]

    # Parse recipients from JSONB.
    recipients = ni_row["recipients"] or []
    if isinstance(recipients, str):
        import json
        recipients = json.loads(recipients)

    # Build the initial state for the graph.
    initial_state = {
        "normalized_item_id": normalized_item_id,
        "account_id": account_id,
        "account_owner_email": account_email,
        "account_owner_emails": all_owner_emails,
        "sender_email": ni_row["sender_email"] or "",
        "sender_name": ni_row["sender_name"],
        "recipients": recipients,
        "subject": ni_row["subject"],
        "body_text": ni_row["body_text"],
        "sent_date": (
            ni_row["sent_at"].strftime("%Y-%m-%d") if ni_row["sent_at"] else None
        ),
        "thread_id": ni_row["thread_id"],
    }

    # Run the LangGraph pipeline.
    logger.info(
        "Running extraction pipeline for normalized_item=%s subject=%r",
        normalized_item_id,
        ni_row["subject"],
    )

    final_state = await extraction_graph.ainvoke(initial_state)

    stored = final_state.get("stored_commitment_ids", [])
    reviews = final_state.get("review_items_created", [])
    deduped = final_state.get("deduplicated_count", 0)

    logger.info(
        "Extraction complete for normalized_item=%s: "
        "%d commitments stored, %d sent to review, %d deduplicated",
        normalized_item_id,
        len(stored),
        len(reviews),
        deduped,
    )

    return final_state


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