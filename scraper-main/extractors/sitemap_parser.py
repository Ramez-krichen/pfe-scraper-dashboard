"""
sitemap_parser.py — Fetch and parse sitemap XML files (both <sitemapindex>
and <urlset> formats).

Uses httpx for lightweight HTTP fetching (no browser needed for XML).
"""
from __future__ import annotations

import logging
import re
import random
import time
import unicodedata
from typing import List, Optional, Dict
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from .models import DiscoveredUrl, UrlCategory, DiscoverySource, SitemapEntry

logger = logging.getLogger(__name__)


def fetch_sitemap(url: str) -> Optional[str]:
    """
    Fetch a sitemap XML file via HTTP and return its raw text.
    Returns None on failure.
    """
    logger.info(f"Fetching sitemap: {url}")
    try:
        response = httpx.get(url, timeout=15, follow_redirects=True)
        if response.status_code != 200:
            logger.warning(f"Sitemap {url} returned status {response.status_code}.")
            return None
        text = response.text
        if not text.strip():
            return None
        return text
    except Exception as e:
        logger.warning(f"Failed to fetch sitemap {url}: {e}")
        return None


def parse_sitemap_xml(xml_text: str) -> tuple[List[SitemapEntry], List[str]]:
    """
    Parse a sitemap XML string.

    Returns a tuple of (url_entries, child_sitemap_urls):
        - url_entries: list of SitemapEntry from <urlset><url> elements
        - child_sitemap_urls: list of sitemap URLs from <sitemapindex><sitemap> elements

    Handles both <sitemapindex> (index pointing to other sitemaps) and
    <urlset> (actual URL list) formats.
    """
    soup = BeautifulSoup(xml_text, "lxml-xml")

    entries: List[SitemapEntry] = []
    child_sitemaps: List[str] = []

    # Check for sitemap index: <sitemapindex> -> <sitemap> -> <loc>
    for sitemap_tag in soup.find_all("sitemap"):
        loc = sitemap_tag.find("loc")
        if loc and loc.string:
            child_sitemaps.append(loc.string.strip())

    # Check for URL set: <urlset> -> <url> -> <loc>, <lastmod>, etc.
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        if not loc or not loc.string:
            continue

        lastmod_tag = url_tag.find("lastmod")
        changefreq_tag = url_tag.find("changefreq")
        priority_tag = url_tag.find("priority")

        entry = SitemapEntry(
            loc=loc.string.strip(),
            lastmod=lastmod_tag.string.strip() if lastmod_tag and lastmod_tag.string else None,
            changefreq=changefreq_tag.string.strip() if changefreq_tag and changefreq_tag.string else None,
            priority=float(priority_tag.string.strip()) if priority_tag and priority_tag.string else None,
        )
        entries.append(entry)

    return entries, child_sitemaps


def fetch_and_parse_all_sitemaps(
    sitemap_urls: List[str],
    *,
    max_sitemaps: int = 50,
) -> List[SitemapEntry]:
    """
    Recursively fetch and parse sitemaps (following sitemap index files).
    Stops after processing max_sitemaps files to avoid runaway crawls.

    Each SitemapEntry records which sitemap file it originated from via
    the ``source_sitemap`` field.

    Returns a flat list of all SitemapEntry objects discovered.
    """
    all_entries: List[SitemapEntry] = []
    visited: set[str] = set()
    queue = list(sitemap_urls)

    while queue and len(visited) < max_sitemaps:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        xml_text = fetch_sitemap(url)
        time.sleep(random.randint(8, 15))

        if not xml_text:
            continue

        entries, child_sitemaps = parse_sitemap_xml(xml_text)

        # Tag every entry with the sitemap it came from
        for entry in entries:
            entry.source_sitemap = url

        all_entries.extend(entries)

        # Queue child sitemaps for processing
        for child_url in child_sitemaps:
            if child_url not in visited:
                queue.append(child_url)

    logger.info(
        f"Parsed {len(visited)} sitemap(s), found {len(all_entries)} URL entries."
    )
    return all_entries


