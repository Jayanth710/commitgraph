from __future__ import annotations

import json
import logging
from typing import Any

from app.services.inline_processor import process_normalized_item_inline
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings

from app.services.gmail_api import (
    GmailApiError,
    GmailHistoryExpiredError,
    get_full_message,
    list_new_message_ids,
)
from app.services.gmail_normalize import normalize_gmail_source_item
# from app.services.redis_streams import publish_normalized_event
from app.services.redis_streams import publish_normalized_event_once

settings = get_settings()
logger = logging.getLogger(__name__)


def build_idempotency_key(account_id: str, message_id: str) -> str:
    return f"gmail:{account_id}:{message_id}"


async def process_gmail_push_notification(
    db: AsyncSession,
    redis=None,
    *,
    email_address: str,
    latest_history_id: str,
) -> dict[str, Any]:
    pending_publications: list[dict[str, str]] = []
    normalized_ids = []  # Collect for post-commit extraction

    try:
        async with db.begin():
            account = await _lock_gmail_account_by_email(db, email_address)

            if account is None:
                logger.warning("No Gmail account found for email=%s", email_address)
                return {
                    "status": "ignored",
                    "reason": "account_not_found",
                    "inserted": 0, "skipped": 0, "normalized": 0, "emitted": 0,
                }

            previous_history_id = (
                str(account["history_id"]) if account["history_id"] is not None else None
            )

            if previous_history_id is None:
                await _update_account_history_id(
                    db, account_id=str(account["id"]), history_id=latest_history_id,
                )
                logger.info(
                    "Bootstrapped Gmail history cursor for account_id=%s history_id=%s",
                    account["id"], latest_history_id,
                )
                return {
                    "status": "bootstrapped",
                    "inserted": 0, "skipped": 0, "normalized": 0, "emitted": 0,
                    "history_id": latest_history_id,
                }

            message_ids = await list_new_message_ids(db, account, previous_history_id)

            inserted = 0
            skipped = 0
            normalized = 0
            emitted = 0

            for message_id in message_ids:
                idempotency_key = build_idempotency_key(str(account["id"]), message_id)
                source_already_exists = False
                should_reextract = True

                existing_source = await _get_source_item_by_idempotency(
                    db, idempotency_key=idempotency_key,
                )

                if existing_source:
                    source_already_exists = True
                    skipped += 1
                    source_item_id = str(existing_source["id"])
                    provider_id = str(existing_source["provider_id"])
                else:
                    try:
                        full_message = await get_full_message(db, account, message_id)
                    except GmailApiError as exc:
                        if "404" in str(exc) or "NOT_FOUND" in str(exc):
                            logger.warning("Message %s not found (deleted/spam?), skipping", message_id)
                            skipped += 1
                            continue
                        raise

                    source_item_id = await _insert_source_item(
                        db,
                        account_id=str(account["id"]),
                        provider_id=message_id,
                        provider_data=full_message,
                        idempotency_key=idempotency_key,
                    )

                    if source_item_id is None:
                        fallback_source = await _get_source_item_by_idempotency(
                            db, idempotency_key=idempotency_key,
                        )
                        if fallback_source is None:
                            raise RuntimeError(f"source_item insert lost for message_id={message_id}")
                        source_already_exists = True
                        skipped += 1
                        source_item_id = str(fallback_source["id"])
                        provider_id = str(fallback_source["provider_id"])
                    else:
                        inserted += 1
                        provider_id = message_id

                normalization_result = await normalize_gmail_source_item(
                    db, source_item_id=source_item_id,
                )
                if normalization_result["status"] == "created":
                    normalized += 1

                normalized_item = await _get_normalized_item_by_source_item_id(
                    db, source_item_id=source_item_id,
                )
                if normalized_item is None:
                    raise RuntimeError(f"normalized_item missing for source_item_id={source_item_id}")

                if source_already_exists and normalized_item.get("processing_status") == "processed":
                    should_reextract = False

                pending_publications.append(
                    {
                        "normalized_item_id": str(normalized_item["id"]),
                        "source_item_id": source_item_id,
                        "account_id": str(account["id"]),
                        "email_address": email_address,
                        "provider_id": provider_id,
                        "thread_id": normalized_item["thread_id"] or "",
                    }
                )

                # Collect for post-commit extraction
                if should_reextract:
                    normalized_ids.append((str(normalized_item["id"]), str(account["id"])))
                else:
                    logger.info(
                        "Skipping re-extraction for already-processed normalized_item=%s provider_id=%s",
                        normalized_item["id"],
                        provider_id,
                    )

            await _update_account_history_id(
                db, account_id=str(account["id"]), history_id=latest_history_id,
            )

        # --- Transaction is now COMMITTED ---

        logger.info(
            "Processed Gmail notification email=%s account_id=%s prev_history_id=%s "
            "new_history_id=%s inserted=%s skipped=%s normalized=%s emitted=%s",
            email_address, account["id"], previous_history_id, latest_history_id,
            inserted, skipped, normalized, emitted,
        )

        if settings.app_env != "production" and redis is not None:
            for publication in pending_publications:
                emit_result = await publish_normalized_event_once(
                    redis,
                    normalized_item_id=publication["normalized_item_id"],
                    source_item_id=publication["source_item_id"],
                    account_id=publication["account_id"],
                    email_address=publication["email_address"],
                    provider_id=publication["provider_id"],
                    thread_id=publication["thread_id"],
                )

                if emit_result["status"] in {"published", "published_no_dedup"}:
                    emitted += 1
                else:
                    logger.info(
                        "Skipped duplicate process:normalized emission "
                        "normalized_item_id=%s status=%s",
                        publication["normalized_item_id"],
                        emit_result.get("status", "unknown"),
                    )

        # Run inline extraction AFTER commit so data is visible
        if settings.app_env == "production" and normalized_ids:
            for nid, aid in normalized_ids:
                try:
                    extraction_result = await process_normalized_item_inline(
                        normalized_item_id=nid, account_id=aid,
                    )
                    logger.info("Inline extraction: %s", extraction_result)
                except Exception:
                    logger.exception("Inline extraction failed for %s", nid)

        return {
            "status": "processed",
            "account_id": str(account["id"]),
            "email_address": email_address,
            "previous_history_id": previous_history_id,
            "latest_history_id": latest_history_id,
            "message_ids": message_ids,
            "inserted": inserted,
            "skipped": skipped,
            "normalized": normalized,
            "emitted": emitted,
        }

    except GmailHistoryExpiredError:
        logger.exception(
            "Gmail history cursor expired for email=%s; full sync required",
            email_address,
        )
        raise

