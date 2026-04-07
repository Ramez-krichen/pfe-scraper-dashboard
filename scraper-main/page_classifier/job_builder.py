from __future__ import annotations


from typing import Any, Dict


from bs4 import BeautifulSoup

from .classifier import classify_page

from .models import PageType, ScrapeJob


def classify_page_from_html(
    html: str,
    url: str,
    *,
    extra_metadata: Dict[str, Any] | None = None,
) -> ScrapeJob:
    """

    Analyze HTML and return a scraper job object with a job_type aligned

    to the detected page type.


    Accepts raw HTML. Browser-driven callers should extract the HTML first,

    for example via Playwright `page.content()`.
    """

    soup = BeautifulSoup(html, "lxml")

    classification = classify_page(soup, url)

    page_type = classification.page_type

    if page_type == PageType.PRODUCT_LIST and classification.pagination.has_pagination:
        page_type = PageType.PRODUCT_LIST_PAGINATED

    metadata = {
        "page_type": page_type,
        "pagination": classification.pagination.to_dict(),
        "signals": classification.signals,
        "notes": classification.notes,
    }

    if extra_metadata:
        metadata.update(extra_metadata)

    return ScrapeJob(url=url, page_type=page_type, metadata=metadata)