# ---------------------------------------------------------------------------
# Sitemap-name classification
# ---------------------------------------------------------------------------

# Patterns to detect the *type* of content from the sitemap filename itself.
# Checked against the filename portion of the sitemap URL (e.g. "product-sitemap1.xml").

_SITEMAP_PRODUCT_PATTERNS = [
    re.compile(r"product[-_]sitemap", re.IGNORECASE),
    re.compile(r"produit[-_]sitemap", re.IGNORECASE),
    re.compile(r"sitemap[-_]product", re.IGNORECASE),
]

_SITEMAP_CATEGORY_PATTERNS = [
    re.compile(r"category[-_]sitemap", re.IGNORECASE),
    re.compile(r"categorie[-_]sitemap", re.IGNORECASE),
    re.compile(r"product[_-]cat[-_]sitemap", re.IGNORECASE),
    re.compile(r"project[_-]cat[-_]sitemap", re.IGNORECASE),
    re.compile(r"sitemap[-_]categor", re.IGNORECASE),
]

_SITEMAP_SKIP_PATTERNS = [
    re.compile(r"post[-_]sitemap", re.IGNORECASE),
    re.compile(r"page[-_]sitemap", re.IGNORECASE),
    re.compile(r"cms[_-]block[-_]sitemap", re.IGNORECASE),
    re.compile(r"portfolio[-_]sitemap", re.IGNORECASE),
    re.compile(r"product[_-]tag[-_]sitemap", re.IGNORECASE),
    re.compile(r"basel[_-]sidebar[-_]sitemap", re.IGNORECASE),
    re.compile(r"author[-_]sitemap", re.IGNORECASE),
]


def classify_sitemap_name(sitemap_url: str) -> Optional[UrlCategory]:
    """
    Inspect a sitemap URL's filename to determine the type of content it holds.

    Returns:
        UrlCategory.PRODUCT  — sitemap clearly holds products
        UrlCategory.CATEGORY — sitemap clearly holds categories
        UrlCategory.OTHER    — sitemap is known non-product/non-category (blog, pages …)
        None                 — no signal from the filename
    """
    # Extract just the filename: "product-sitemap1.xml"
    path = urlparse(sitemap_url).path
    filename = path.rsplit("/", 1)[-1] if "/" in path else path

    for pat in _SITEMAP_SKIP_PATTERNS:
        if pat.search(filename):
            return UrlCategory.OTHER

    for pat in _SITEMAP_PRODUCT_PATTERNS:
        if pat.search(filename):
            return UrlCategory.PRODUCT

    for pat in _SITEMAP_CATEGORY_PATTERNS:
        if pat.search(filename):
            return UrlCategory.CATEGORY

    return None


# ---------------------------------------------------------------------------
# URL classification helpers
# ---------------------------------------------------------------------------

_CATEGORY_PATTERNS = [
    r"/(nos\-)?categor",            # /category/, /categories/, /categorie/
    r"/collection[s]?/",
    r"/catalog\/?",
    r"/products",
    r"/produits",
    r"/c/",
    r"/cat/",
    r"\/\d{1,3}-[0-9a-zA-Z+\-?]+\/?$",
    r"/accueil",
    r"[nos\-]?marque[s]?",
]

_PRODUCT_PATTERNS = [
    r"/product[s]?/[0-9\w-]+/?",
    r"/produit[s]?/[0-9\w-]+/?",
    r"/item[s]?/[0-9\w-]+/?",
    r"/p/[0-9\w-]+/?",
    r"[a-zA-Z][a-zA-Z0-9-]+-\d+\.html$",   # PrestaShop: slug-ID.html
    r"[?&](?:id|pid|product_id|item_id)=\d+",
    r"/product/[0-9\w-]+/?$",                    # WooCommerce
]

_BLOG_PATTERNS = [
    r"/blog[s]?",
    r"/article[s]?",
    r"/post[s]?",
    r"/tag[s]?",
]

