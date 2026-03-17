import asyncio
import logging

from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger("commitgraph.scheduler")


async def run_scheduler() -> None:
    logger.info("scheduler started")
    while True:
        logger.info("scheduler heartbeat")
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(run_scheduler())