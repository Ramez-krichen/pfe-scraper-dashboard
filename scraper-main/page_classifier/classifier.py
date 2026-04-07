from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from product_detection.models import ScoringConfig


from .models import PageClassification, PageType

from .pagination import detect_pagination

from .signals import (
    count_add_to_cart_signals,
    count_article_candidates,
    count_nav_links,
    count_price_matches,
    count_product_like_links,
    count_time_markers,
    has_filter_controls,
    has_related_section,
    has_schema_product,
    has_search_input,
    url_has_blog_hint,
    url_has_category_hint,
    url_has_product_detail_hint,
    url_has_product_hint,
    url_is_homepage,
)


logger = logging.getLogger(__name__)


def _parse_html(html: str) -> BeautifulSoup:

    try:
        return BeautifulSoup(html, "lxml")

    except Exception:
        return BeautifulSoup(html, "html.parser")


def _score_product_detail(
    *,
    schema_product: bool,
    add_to_cart_count: int,
    price_match_count: int,
    url_product_hint: bool,
    product_like_links: int,
) -> float:

    score = 0.0

    if schema_product:
        score += 0.5

    if add_to_cart_count > 0:
        score += 0.1

    if price_match_count > 0:
        score += 0.05

    if url_product_hint:
        score += 0.4

    if product_like_links <= 3:
        score += 0.05

    return min(score, 1.0)


def _score_content_list(
    *, article_count: int, time_markers: int, blog_hint: bool, product_like_links: int
) -> float:

    score = 0.0

    if article_count >= 3:
        score += 0.4

    if time_markers >= 3:
        score += 0.2

    if blog_hint:
        score += 0.2

    if product_like_links <= 2:
        score += 0.1

    return min(score, 1.0)


def _score_homepage(*, url: str, nav_links: int, has_search: bool) -> float:

    score = 0.0

    path = "/"

    try:
        from urllib.parse import urlparse

        path = urlparse(url).path or "/"

    except Exception:
        path = "/"

    if path in ("/", "") or path.lower().endswith(("/index.html", "/index.htm")):
        score += 0.6

    if nav_links >= 8:
        score += 0.2

    if has_search:
        score += 0.1

    return min(score, 1.0)


def classify_page(
    soup: BeautifulSoup, url: str, *, config: ScoringConfig | None = None
) -> PageClassification:
    """

    Classify a page based on HTML content.


    Returns a PageClassification with the page type, confidence, pagination hints,

    and extracted signals to help downstream routing decisions.

    """

    if not soup:
        return PageClassification(page_type=PageType.UNKNOWN)

    config = config or ScoringConfig()

    pagination = detect_pagination(soup)

    page_text = soup.get_text(" ", strip=True)

    schema_product = has_schema_product(soup)

    add_to_cart_count = count_add_to_cart_signals(soup, config)

    price_match_count = count_price_matches(page_text, config)

    url_product_hint = url_has_product_hint(url, config)

    url_detail_hint = url_has_product_detail_hint(url, config)

    url_category_hint = url_has_category_hint(url)

    product_like_links = count_product_like_links(soup, url, config)

    article_count = count_article_candidates(soup)

    time_markers = count_time_markers(soup)

    blog_hint = url_has_blog_hint(url)

    nav_links = count_nav_links(soup)

    has_search = has_search_input(soup)

    filter_controls = has_filter_controls(soup)

    related_section = has_related_section(soup)

    homepage_hint = url_is_homepage(url)

    signals = {
        "schema_product": schema_product,
        "add_to_cart_count": add_to_cart_count,
        "price_match_count": price_match_count,
        "url_product_hint": url_product_hint,
        "url_detail_hint": url_detail_hint,
        "url_category_hint": url_category_hint,
        "product_like_links": product_like_links,
        "article_count": article_count,
        "time_markers": time_markers,
        "blog_hint": blog_hint,
        "nav_links": nav_links,
        "has_search": has_search,
        "has_filters": filter_controls,
        "has_related_section": related_section,
        "homepage_hint": homepage_hint,
    }

    if homepage_hint and not url_category_hint:
        homepage_score = _score_homepage(
            url=url, nav_links=nav_links, has_search=has_search
        )

        return PageClassification(
            page_type=PageType.GENERAL,
            pagination=pagination,
            signals=signals,
            notes="Homepage URL without category hint; treating as homepage",
        )

    if filter_controls:
        return PageClassification(
            page_type=PageType.PRODUCT_LIST,
            pagination=pagination,
            signals=signals,
            notes="Detected product list via ProductListDetector",
        )

    product_detail_score = _score_product_detail(
        schema_product=schema_product,
        add_to_cart_count=add_to_cart_count,
        price_match_count=price_match_count,
        url_product_hint=url_detail_hint or url_product_hint,
        product_like_links=product_like_links,
    )

    content_list_score = _score_content_list(
        article_count=article_count,
        time_markers=time_markers,
        blog_hint=blog_hint,
        product_like_links=product_like_links,
    )

    homepage_score = _score_homepage(
        url=url, nav_links=nav_links, has_search=has_search
    )

    if (
        product_detail_score >= 0.7 and (related_section or url_detail_hint)
    ):
        return PageClassification(
            page_type=PageType.PRODUCT_DETAIL,
            pagination=pagination,
            signals=signals,
            notes="Product detail detected; list likely related items",
        )

    if product_detail_score >= 0.6 and product_detail_score >= content_list_score:
        return PageClassification(
            page_type=PageType.PRODUCT_DETAIL,
            pagination=pagination,
            signals=signals,
            notes="Detected product detail signals",
        )

    if content_list_score >= 0.6:
        return PageClassification(
            page_type=PageType.CONTENT_LIST,
            pagination=pagination,
            signals=signals,
            notes="Detected content/blog list signals",
        )

    if homepage_score >= 0.6:
        return PageClassification(
            page_type=PageType.GENERAL,
            pagination=pagination,
            signals=signals,
            notes="Detected homepage signals",
        )

    return PageClassification(
        page_type=PageType.UNKNOWN,
        pagination=pagination,
        signals=signals,
        notes="No strong signals matched",
    )