_NEWS_PATTERNS = [
    r"/news",
    r"/actualit",
]

_ABOUT_PATTERNS = [
    r"/about[\w-]*",
    r"/a[-_/]?propos[\w-]*",
    r"/qui[-_/]?sommes(?:[-_/]?nous)?",
]

_CONTACT_PATTERNS = [
    r"/contact[\w-]*",
]

_EVENT_PATTERNS = [
    r"/event[s]?[\w-]*",
    r"/evenement[s]?[\w-]*",
]

_PROMO_PATTERNS = [
    r"/promo(?:tion)?s?",
    r"/offre[s]?",
    r"/pack[s]?",
]

_AUTH_PATTERNS = [
    r"/login",
    r"/logout",
    r"password",
    r"register|registration",
    r"account",
    r"checkout",
    r"cart",
    r"wishlist",
]

_SUPPORT_PATTERNS = [
    r"ticket[s]?",
]

_ANTI_PRODUCT_PATTERNS = [
    # r"/\d{4}/\d{2}/",       # Date-based paths
    r"/author",
    r"/page/\d+",
]

_RULES_PATTERNS = [
    r"conditions",
    r"mentions",
    r"politique",
    r"confidentialite",
]

# Path prefixes that act as a shop root (products live deep under these)
_SHOP_ROOT_SEGMENTS = {"shop", "boutique", "cat", "produits"}

_compiled_category = [re.compile(p, re.IGNORECASE) for p in _CATEGORY_PATTERNS]
_compiled_product = [re.compile(p, re.IGNORECASE) for p in _PRODUCT_PATTERNS]
_compiled_blog = [re.compile(p, re.IGNORECASE) for p in _BLOG_PATTERNS]
_compiled_news = [re.compile(p, re.IGNORECASE) for p in _NEWS_PATTERNS]
_compiled_about = [re.compile(p, re.IGNORECASE) for p in _ABOUT_PATTERNS]
_compiled_contact = [re.compile(p, re.IGNORECASE) for p in _CONTACT_PATTERNS]
_compiled_event = [re.compile(p, re.IGNORECASE) for p in _EVENT_PATTERNS]
_compiled_promo = [re.compile(p, re.IGNORECASE) for p in _PROMO_PATTERNS]
_compiled_auth = [re.compile(p, re.IGNORECASE) for p in _AUTH_PATTERNS]
_compiled_rules = [re.compile(p, re.IGNORECASE) for p in _RULES_PATTERNS]
_compiled_support = [re.compile(p, re.IGNORECASE) for p in _SUPPORT_PATTERNS]
_compiled_anti = [re.compile(p, re.IGNORECASE) for p in _ANTI_PRODUCT_PATTERNS]

# A "slug" segment: lowercase letters/digits/hyphens, at least 2 chars, not all digits
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,}$")


def _normalize_url_for_matching(url: str) -> str:
    """Return a lowercase, unquoted, ASCII-safe URL string for regex matching."""
    decoded = unquote(url)
    ascii_url = unicodedata.normalize("NFKD", decoded).encode("ascii", "ignore").decode("ascii")
    return ascii_url.lower()


def _is_slug(segment: str) -> bool:
    """Return True if the segment looks like a product slug (not a pure number)."""
    return bool(_SLUG_RE.match(segment)) and not segment.isdigit()


