"""
homepage.py — Extract category and product URLs from a homepage.
"""

from __future__ import annotations
import re
import unicodedata
from typing import Dict, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import (
    CrawlResult,
    DiscoveredUrl,
    DiscoverySource,
)
from product_detection.utils import normalize_url
from .sitemap_parser import classify_url
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

_EXCLUDED_FRAGMENTS = (
    "#",
    "javascript:",
    "mailto:",
    "tel:",
    "login",
    "signup",
    "register",
    "account",
    "cart",
    "checkout",
    "wishlist",
    "compare",
    "privacy",
    "terms",
    "cookie",
    "search",
    # "contact",
    # "help",
    # "faq",
    # "support",
    "tracking",
    "returns",
    "compte",
    "connexion",
    "wish",
    "panier",
)

# _OTHER_PAGE_TEXT_HINTS = (
#     "about",
#     "about us",
#     "a propos",
#     "contact",
#     "event",
#     "events",
#     "evenement",
#     "evenements",
#     "blog",
#     "blogs",
#     "qui sommes",
#     "accueil",
#     "acceuil",
#     "actualit",
#     "promo",
#     "promotion",
#     "promotions",
#     "historique",
# )


def _parse_html(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _is_excluded_href(href: str) -> bool:
    lowered = href.lower()
    return any(fragment in lowered for fragment in _EXCLUDED_FRAGMENTS)


def _same_host(url: str, base_url: str) -> bool:
    if not base_url:
        return True
    try:
        return urlparse(url).netloc == urlparse(base_url).netloc
    except Exception:
        return True


def _anchor_context_hints(tag) -> str:
    attrs = " ".join([tag.get("id") or "", " ".join(tag.get("class") or [])]).lower()
    return attrs


def _normalize_text_for_matching(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def is_base_url(url: str) -> bool:
    reg = re.compile(r"^https?://[www\.]?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}/?$")
    return reg.match(url) is not None


def extract_urls(
    html: str,
    url: str = "",
) -> Dict[str, List[DiscoveredUrl]]:
    """
    Extract category and product URLs from a homepage.
    Returns HomepageUrls with category_urls, product_urls, and other_urls.
    """
    if not html:
        return {
            "product": [],
            "category": [],
            "other": [],
            "blog": [],
            "news": [],
            "about": [],
            "contact": [],
            "event": [],
            "promo": [],
            "auth": [],
            "support": [],
            "rules": [],
        }

    soup = _parse_html(html)

    selectors = [
        "nav a[href]",
        "header a[href]",
        "main a[href]",
        "li a[href]",
    ]

    seen = set()
    results: Dict[str, List[DiscoveredUrl]] = {
        "product": [],
        "category": [],
        "other": [],
        "blog": [],
        "news": [],
        "about": [],
        "contact": [],
        "event": [],
        "promo": [],
        "auth": [],
        "support": [],
        "rules": [],
    }

    for selector in selectors:
        for a in soup.select(selector):
            href = a.get("href")
            if not href:
                continue
            if _is_excluded_href(href):
                continue
            if is_base_url(href):
                continue

            normalized = normalize_url(href, url)
            if not normalized:
                continue
            if not _same_host(normalized, url):
                continue

            if normalized in seen:
                continue
            seen.add(normalized)

            # anchor_text = _normalize_text_for_matching(a.get_text(" ", strip=True) or "")
            # context_hints = _normalize_text_for_matching(_anchor_context_hints(a))

            # if any(term in anchor_text for term in _OTHER_PAGE_TEXT_HINTS) or any(
            #     term in context_hints for term in _OTHER_PAGE_TEXT_HINTS
            # ):
            #     results["category"].append(normalized)
            #     continue

            url_category = classify_url(normalized)
            results[url_category.value].append(DiscoveredUrl(
                url=normalized,
                category=url_category,
                source=DiscoverySource.HOMEPAGE,
            ))

    return results


async def extract_urls_from_page(base_url: str, page: "Page") -> CrawlResult:
    """
    Navigate to the homepage, extract all links, and classify them
    into product / category / other.

    Delegates the heavy lifting to extract_homepage_urls(),
    which already handles anchor extraction and heuristic classification.

    Parameters
    ----------
    base_url : str
        The website's root URL (e.g. "https://egm.tn").
    page : Page
        An active Playwright page instance.

    Returns
    -------
    CrawlResult
        With source = DiscoverySource.HOMEPAGE and the classified URLs.
    """
    result = CrawlResult(base_url=base_url, source=DiscoverySource.HOMEPAGE)

    try:
        logger.info(f"Crawling homepage: {base_url}")
        # sb.open(base_url)
        await page.goto(base_url)
        # html = sb.get_page_source() or ""
        html = await page.content() or ""

        if not html.strip():
            result.error = "Homepage returned empty content."
            return result

        homepage_data = extract_urls(html, base_url)
        result.urls = homepage_data

        logger.info(
            f"found {result} category, "
            f"{len(homepage_data.get('product', []))} product, "
            f"and other URLs."
        )

    except Exception as e:
        logger.error(f"Error crawling homepage {base_url}: {e}")
        result.error = str(e)

    return result
