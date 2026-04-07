"""
models.py — Pure Python data classes for the product_detection module.
No external runtime dependencies.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Per-product output
# ---------------------------------------------------------------------------

@dataclass
class ProductItem:
    """Represents a single detected product on a listing page."""
    url: str
    title: Optional[str] = None
    price: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "price": self.price,
        }


# ---------------------------------------------------------------------------
# Top-level detection result (matches the required JSON schema)
# ---------------------------------------------------------------------------

@dataclass
class DetectionResult:
    """
    Root output object returned by ProductListDetector.detect().

    Fields
    ------
    is_product_list     : True when the page is confidently a product listing.
    confidence_score    : 0.0–1.0 blended confidence.
    container_selector  : A human-readable CSS-style descriptor of the winning
                          container (e.g. "ul.products-list > li.item").
                          None when no list is detected.
    products            : Extracted product items.
    """
    is_product_list: bool
    confidence_score: float
    container_selector: Optional[str]
    products: List[ProductItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "is_product_list": self.is_product_list,
            "confidence_score": round(self.confidence_score, 4),
            "container_selector": self.container_selector,
            "products": [p.to_dict() for p in self.products],
        }


# ---------------------------------------------------------------------------
# Intermediate scoring result for a cluster
# ---------------------------------------------------------------------------

@dataclass
class ClusterScore:
    """Internal scoring result for a candidate repeating-block cluster."""
    blocks: list                   # list of bs4 Tag objects
    parent_tag: str                # tag name of the common parent
    class_signature: str           # sorted common class string of blocks
    avg_block_score: float = 0.0
    block_count: int = 0
    url_consistency: float = 0.0   # fraction of blocks that have a product URL
    consistency: float = 1.0       # 1 - normalised std-dev of per-block scores
    composite_score: float = 0.0  # final blended score used for ranking


# ---------------------------------------------------------------------------
# Scoring configuration (injectable, platform-extensible)
# ---------------------------------------------------------------------------

@dataclass
class ScoringConfig:
    """
    Configures all tunable parameters for HeuristicScorer and HeuristicExtractor.

    Custom regex rules or URL patterns can be injected at construction time.
    """

    # --- Cluster detection ---
    min_cluster_size: int = 1      # minimum sibling count to be a candidate cluster

    # --- Scoring signals (each adds this weight to the block score) ---
    weight_has_image: float = 1.0
    weight_has_anchor: float = 1.0
    weight_product_url: float = 1.0
    weight_price_match: float = 1.5     # slightly higher — very discriminating
    weight_add_to_cart: float = 1.0
    weight_schema_org: float = 1.5     # strong structural signal

    # --- Confidence weights ---
    conf_weight_avg_score: float = 0.50
    conf_weight_consistency: float = 0.20
    conf_weight_url_consistency: float = 0.20
    conf_weight_block_count: float = 0.10
    conf_block_count_saturation: int = 20   # block count at which count weight saturates

    # --- Minimum thresholds ---
    min_confidence_to_declare: float = 0.2   # below this → is_product_list=False

    # --- Price regex ---
    price_patterns: List[str] = field(default_factory=lambda: [
        r"\d[\d\s]*[.,]\d{2}\s*(?:DT|TND|\$)",
        r"(?:DT|TND|€|\$)\s*\d[\d\s]*[.,]?\d*",
        r"\d+[.,]?\d*\s*(?:DT|TND|€|\$)",     # minimal form
    ])

    # --- Product URL patterns ---
    product_url_patterns: List[str] = field(default_factory=lambda: [
        r"/product[s]?/",
        r"/produit[s]?/",
        r"/shop/[^/]+",           # /shop/<slug>
        r"/item[s]?/",
        r"/p/[^/]+",              # /p/<slug>
        r"/catalogue/",
        # PrestaShop: slug-ID.html (requires alphabetic slug before ID)
        r"[a-zA-Z][a-zA-Z0-9-]+-\d+\.html$",
        # Query-string product ID parameters
        r"[?&](?:id|pid|product_id|item_id)=\d+",
        # WooCommerce: /product/slug/
        r"/product/[\w-]+/?$",
    ])

    # --- Anti-patterns: URLs matching these are NOT considered product URLs ---
    # These override the product_url_patterns above.
    anti_product_url_patterns: List[str] = field(default_factory=lambda: [
        r"/\d{4}/\d{2}/",         # Date-based paths (/2024/01/)
        r"/\d{4}/[a-z]",          # Year-then-slug paths (/2024/post-title)
        r"/blog/",
        r"/news/",
        r"/actualit",              # /actualites/, /actualite/
        r"/article[s]?/",
        r"/post[s]?/",
        r"/tag[s]?/",
        r"/categor",
        r"/author/",
        r"/page/\d+",             # Pagination pages
        r"/\w+(compte|connexion)\w+",
    ])

    def compiled_anti_product_patterns(self) -> List[re.Pattern]:
        return [re.compile(p, re.IGNORECASE) for p in self.anti_product_url_patterns]

    # --- Add-to-cart signal keywords (case-insensitive) ---
    add_to_cart_keywords: List[str] = field(default_factory=lambda: [
        "add to cart", "add to bag", "ajouter au panier",
        "ajouter", "buy now", "acheter",
    ])
    add_to_cart_class_fragments: List[str] = field(default_factory=lambda: [
        "add-to-cart", "addtocart", "add_to_cart", "btn-cart",
        "cart-button", "buy-btn",
    ])

    # --- Excluded link patterns (per-block URL extraction) ---
    excluded_url_fragments: List[str] = field(default_factory=lambda: [
        "add-to-cart", "wishlist", "compare", "quickview",
        "quick-view", "quick_view", "login", "register",
    ])
    excluded_url_exact: List[str] = field(default_factory=lambda: ["#", "javascript:void(0)"])

    def compiled_price_patterns(self) -> List[re.Pattern]:
        return [re.compile(p, re.IGNORECASE) for p in self.price_patterns]

    def compiled_product_url_patterns(self) -> List[re.Pattern]:
        return [re.compile(p, re.IGNORECASE) for p in self.product_url_patterns]
