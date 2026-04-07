from __future__ import annotations

import re
from typing import Iterable
from bs4 import BeautifulSoup

from .models import PaginationInfo

_PAGINATION_LINK_SELECTORS = [
    "nav.pagination a",
    "ul.pagination a",
    ".pagination a",
    ".page-numbers a",
    ".pager a",
]

_LOAD_MORE_RE = re.compile(r"(load more|show more|afficher plus|voir plus)", re.I)
_PAGE_PARAM_RE = re.compile(r"[?&](page|p|pagenumber)=\d+", re.I)
_PAGE_PATH_RE = re.compile(r"/page/\d+", re.I)


def _has_anchor_with_href_pattern(anchors: Iterable, pattern: re.Pattern) -> bool:
    for a in anchors:
        href = (a.get("href") or "").strip()
        if href and pattern.search(href):
            return True
    return False


def detect_pagination(soup: BeautifulSoup) -> PaginationInfo:
    hints: list[str] = []

    if soup.select_one(", ".join(_PAGINATION_LINK_SELECTORS)):
        hints.append("pagination_links")

    if soup.select_one('a[rel="next"], link[rel="next"]'):
        hints.append("rel_next")

    if soup.select_one('[aria-label*="next" i], [aria-label*="suivant" i]'):
        hints.append("aria_next")

    anchors = soup.find_all("a", href=True)
    if _has_anchor_with_href_pattern(anchors, _PAGE_PARAM_RE):
        hints.append("page_param")
    if _has_anchor_with_href_pattern(anchors, _PAGE_PATH_RE):
        hints.append("page_path")

    for tag in soup.find_all(["button", "a"]):
        text = tag.get_text(" ", strip=True)
        if text and _LOAD_MORE_RE.search(text):
            hints.append("load_more_text")
            break

    return PaginationInfo(has_pagination=bool(hints), hints=hints)
