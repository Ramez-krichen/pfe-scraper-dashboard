"""Example worker-style usage for the shared browser pool."""

from __future__ import annotations

import asyncio
import logging

from playwright.async_api import BrowserContext

from browser_pool import BrowserPool, BrowserPoolConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


async def on_context_created(context: BrowserContext) -> None:
    """Inject lightweight fingerprint hardening into each new context."""

    await context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        """
    )


async def scrape(pool: BrowserPool, url: str) -> str:
    """Scrapes one URL using a pooled page lease."""

    async with pool.get_page() as page:
        await page.goto(url, wait_until="domcontentloaded")
        return await page.content()


async def main() -> None:
    config = BrowserPoolConfig(
        browsers=2,
        contexts_per_browser=4,
        max_pages_per_context=25,
        on_context_created=on_context_created,
        launch_options={"args": ["--disable-dev-shm-usage"]},
    )

    async with BrowserPool(config) as pool:
        urls = [
            "https://example.com",
            "https://httpbin.org/html",
        ]
        results = await asyncio.gather(*(scrape(pool, url) for url in urls))

        for url, html in zip(urls, results, strict=True):
            print(f"{url}: {len(html)} bytes")

        print(pool.snapshot_metrics())


if __name__ == "__main__":
    asyncio.run(main())