def _classify_by_depth(url: str) -> Optional[UrlCategory]:
    """
    Analyse the URL path depth to distinguish products from categories
    under shop-root prefixes.

    Heuristic:
        /shop/                          → CATEGORY  (just the root)
        /shop/cat1/                     → CATEGORY  (1 level below root)
        /shop/cat1/cat2/                → CATEGORY  (2 levels — still navigational)
        /shop/cat1/cat2/cat3/slug/      → PRODUCT   (3+ levels below root with slug tail)
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return None

    segments = [s for s in path.split("/") if s]
    if not segments:
        return None

    # Find a shop-root segment
    shop_idx: Optional[int] = None
    for i, seg in enumerate(segments):
        if seg.lower() in _SHOP_ROOT_SEGMENTS:
            shop_idx = i
            break

    if shop_idx is None:
        return None

    # Segments after the shop root
    after = segments[shop_idx + 1:]

    if len(after) <= 2:
        # /shop/ or /shop/cat1/ or /shop/cat1/cat2/ → CATEGORY
        return UrlCategory.CATEGORY

    # 3+ segments after shop root — check if the last segment is a slug
    if _is_slug(after[-1]):
        return UrlCategory.PRODUCT

    return None


def classify_url(url: str) -> UrlCategory:
    """
    Classify a single URL as PRODUCT, CATEGORY, or OTHER based on path heuristics.
    """
    matchable_url = _normalize_url_for_matching(url)

    # Check non-product content patterns first
    if any(pat.search(matchable_url) for pat in _compiled_anti):
        return UrlCategory.OTHER

    # Check category patterns
    if any(pat.search(matchable_url) for pat in _compiled_category):
        return UrlCategory.CATEGORY

    # Check product patterns
    if any(pat.search(matchable_url) for pat in _compiled_product):
        return UrlCategory.PRODUCT
    
    # Check blog patterns
    if any(pat.search(matchable_url) for pat in _compiled_blog):
        return UrlCategory.BLOG
    
    # Check news patterns
    if any(pat.search(matchable_url) for pat in _compiled_news):
        return UrlCategory.NEWS
    
    # Check about patterns
    if any(pat.search(matchable_url) for pat in _compiled_about):
        return UrlCategory.ABOUT
    
    # Check contact patterns
    if any(pat.search(matchable_url) for pat in _compiled_contact):
        return UrlCategory.CONTACT
    
    # Check event patterns
    if any(pat.search(matchable_url) for pat in _compiled_event):
        return UrlCategory.EVENT
    
    # Check promo patterns
    if any(pat.search(matchable_url) for pat in _compiled_promo):
        return UrlCategory.PROMO
    
    # Check auth patterns
    if any(pat.search(matchable_url) for pat in _compiled_auth):
        return UrlCategory.AUTH
    
    # Check support patterns
    if any(pat.search(matchable_url) for pat in _compiled_support):
        return UrlCategory.SUPPORT
    
    # Check rules patterns
    if any(pat.search(matchable_url) for pat in _compiled_rules):
        return UrlCategory.RULES

    # Depth-based analysis for /shop/-style paths
    depth_result = _classify_by_depth(matchable_url)
    if depth_result is not None:
        return depth_result

    return UrlCategory.OTHER


def classify_sitemap_entries(entries: List[SitemapEntry]) -> Dict[str, List[Dict]]:
    """
    Convert a list of SitemapEntry objects into classified DiscoveredUrl objects.

    If an entry's ``source_sitemap`` provides a strong classification signal
    (via the sitemap filename), that classification is used directly.
    Otherwise, the URL-level heuristics are applied.
    """
    # Pre-compute sitemap-name classifications (cache per sitemap URL)
    _sitemap_hint_cache: dict[str, Optional[UrlCategory]] = {}

    results: Dict[str, List[Dict]] = {
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

    for entry in entries:
        category: Optional[UrlCategory] = None

        # Try sitemap-name hint first
        if entry.source_sitemap:
            if entry.source_sitemap not in _sitemap_hint_cache:
                _sitemap_hint_cache[entry.source_sitemap] = classify_sitemap_name(
                    entry.source_sitemap
                )
            category = _sitemap_hint_cache[entry.source_sitemap]

        # Fall back to URL-level classification
        if category is None:
            category = classify_url(entry.loc)

        results[category.value].append(DiscoveredUrl(
            url=entry.loc,
            lastmod=entry.lastmod,
            changefreq=entry.changefreq,
            category=category,
            source=DiscoverySource.SITEMAP,
        ).to_dict())

    return results
