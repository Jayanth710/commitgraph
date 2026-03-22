import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.services.brief_delivery import run_due_brief_deliveries
from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger("commitgraph.scheduler")


async def run_scheduler() -> None:
    logger.info("scheduler started")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    result = await run_due_brief_deliveries(db)
            logger.info("scheduler heartbeat sent=%d failed=%d skipped=%d", result["sent"], result["failed"], result["skipped"])
        except Exception:
            logger.exception("scheduler cycle failed")
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(run_scheduler())
