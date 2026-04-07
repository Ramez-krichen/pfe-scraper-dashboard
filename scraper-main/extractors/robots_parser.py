"""
robots_parser.py — Fetch and parse robots.txt to extract Sitemap directives
and Disallow paths.

Uses httpx for lightweight HTTP fetching (no browser needed for plain text).
"""
from __future__ import annotations

import logging
from typing import List, Optional
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


def fetch_robots_txt(base_url: str) -> Optional[str]:
    """
    GET {base_url}/robots.txt and return the text content.
    Returns None if the request fails or returns a non-200 status.
    """
    robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
    logger.info(f"Fetching robots.txt from: {robots_url}")

    try:
        response = httpx.get(robots_url, timeout=30, follow_redirects=True)

        if response.status_code != 200:
            logger.info(f"robots.txt returned status {response.status_code}.")
            return None

        text = response.text
        if not text.strip():
            logger.info("robots.txt is empty.")
            return None

        # Heuristic: if no "User-agent" or "Sitemap" keyword, probably not
        # a real robots.txt (could be a styled 404 page).
        lower = text.lower()
        if "user-agent" not in lower and "sitemap" not in lower:
            logger.info("Page doesn't look like a valid robots.txt.")
            return None

        return text

    except Exception as e:
        logger.warning(f"Failed to fetch robots.txt: {e}")
        return None


def parse_sitemap_directives(robots_text: str) -> List[str]:
    """
    Extract all Sitemap: URLs from a robots.txt string.

    Example input line:
        Sitemap: https://egm.tn/sitemap.xml

    Returns a list of sitemap URLs (may be empty).
    """
    sitemaps: List[str] = []
    for line in robots_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            url = stripped.split(":", 1)[1].strip()
            if url:
                sitemaps.append(url)
    return sitemaps


def parse_disallowed_paths(robots_text: str, user_agent: str = "*") -> List[str]:
    """
    Extract Disallow paths for the given User-agent from a robots.txt string.
    Defaults to the wildcard (*) user-agent.

    Returns a list of path strings (e.g. ["/admin/", "/api/"]).
    """
    disallowed: List[str] = []
    in_matching_block = False

    for line in robots_text.splitlines():
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            continue

        lower = stripped.lower()

        if lower.startswith("user-agent:"):
            agent = stripped.split(":", 1)[1].strip()
            in_matching_block = (agent == user_agent or agent == "*")
            continue

        if in_matching_block and lower.startswith("disallow:"):
            path = stripped.split(":", 1)[1].strip()
            if path:
                disallowed.append(path)

    return disallowed
