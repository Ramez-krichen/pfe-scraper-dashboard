"""
Shared extraction models for structured outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


@dataclass
class ProductDetail:
    url: str
    title: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = field(default_factory=list)
    sku: Optional[str] = None
    brand: Optional[str] = None
    availability: Optional[str] = None
    on_page_details: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "price": self.price,
            "currency": self.currency,
            "description": self.description,
            "images": list(self.images),
            "sku": self.sku,
            "brand": self.brand,
            "availability": self.availability,
            "on_page_details": self.on_page_details,
        }


@dataclass
class TextContent:
    title: Optional[str] = None
    text: str = ""
    language: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "text": self.text,
            "language": self.language,
        }


class UrlCategory(str, Enum):
    """Classification of a discovered URL."""

    PRODUCT = "product"
    CATEGORY = "category"
    OTHER = "other"
    BLOG = "blog"
    NEWS = "news"
    ABOUT = "about"
    CONTACT = "contact"
    EVENT = "event"
    PROMO = "promo"
    AUTH = "auth"
    SUPPORT = "support"
    RULES = "rules"


class DiscoverySource(str, Enum):
    """How a URL was discovered."""

    SITEMAP = "sitemap"
    HOMEPAGE = "homepage"


@dataclass
class SitemapEntry:
    """A single <url> entry parsed from a sitemap XML."""

    loc: str
    lastmod: Optional[str] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None
    source_sitemap: Optional[str] = None


@dataclass
class DiscoveredUrl:
    """A single URL discovered during crawling, with its classification."""

    url: str
    lastmod: Optional[str] = None
    changefreq: Optional[str] = None
    category: UrlCategory = UrlCategory.OTHER
    source: DiscoverySource = DiscoverySource.HOMEPAGE
    anchor_text: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "lastmod": self.lastmod,
            "changefreq": self.changefreq,
            "category": self.category.value,
            "source": self.source.value,
            "anchor_text": self.anchor_text,
        }


@dataclass
class CrawlResult:
    """Top-level result from a site crawl / URL discovery run."""

    base_url: str
    source: DiscoverySource = DiscoverySource.HOMEPAGE
    urls: Dict[str, List[Dict]] = field(default_factory=dict)
    sitemap_urls_found: List[str] = field(default_factory=list)
    disallowed_paths: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def count(self) -> int:
        return sum(len(v) for v in self.urls.values() if v is not None)

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "source": self.source.value,
            "urls": self.urls,
            "count": self.count(),
            "sitemap_urls_found": self.sitemap_urls_found,
            "disallowed_paths": self.disallowed_paths,
            "error": self.error,
        }
