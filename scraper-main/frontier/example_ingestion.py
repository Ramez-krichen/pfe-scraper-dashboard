"""Example URL ingestion script for the distributed frontier."""

from __future__ import annotations

import asyncio
import logging

from frontier import FrontierConfig, FrontierManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = FrontierConfig(
        host="localhost",
        port=6379,
        password="12345678",
        db=0,
        domain_delays={
            "example.com": 3.0,
            "httpbin.org": 1.5,
        },
    )

    urls = [
        ("https://example.com/", 1),
        ("https://example.com/docs", 3),
        ("https://httpbin.org/html", 5),
        ("https://httpbin.org/anything?x=1&y=2", 2),
        ("https://example.com/", 1),
    ]

    async with FrontierManager(config) as frontier:
        for url, priority in urls:
            url_id = await frontier.add_url(url, priority=priority)
            if url_id is None:
                logger.info("Skipped duplicate %s", url)
            else:
                logger.info("Enqueued %s as %s", url, url_id)


if __name__ == "__main__":
    asyncio.run(main())
