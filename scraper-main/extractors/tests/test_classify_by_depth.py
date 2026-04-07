import pytest
from site_crawler.sitemap_parser import _classify_by_depth
from site_crawler.models import UrlCategory

class TestClassifyByDepth:
    """Test depth-based classification under shop-root segments."""

    @pytest.mark.parametrize("url,expected", [
        # Shop root alone → CATEGORY
        ("https://example.com/shop/", UrlCategory.CATEGORY),
        # 1 segment after shop → CATEGORY
        ("https://example.com/shop/tools/", UrlCategory.CATEGORY),
        # 2 segments after shop → CATEGORY
        ("https://example.com/shop/tools/drills/", UrlCategory.CATEGORY),
        # 3+ segments with slug tail → PRODUCT
        (
            "https://comptoir-hammami.com/shop/materiels-btp/electroportatifs-et-consommables/makita/perfo-burin-sds-plus-hr2631ft/",
            UrlCategory.PRODUCT,
        ),
        (
            "https://example.com/shop/cat1/cat2/cat3/my-cool-product/",
            UrlCategory.PRODUCT,
        ),
        # boutique root
        ("https://example.com/boutique/shoes/", UrlCategory.CATEGORY),
        ("https://example.com/boutique/a/b/c/nice-shoe/", UrlCategory.PRODUCT),
        # No shop root → None
        ("https://example.com/about/", None),
        ("https://example.com/", None),
        # 3+ segments but last is pure digits → None (not a slug)
        ("https://example.com/shop/a/b/c/12345/", None),
    ])
    def test_depth_classification(self, url, expected):
        assert _classify_by_depth(url) == expected

    def test_empty_path(self):
        """Root URL should return None."""
        assert _classify_by_depth("https://example.com") is None

    def test_produits_root(self):
        """/produits/ is a shop root segment."""
        assert _classify_by_depth("https://example.com/produits/cat1/") == UrlCategory.CATEGORY
        assert _classify_by_depth("https://example.com/produits/a/b/c/slug/") == UrlCategory.PRODUCT