async def _lock_gmail_account_by_email(
    db: AsyncSession,
    email_address: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT
                id,
                email_address,
                provider,
                history_id,
                access_token_encrypted,
                refresh_token_encrypted
            FROM accounts
            WHERE provider = 'gmail'
              AND email_address = :email_address
            FOR UPDATE
            """
        ),
        {"email_address": email_address},
    )

    row = result.mappings().first()
    return dict(row) if row else None


async def _get_source_item_by_idempotency(
    db: AsyncSession,
    *,
    idempotency_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT id, account_id, provider_id
            FROM source_items
            WHERE idempotency_key = :idempotency_key
            LIMIT 1
            """
        ),
        {"idempotency_key": idempotency_key},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _get_normalized_item_by_source_item_id(
    db: AsyncSession,
    *,
    source_item_id: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT id, thread_id, processing_status
            FROM normalized_items
            WHERE source_item_id = :source_item_id
            LIMIT 1
            """
        ),
        {"source_item_id": source_item_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _insert_source_item(
    db: AsyncSession,
    *,
    account_id: str,
    provider_id: str,
    provider_data: dict[str, Any],
    idempotency_key: str,
) -> str | None:
    result = await db.execute(
        text(
            """
            INSERT INTO source_items (
                account_id,
                provider,
                provider_id,
                provider_data,
                idempotency_key
            )
            VALUES (
                :account_id,
                'gmail',
                :provider_id,
                CAST(:provider_data AS JSONB),
                :idempotency_key
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """
        ),
        {
            "account_id": account_id,
            "provider_id": provider_id,
            "provider_data": json.dumps(provider_data),
            "idempotency_key": idempotency_key,
        },
    )

    inserted_id = result.scalar_one_or_none()
    return str(inserted_id) if inserted_id else None


async def _update_account_history_id(db, *, account_id, history_id):
    await db.execute(
        text("""
            UPDATE accounts SET history_id = :hid, last_sync_at = now()
            WHERE id = :aid
        """),
        {"hid": str(history_id), "aid": account_id},
    )
