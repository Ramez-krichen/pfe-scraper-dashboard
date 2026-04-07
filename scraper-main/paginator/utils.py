import random
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from playwright.async_api import Page


def random_sleep(min_sec: float = 1.0, max_sec: float = 3.0) -> None:
    """Sleep for a random duration to mimic human interaction."""
    time.sleep(random.uniform(min_sec, max_sec))


# async def count_products(page: Page, selector: str) -> int:
#     """Count the number of visible products on the current page."""
#     try:
#         # sb.find_elements(selector, timeout=2)
#         return await page.locator(selector).count()
#     except Exception:
#         return 0


def get_next_page_url(base_url: str, param_name: str, next_page_num: int) -> str:
    """Construct the next URL by updating the pagination query parameter."""
    parsed_url = urlparse(base_url)
    query_params = parse_qs(parsed_url.query)
    query_params[param_name] = [str(next_page_num)]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))
