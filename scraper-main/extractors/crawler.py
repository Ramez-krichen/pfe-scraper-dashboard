"""
crawler.py — Main orchestrator for URL discovery.

Pipeline:
    1. Fetch robots.txt → extract Sitemap: directives
    2. If sitemaps found → fetch & parse them → classify URLs
    3. If no robots.txt or no sitemaps → fallback to homepage crawl
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import CrawlResult, DiscoverySource
from .robots_parser import fetch_robots_txt, parse_sitemap_directives, parse_disallowed_paths
from .sitemap_parser import fetch_and_parse_all_sitemaps, classify_sitemap_entries
from .homepage import extract_urls_from_page

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def discover_urls(
    base_url: str,
    page: "Page",
    *,
    max_sitemaps: int = 20,
) -> CrawlResult:
    """
    Discover product/category URLs from a website.

    Strategy:
        1. Try robots.txt → extract Sitemap: directives
        2. Fetch & parse sitemaps → classify URLs
        3. If (1) or (2) fails → crawl the homepage as fallback

    Parameters
    ----------
    base_url : str
        Root URL of the website (e.g. "https://egm.tn").
    page : Page
        An active Playwright page instance.
    max_sitemaps : int
        Maximum number of sitemap files to process (prevents runaway crawls).

    Returns
    -------
    CrawlResult
        Contains classified URLs and metadata about the discovery process.
    """
    base_url = base_url.rstrip("/")
    result = CrawlResult(base_url=base_url)
    sitemap_urls = []

    # ------------------------------------------------------------------
    # Step 1: Fetch and parse robots.txt
    # ------------------------------------------------------------------
    robots_text = fetch_robots_txt(base_url)

    if not robots_text:
        logger.info("No robots.txt found. trying sitemap.xml")
    else:
        logger.info("robots.txt found — extracting sitemap directives.")

        # Extract disallowed paths for reference
        result.disallowed_paths = parse_disallowed_paths(robots_text)

        # Extract sitemap URLs
        sitemap_urls = parse_sitemap_directives(robots_text)

        if not sitemap_urls:
            logger.info("robots.txt has no Sitemap directives. trying sitemap.xml")


    # Add sitemap.xml if not found
    default_sitemap = base_url + "/sitemap.xml"

    if default_sitemap not in sitemap_urls:
        sitemap_urls.append(default_sitemap)
        result.sitemap_urls_found = sitemap_urls

    # ----------------------------------------------------------
    # Step 2: Fetch and parse sitemaps
    # ----------------------------------------------------------
    logger.info(f"Found {len(sitemap_urls)} sitemap(s) — fetching.")
    entries = fetch_and_parse_all_sitemaps(
        sitemap_urls, max_sitemaps=max_sitemaps
    )

    if entries:
        classified = classify_sitemap_entries(entries)
        result.urls = classified
        result.source = DiscoverySource.SITEMAP
        return result
    else:
        logger.warning("Sitemaps were found but contained no URL entries.")

    # ------------------------------------------------------------------
    # Step 3: Fallback — crawl the homepage
    # ------------------------------------------------------------------
    logger.info("Falling back to homepage crawl for URL discovery.")
    homepage_result = await extract_urls_from_page(base_url, page)

    # Merge homepage results into our result object
    result.urls = homepage_result.urls
    result.source = DiscoverySource.HOMEPAGE
    result.error = homepage_result.error

    return result
