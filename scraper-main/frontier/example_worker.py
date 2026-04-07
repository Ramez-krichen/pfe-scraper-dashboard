"""Example worker loop for the distributed URL frontier."""

from __future__ import annotations

import asyncio
import logging
import random

from frontier import FrontierConfig, FrontierWorkerAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def process_url(url: str) -> None:
    """Placeholder for the real scrape implementation."""

    await asyncio.sleep(random.uniform(0.2, 1.0))
    if "fail" in url:
        raise RuntimeError("simulated scrape failure")


async def main() -> None:
    config = FrontierConfig(
        host="localhost",
        port=6379,
        password="12345678",
        db=0,
        default_crawl_delay_seconds=2.0,
        inflight_timeout_seconds=120.0,
        domain_delays={
            "example.com": 3.0,
            "amazon.com": 10.0,
        },
    )

    async with FrontierWorkerAPI(config) as frontier:
        while True:
            scheduled_url = await frontier.get_next_url(wait=False)
            if scheduled_url is None:
                logger.info("No ready URLs. Worker is idle.")
                break

            logger.info(
                "Leased %s from %s with priority=%s retries=%s",
                scheduled_url.url,
                scheduled_url.domain,
                scheduled_url.priority,
                scheduled_url.retries,
            )

            try:
                await process_url(scheduled_url.url)
            except Exception as exc:
                result = await frontier.fail_url(scheduled_url.id, str(exc))
                logger.warning("Marked %s as %s", scheduled_url.id, result)
                continue

            await frontier.complete_url(scheduled_url.id)
            logger.info("Completed %s", scheduled_url.id)


if __name__ == "__main__":
    asyncio.run(main())
