import logging
from typing import Literal, NotRequired, TypedDict
from urllib.parse import urlparse, parse_qs

from playwright.async_api import Page

from .constants import (
    LOAD_MORE_SELECTORS,
    LOAD_MORE_TEXTS,
    NEXT_BUTTON_SELECTORS,
    PAGINATION_NAV_SELECTORS,
    PRODUCT_HEURISTICS,
    URL_PARAM_CANDIDATES,
)

logger = logging.getLogger(__name__)


class PaginationTypeInfo(TypedDict):
    type: Literal["url", "load_more", "next_button", "infinite_scroll"]
    pattern: NotRequired[str | None]
    selector: NotRequired[str | None]


async def detect_product_container(page: Page) -> str:
    """
    Identify repeating product blocks.
    Returns the CSS selector used for counting products.
    """
    best_selector = None
    max_count = 0

    for selector in PRODUCT_HEURISTICS:
        try:
            # sb.find_elements(selector, timeout=2)
            count = await page.locator(selector).count()
            if count > max_count and count > 2:
                max_count = count
                best_selector = selector
        except Exception:
            pass

    if not best_selector:
        logger.warning(
            "Could not reliably detect product container. Falling back to a generic 'div' counter, which may be inaccurate."
        )
        best_selector = "div"

    logger.info(
        f"Detected product container selector: '{best_selector}' (count: {max_count})"
    )
    return best_selector


async def detect_pagination_type(page: Page) -> PaginationTypeInfo:
    """
    Detect the type of pagination present on the current page.
    Returns a dictionary with type, pattern, and selector.
    """
    logger.info("Detecting pagination type...")

    for selector in LOAD_MORE_SELECTORS:
        try:
            # sb.is_element_visible(selector)
            locator = page.locator(selector)
            if await locator.count() > 0 and locator.first.is_visible():
                logger.info(f"Detected Load More button via selector: {selector}")
                return {"type": "load_more", "pattern": None, "selector": selector}
        except Exception:
            pass

    try:
        # sb.find_elements("button, a")
        elements = await page.locator("button, a").all()
        for el in elements:
            text = (await el.text_content() or "").lower()
            if (
                any(keyword in text for keyword in LOAD_MORE_TEXTS)
                and el.is_visible()
            ):
                cls = await el.get_attribute("class")
                if cls:
                    first_class = cls.split()[0]
                    # el.tag_name
                    tag_name = el.evaluate("element => element.tagName.toLowerCase()")
                    selector = f"{tag_name}.{first_class}"
                    # sb.is_element_visible(selector)
                    locator = page.locator(selector)
                    if await locator.count() > 0 and locator.first.is_visible():
                        logger.info(
                            f"Detected Load More button via text heuristic: {selector}"
                        )
                        return {
                            "type": "load_more",
                            "pattern": None,
                            "selector": selector,
                        }
    except Exception as e:
        logger.debug(f"Error checking load more text: {e}")

    # sb.get_current_url()
    current_url = page.url
    parsed_url = urlparse(current_url)
    query_params = parse_qs(parsed_url.query)

    for param in URL_PARAM_CANDIDATES:
        if param in query_params:
            logger.info(f"Detected URL pagination in current URL via param: {param}")
            return {"type": "url", "pattern": param, "selector": None}

    for nav_selector in PAGINATION_NAV_SELECTORS:
        try:
            # sb.find_elements(nav_selector, timeout=2)
            links = await page.locator(nav_selector).all()
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    parsed_href = urlparse(href)
                    href_params = parse_qs(parsed_href.query)
                    for param in URL_PARAM_CANDIDATES:
                        if param in href_params:
                            logger.info(
                                f"Detected URL pagination via anchor tag ({nav_selector}), param: {param}"
                            )
                            return {"type": "url", "pattern": param, "selector": None}
        except Exception:
            pass

    for selector in NEXT_BUTTON_SELECTORS:
        try:
            # sb.is_element_visible(selector)
            locator = page.locator(selector)
            if await locator.count() > 0 and locator.first.is_visible():
                logger.info(f"Detected Next button via selector: {selector}")
                return {"type": "next_button", "pattern": None, "selector": selector}
        except Exception:
            pass

    logger.info("No explicit pagination controls found. Defaulting to Infinite Scroll.")
    return {"type": "infinite_scroll", "pattern": None, "selector": None}
