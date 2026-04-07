import pytest
from site_crawler.sitemap_parser import parse_sitemap_xml, classify_sitemap_entries
from site_crawler.models import UrlCategory, DiscoverySource, SitemapEntry

SAMPLE_URLSET = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/product/widget-123</loc>
    <lastmod>2025-01-15</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://example.com/category/electronics</loc>
    <lastmod>2025-01-10</lastmod>
  </url>
  <url>
    <loc>https://example.com/about</loc>
  </url>
</urlset>
"""

class TestClassifySitemapEntries:
    """Test bulk classification of sitemap entries."""

    def test_classify_entries_from_xml(self):
        """Should classify a list of SitemapEntry objects parsed from XML."""
        entries, _ = parse_sitemap_xml(SAMPLE_URLSET)
        classified = classify_sitemap_entries(entries)

        assert len(classified) == 3
        assert all(u.source == DiscoverySource.SITEMAP for u in classified)

        categories = {u.category for u in classified}
        assert UrlCategory.PRODUCT in categories
        assert UrlCategory.CATEGORY in categories
        assert UrlCategory.OTHER not in categories

    def test_sitemap_name_product_override(self):
        """When source_sitemap signals 'product', all URLs become PRODUCT."""
        entries = [
            SitemapEntry(
                loc="https://example.com/shop/some-item/",
                source_sitemap="https://example.com/product-sitemap1.xml",
            ),
            SitemapEntry(
                loc="https://example.com/about",
                source_sitemap="https://example.com/product-sitemap1.xml",
            ),
        ]
        classified = classify_sitemap_entries(entries)
        assert all(u.category == UrlCategory.PRODUCT for u in classified)

    def test_sitemap_name_category_override(self):
        """When source_sitemap signals 'category', URLs become CATEGORY."""
        entries = [
            SitemapEntry(
                loc="https://example.com/some-unknown-path/",
                source_sitemap="https://example.com/category-sitemap.xml",
            ),
        ]
        classified = classify_sitemap_entries(entries)
        assert classified[0].category == UrlCategory.CATEGORY

    def test_skip_sitemap_marks_other(self):
        """Entries from skip-sitemaps (post, page, etc.) should be OTHER."""
        entries = [
            SitemapEntry(
                loc="https://example.com/product/some-thing",
                source_sitemap="https://example.com/post-sitemap.xml",
            ),
        ]
        classified = classify_sitemap_entries(entries)
        assert classified[0].category == UrlCategory.OTHER

    def test_unknown_sitemap_falls_back_to_url(self):
        """When source_sitemap has no signal, URL-level heuristics are used."""
        entries = [
            SitemapEntry(
                loc="https://example.com/product/widget-123",
                source_sitemap="https://example.com/sitemap.xml",
            ),
            SitemapEntry(
                loc="https://example.com/category/tools",
                source_sitemap="https://example.com/sitemap.xml",
            ),
        ]
        classified = classify_sitemap_entries(entries)
        assert classified[0].category == UrlCategory.PRODUCT
        assert classified[1].category == UrlCategory.CATEGORY

    def test_no_source_sitemap_uses_url_heuristic(self):
        """Entries without source_sitemap fall back to URL classification."""
        entries = [
            SitemapEntry(loc="https://example.com/product/thing-1"),
            SitemapEntry(loc="https://example.com/about"),
        ]
        classified = classify_sitemap_entries(entries)
        assert classified[0].category == UrlCategory.PRODUCT
        assert classified[1].category == UrlCategory.CATEGORY

    def test_mixed_sitemaps(self):
        """Entries from different sitemaps get different classifications."""
        entries = [
            SitemapEntry(
                loc="https://example.com/some-url",
                source_sitemap="https://example.com/product-sitemap1.xml",
            ),
            SitemapEntry(
                loc="https://example.com/another-url",
                source_sitemap="https://example.com/category-sitemap.xml",
            ),
            SitemapEntry(
                loc="https://example.com/blog-post",
                source_sitemap="https://example.com/post-sitemap.xml",
            ),
            SitemapEntry(
                loc="https://example.com/product/actual-product",
                source_sitemap="https://example.com/sitemap.xml",
            ),
        ]
        classified = classify_sitemap_entries(entries)
        assert classified[0].category == UrlCategory.PRODUCT    # from product sitemap
        assert classified[1].category == UrlCategory.CATEGORY    # from category sitemap
        assert classified[2].category == UrlCategory.OTHER       # from post sitemap
        assert classified[3].category == UrlCategory.PRODUCT     # from URL heuristic
