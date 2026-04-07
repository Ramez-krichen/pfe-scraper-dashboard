"""
scorer.py — HeuristicScorer: scores candidate product block clusters.

Scoring is fully configurable via ScoringConfig and degrades gracefully
when signals are absent (e.g. no schema.org markup — that signal just
contributes 0 to the total).
"""
from __future__ import annotations

import re
from typing import List

from bs4 import Tag

from .models import ClusterScore, ScoringConfig
from .utils import (
    extract_price_text,
    is_excluded_url,
    matches_product_url,
    normalised_std,
)


class HeuristicScorer:
    """
    Scores a list of BeautifulSoup Tag objects (a candidate cluster) using
    configurable heuristic signals.

    Usage
    -----
    scorer = HeuristicScorer(config)
    score  = scorer.score_block(tag)
    result = scorer.score_cluster(blocks, parent_tag, child_key)
    """

    def __init__(self, config: ScoringConfig) -> None:
        self.config = config
        self._price_re: List[re.Pattern] = config.compiled_price_patterns()
        self._product_url_re: List[re.Pattern] = config.compiled_product_url_patterns()
        self._add_to_cart_text_re = re.compile(
            "|".join(re.escape(k) for k in config.add_to_cart_keywords),
            re.IGNORECASE,
        )
        self._add_to_cart_class_re = re.compile(
            "|".join(re.escape(k) for k in config.add_to_cart_class_fragments),
            re.IGNORECASE,
        )

    # ------------------------------------------------------------------
    # Single-block scoring
    # ------------------------------------------------------------------

    def score_block(self, block: Tag) -> float: # type: ignore
        """
        Compute a numeric score for a single candidate product block tag.

        Returns a float ≥ 0.  The theoretical maximum equals the sum of
        all configured weights (default = 7.0).
        """
        score: float = 0.0
        cfg = self.config

        # Signal 1: has image
        if block.find("img"):
            score += cfg.weight_has_image

        # Signal 2: has anchor
        anchors = block.find_all("a", href=True)
        if anchors:
            score += cfg.weight_has_anchor

            # Signal 3: anchor with product-like URL
            for a in anchors:
                href = a.get("href", "")
                if (
                    not is_excluded_url(href, cfg.excluded_url_fragments, cfg.excluded_url_exact)
                    and matches_product_url(href, self._product_url_re)
                ):
                    score += cfg.weight_product_url
                    break

        # Signal 4: price pattern in block text
        block_text = block.get_text(" ", strip=True)
        if extract_price_text(block_text, self._price_re):
            score += cfg.weight_price_match

        # Signal 5: add-to-cart button / link
        if self._has_add_to_cart(block):
            score += cfg.weight_add_to_cart

        # Signal 6: schema.org Product markup
        if block.find(attrs={"itemtype": re.compile(r"schema\.org/Product", re.IGNORECASE)}):
            score += cfg.weight_schema_org
        # Also check itemscope descendants
        elif block.find(attrs={"itemscope": True, "itemtype": re.compile(r"Product", re.IGNORECASE)}):
            score += cfg.weight_schema_org

        return score

    def _has_add_to_cart(self, block: Tag) -> bool: # type: ignore
        """Check for add-to-cart button via text content or class name."""
        # Check button/link text
        for tag in block.find_all(["button", "a", "input"]):
            text = tag.get_text(strip=True)
            if text and self._add_to_cart_text_re.search(text):
                return True
            classes = " ".join(tag.get("class") or [])
            if classes and self._add_to_cart_class_re.search(classes):
                return True
            # Also check data-action or aria-label
            for attr in ("data-action", "aria-label", "title", "value"):
                val = tag.get(attr, "")
                if val and self._add_to_cart_text_re.search(val):
                    return True
        return False

    # ------------------------------------------------------------------
    # Cluster scoring
    # ------------------------------------------------------------------

    def max_possible_score(self) -> float:
        """Return the theoretical maximum block score given current config weights."""
        cfg = self.config
        return (
            cfg.weight_has_image
            + cfg.weight_has_anchor
            + cfg.weight_product_url
            + cfg.weight_price_match
            + cfg.weight_add_to_cart
            + cfg.weight_schema_org
        )

    def score_cluster(
        self,
        blocks: List[Tag], # type: ignore
        parent_tag,
        child_key: str,
    ) -> ClusterScore:
        """
        Compute a ClusterScore for a group of sibling tags that share
        the same structural key.
        """
        block_scores = [self.score_block(b) for b in blocks]
        avg = sum(block_scores) / len(block_scores) if block_scores else 0.0
        std_norm = normalised_std(block_scores)
        consistency = 1.0 - std_norm   # 1 = perfectly uniform, 0 = highly variable

        # URL consistency: fraction of blocks containing at least one product URL
        url_hits = sum(1 for b in blocks if self._block_has_product_url(b))
        url_consistency = url_hits / len(blocks) if blocks else 0.0

        composite = self._composite_score(avg, consistency, url_consistency, len(blocks))

        return ClusterScore(
            blocks=blocks,
            parent_tag=str(getattr(parent_tag, "name", "unknown")),
            class_signature=child_key,
            avg_block_score=avg,
            block_count=len(blocks),
            url_consistency=url_consistency,
            consistency=consistency,
            composite_score=composite,
        )

    def _block_has_product_url(self, block: Tag) -> bool: # type: ignore
        """True if any non-excluded anchor in block has a product-like URL."""
        cfg = self.config
        for a in block.find_all("a", href=True):
            href = a.get("href", "")
            if (
                not is_excluded_url(href, cfg.excluded_url_fragments, cfg.excluded_url_exact)
                and matches_product_url(href, self._product_url_re)
            ):
                return True
        return False

    def _composite_score(
        self,
        avg_block_score: float,
        consistency: float,
        url_consistency: float,
        block_count: int,
    ) -> float:
        """
        Blended composite used only for *ranking* clusters, not for
        the public confidence score (that is computed in detector.py).
        """
        cfg = self.config
        max_score = self.max_possible_score()
        norm_avg = avg_block_score / max_score if max_score > 0 else 0.0
        count_factor = min(block_count / cfg.conf_block_count_saturation, 1.0)
        return (
            norm_avg * cfg.conf_weight_avg_score
            + consistency * cfg.conf_weight_consistency
            + url_consistency * cfg.conf_weight_url_consistency
            + count_factor * cfg.conf_weight_block_count
        )

    # ------------------------------------------------------------------
    # Public confidence score (used by detector.py)
    # ------------------------------------------------------------------

    def compute_confidence(self, cluster: ClusterScore) -> float:
        """
        Compute the final public-facing confidence score (0.0–1.0)
        for the winning cluster.
        """
        cfg = self.config
        max_score = self.max_possible_score()
        norm_avg = cluster.avg_block_score / max_score if max_score > 0 else 0.0
        count_factor = min(cluster.block_count / cfg.conf_block_count_saturation, 1.0)
        raw = (
            norm_avg * cfg.conf_weight_avg_score
            + cluster.consistency * cfg.conf_weight_consistency
            + cluster.url_consistency * cfg.conf_weight_url_consistency
            + count_factor * cfg.conf_weight_block_count
        )
        return max(0.0, min(raw, 1.0))
