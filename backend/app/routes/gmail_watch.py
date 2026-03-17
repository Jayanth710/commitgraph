from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.security import decrypt_token
from app.db.session import AsyncSessionLocal
from app.services.gmail_watch import start_gmail_watch

router = APIRouter(prefix="/gmail/watch", tags=["gmail-watch"])


@router.post("/start")
async def gmail_watch_start(email_address: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                SELECT id, access_token_encrypted
                FROM accounts
                WHERE provider = 'gmail' AND email_address = :email_address
                LIMIT 1
                """
            ),
            {"email_address": email_address},
        )
        row = result.first()

        if not row:
            raise HTTPException(status_code=404, detail="Gmail account not found")

        account_id = row[0]
        access_token_encrypted = row[1]

        if not access_token_encrypted:
            raise HTTPException(status_code=400, detail="No access token stored")

        try:
            access_token = decrypt_token(access_token_encrypted)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="Stored Gmail access token could not be decrypted",
            ) from exc

        watch_data = await start_gmail_watch(access_token)

        history_id = watch_data.get("historyId")
        expiration_ms = watch_data.get("expiration")

        watch_expiry = None
        if expiration_ms:
            watch_expiry = datetime.fromtimestamp(
                int(expiration_ms) / 1000,
                tz=timezone.utc,
            )

        await session.execute(
            text(
                """
                UPDATE accounts
                SET history_id = :history_id,
                    watch_expiry = :watch_expiry,
                    last_sync_at = NOW(),
                    sync_status = 'active'
                WHERE id = :account_id
                """
            ),
            {
                "history_id": history_id,
                "watch_expiry": watch_expiry,
                "account_id": account_id,
            },
        )
        await session.commit()

    return {
        "message": "Gmail watch started",
        "email_address": email_address,
        "history_id": history_id,
        "watch_expiry": watch_expiry.isoformat() if watch_expiry else None,
    }