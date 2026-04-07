"""
utils.py — Stateless utility helpers for the product_detection module.
"""
from __future__ import annotations

import re
import statistics
from typing import List, Optional, Sequence
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import Tag


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def normalize_url(href: str, base_url: str = "") -> Optional[str]:
    """
    Resolve *href* against *base_url* and return a clean absolute URL.
    Returns None if href is empty, a fragment-only link, or javascript:.
    """
    if not href:
        return None
    href = href.strip()
    if href.startswith("javascript:") or href == "#":
        return None
    try:
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        # Re-serialise without fragment to normalise
        clean = urlunparse(parsed._replace(fragment=""))
        return clean if clean else None
    except Exception:
        return None


def matches_product_url(
    url: str,
    patterns: List[re.Pattern],
    anti_patterns: Optional[List[re.Pattern]] = None,
) -> bool:
    """Return True if *url* path matches at least one product URL pattern
    AND does not match any anti-patterns."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        path_and_query = parsed.path + ("?" + parsed.query if parsed.query else "")
    except Exception:
        path_and_query = url
    # Veto check first (cheaper when it returns early)
    if anti_patterns:
        if any(ap.search(path_and_query) for ap in anti_patterns):
            return False
    return any(p.search(path_and_query) for p in patterns)


def is_excluded_url(href: str, excluded_fragments: List[str], excluded_exact: List[str]) -> bool:
    """Return True if *href* should be skipped (add-to-cart, wishlist, etc.)."""
    if not href:
        return True
    href_lower = href.lower()
    if href_lower in excluded_exact:
        return True
    return any(frag in href_lower for frag in excluded_fragments)


# ---------------------------------------------------------------------------
# DOM structural helpers
# ---------------------------------------------------------------------------

# Patterns that produce per-item unique or quasi-unique class fragments.
# These are stripped before computing the structural signature so that
# WooCommerce's `post-1001`, `post-1002`, `type-product`, `instock`, etc.
# do not prevent identical items from being recognised as a cluster.
_NOISE_CLASS_RE = re.compile(
    r"^(?:"
    r"post-\d+"            # WordPress post ID classes
    r"|\d+"               # bare numeric classes
    r"|type-[\w-]+"       # WooCommerce type-*
    r"|status-[\w-]+"     # WooCommerce status-*
    r"|instock|outofstock"  # stock status
    r"|first|last"         # positional
    r"|odd|even"           # row classes
    r"|^(first|last)(-|$)|"              # first-*, last-*
    r"|.*item-of-.*|"                    # first-item-of-tablet-line, etc
    r"|.*-line$|"                        # last-line
    r"|^col-(xs|sm|md|lg|xl)-\d+$"      # bootstrap grid helpers
    r"|^(row|clearfix)$"                 # common layout helpers
    r"|product_cat.*"
    r"|product-type.*"
    r"|shimmer"
    r"|shipping-taxable"
    r"|sale"
    r"|wd-quantity-overlap"
    r"|wd-with-labels"
    r")$",
    re.IGNORECASE,
)


def get_class_signature(tag: Tag) -> str: # type: ignore
    """
    Produce a stable, sorted string of a tag's CSS classes, with
    per-item unique/noise classes removed.
    Used to group sibling elements by structural similarity.
    """
    classes = tag.get("class") or []
    stable = [c for c in classes if not _NOISE_CLASS_RE.match(str(c))]
    return " ".join(sorted(stable))


def get_tag_key(tag: Tag) -> str: # type: ignore
    """
    Key combining tag name + class signature.
    Two sibling elements with the same key are treated as structurally equivalent.
    """
    return f"{tag.name}::{get_class_signature(tag)}"


def describe_selector(parent_tag: Tag, child_class_sig: str) -> str: # type: ignore
    """
    Build a human-readable CSS-style descriptor for the winning cluster.
    Example: "ul.products-list > li.product-item"
    """
    parent_name = getattr(parent_tag, "name", "div") if parent_tag is not None else "div"
    parent_classes = " ".join(sorted((parent_tag.get("class") or []))) if parent_tag is not None else ""
    parent_str = f"{parent_name}.{'.'.join(parent_classes.split())}" if parent_classes else parent_name

    # Extract cluster child fragment
    if "::" in child_class_sig:
        child_tag_name, child_classes = child_class_sig.split("::", 1)
        child_str = f"{child_tag_name}.{'.'.join(child_classes.split())}" if child_classes else child_tag_name
    else:
        child_str = child_class_sig

    return f"{parent_str} > {child_str}"


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def extract_price_text(text: str, patterns: List[re.Pattern]) -> Optional[str]:
    """
    Search *text* for a price match using all configured patterns.
    Returns the first match string, stripped. None if no match.
    """
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            return m.group(0).strip()
    return None


def extract_title_from_tag(tag: Tag) -> Optional[str]: # type: ignore
    """
    Heuristic title extraction from a product block.
    Priority: h1 > h2 > h3 > [class*=title] > [class*=name] > first <a> text.
    """
    for selector in ("h1", "h2", "h3", "h4"):
        el = tag.find(selector)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)[:200]

    for cls_fragment in ("title", "name", "product-title", "product-name"):
        el = tag.find(class_=re.compile(cls_fragment, re.IGNORECASE))
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)[:200]

    anchor = tag.find("a")
    if anchor and anchor.get_text(strip=True):
        return anchor.get_text(strip=True)[:200]

    return None


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def normalised_std(values: Sequence[float]) -> float:
    """
    Return normalised standard deviation (0 = all equal, 1 = max spread).
    Used to measure cluster consistency.
    """
    if len(values) < 2:
        return 0.0
    max_val = max(values)
    if max_val == 0:
        return 0.0
    try:
        std = statistics.stdev(values)
        return min(std / max_val, 1.0)
    except Exception:
        return 0.0
