"""
text_content.py — Heuristic extraction for readable text content.
"""
from __future__ import annotations

from typing import Optional

from bs4 import BeautifulSoup
from playwright.async_api import Page
from markdownify import MarkdownConverter

from .models import TextContent


def _parse_html(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _clean_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = " ".join(str(value).split())
    return text if text else None


def _get_meta(soup: BeautifulSoup, *keys: str) -> Optional[str]:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find(
            "meta", attrs={"name": key}
        )
        if tag and tag.get("content"):
            return _clean_text(str(tag.get("content")))
    return None


def _select_best_container(soup: BeautifulSoup) -> BeautifulSoup:
    selectors = [
        "article",
        "main",
        "section#content",
        "div#content",
        "div.content",
        "section.article",
    ]
    best = None
    best_len = 0
    for selector in selectors:
        for tag in soup.select(selector):
            text_len = len(tag.get_text(" ", strip=True))
            if text_len > best_len:
                best_len = text_len
                best = tag

    if best is not None:
        return best # type: ignore

    return soup.body or soup # type: ignore


async def extract_text_content(page: Page) -> TextContent:
    """
    Extract readable text content from a page.
    Returns a TextContent object with best-effort fields.
    """
    # if not html:
    #     return TextContent(url=url)
    await page.evaluate("""() => document.querySelectorAll("script, noscript, aside, form, style, div[class*='header'], header:not(article header), div[class*='footer'], footer, div[class*='nav'], .newsletter, div[class*='pied'], nav, .copyright, div[class*='chat'], div.head, div[class*='whatsapp'], div[class*='back']").forEach(el => el.remove())""")

    soup = _parse_html(await page.content())
    title = _get_meta(soup, "og:title", "twitter:title", "title")
    if not title:
        h1 = soup.find("h1")
        title = _clean_text(h1.get_text(" ", strip=True) if h1 else None)
    if not title:
        title_tag = soup.find("title")
        title = _clean_text(title_tag.get_text(" ", strip=True) if title_tag else None)

    lang = None
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        lang = _clean_text(html_tag.get("lang")) # type: ignore

    container = _select_best_container(soup)

    # Remove common non-content elements
    # for tag in container.find_all(
    #     ["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]
    # ):
    #     tag.decompose()

    text = MarkdownConverter().convert_soup(container)

    return TextContent(title=title, text=text, language=lang)
