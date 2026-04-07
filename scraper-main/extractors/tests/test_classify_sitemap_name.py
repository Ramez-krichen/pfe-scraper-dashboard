import pytest
from site_crawler.sitemap_parser import classify_sitemap_name
from site_crawler.models import UrlCategory

class TestClassifySitemapName:
    """Test sitemap-name-based classification."""

    @pytest.mark.parametrize("url,expected", [
        # Product sitemaps
        ("https://example.com/product-sitemap1.xml", UrlCategory.PRODUCT),
        ("https://example.com/product-sitemap2.xml", UrlCategory.PRODUCT),
        ("https://example.com/product_sitemap.xml", UrlCategory.PRODUCT),
        ("https://example.com/produit-sitemap.xml", UrlCategory.PRODUCT),
        ("https://example.com/sitemap-products.xml", UrlCategory.PRODUCT),
        # Category sitemaps
        ("https://example.com/category-sitemap.xml", UrlCategory.CATEGORY),
        ("https://example.com/product_cat-sitemap.xml", UrlCategory.CATEGORY),
        ("https://example.com/project-cat-sitemap.xml", UrlCategory.CATEGORY),
        ("https://example.com/sitemap-categories.xml", UrlCategory.CATEGORY),
        # Skip sitemaps (OTHER)
        ("https://example.com/post-sitemap.xml", UrlCategory.OTHER),
        ("https://example.com/page-sitemap.xml", UrlCategory.OTHER),
        ("https://example.com/cms_block-sitemap.xml", UrlCategory.OTHER),
        ("https://example.com/portfolio-sitemap.xml", UrlCategory.OTHER),
        ("https://example.com/product_tag-sitemap.xml", UrlCategory.OTHER),
        ("https://example.com/basel_sidebar-sitemap.xml", UrlCategory.OTHER),
        ("https://example.com/author-sitemap.xml", UrlCategory.OTHER),
    ])
    def test_known_sitemap_names(self, url, expected):
        """Sitemap filenames with known keywords should classify correctly."""
        assert classify_sitemap_name(url) == expected

    @pytest.mark.parametrize("url", [
        "https://example.com/sitemap.xml",
        "https://example.com/sitemap_index.xml",
        "https://example.com/my-custom-sitemap.xml",
    ])
    def test_unknown_sitemap_names(self, url):
        """Sitemaps with no recognisable pattern should return None."""
        assert classify_sitemap_name(url) is None

    def test_case_insensitive(self):
        """Sitemap name matching should be case-insensitive."""
        assert classify_sitemap_name("https://example.com/Product-Sitemap.xml") == UrlCategory.PRODUCT
        assert classify_sitemap_name("https://example.com/CATEGORY-SITEMAP.xml") == UrlCategory.CATEGORY
