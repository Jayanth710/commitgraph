import asyncio
import logging
import time

from app.db.session import AsyncSessionLocal
from app.services.brief_delivery import run_due_brief_deliveries
from app.services.deadline_reminders import run_due_deadline_reminders
from app.services.watch_renewal import run_due_watch_renewals
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.observability import init_observability

settings = get_settings()
setup_logging(settings.log_level)
init_observability()
logger = logging.getLogger("commitgraph.scheduler")


async def run_scheduler() -> None:
    logger.info("scheduler started")
    last_renewal_at = 0.0
    while True:
        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    result = await run_due_brief_deliveries(db)
            logger.info("scheduler heartbeat sent=%d failed=%d skipped=%d", result["sent"], result["failed"], result["skipped"])
        except Exception:
            logger.exception("scheduler cycle failed")

        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    reminders = await run_due_deadline_reminders(db)
            if reminders["sent"] or reminders["failed"]:
                logger.info(
                    "deadline reminders sent=%d failed=%d skipped=%d",
                    reminders["sent"], reminders["failed"], reminders["skipped"],
                )
        except Exception:
            logger.exception("deadline reminder cycle failed")

        now = time.monotonic()
        if now - last_renewal_at >= settings.watch_renewal_interval_seconds:
            try:
                renewal = await run_due_watch_renewals()
                if renewal["renewed"] or renewal["failed"]:
                    logger.info(
                        "watch renewal renewed=%d failed=%d skipped=%d",
                        renewal["renewed"], renewal["failed"], renewal["skipped"],
                    )
            except Exception:
                logger.exception("watch renewal cycle failed")
            last_renewal_at = now

        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(run_scheduler())
