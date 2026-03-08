import time

import httpx
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from ..constants import EXIT_FATAL, EXIT_OK
from ..db.stores import upsert_stores
from ..stores import fetch_stores


async def scrape_stores() -> int:
    """Fetch and upsert the full SAQ store directory. Returns exit code."""
    start = time.monotonic()

    async with httpx.AsyncClient(
        headers={"User-Agent": settings.USER_AGENT}, timeout=settings.REQUEST_TIMEOUT
    ) as client:
        try:
            stores = await fetch_stores(client)
            await upsert_stores(stores)
        except (httpx.HTTPError, SQLAlchemyError, ValueError, KeyError) as exc:
            logger.opt(exception=exc).error("Store scrape failed")
            return EXIT_FATAL

    elapsed = time.monotonic() - start
    minutes, seconds = divmod(int(elapsed), 60)
    logger.info(
        "Store scrape complete in {}m {}s — {} stores loaded", minutes, seconds, len(stores)
    )
    return EXIT_OK
