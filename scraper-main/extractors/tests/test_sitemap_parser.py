"""
test_sitemap_parser.py — Unit tests for sitemap_parser module.

Tests all public and internal functions:
  - fetch_sitemap
  - parse_sitemap_xml
  - fetch_and_parse_all_sitemaps
  - classify_sitemap_name
  - _is_slug
  - _classify_by_depth
  - classify_url
  - classify_sitemap_entries
"""
import pytest
from unittest.mock import patch, MagicMock
import httpx

from site_crawler.sitemap_parser import (
    fetch_sitemap,
    parse_sitemap_xml,
    fetch_and_parse_all_sitemaps,
    classify_sitemap_name,
    classify_url,
    classify_sitemap_entries,
    _is_slug,
    _classify_by_depth,
)
from site_crawler.models import UrlCategory, DiscoverySource, SitemapEntry


# ---------------------------------------------------------------------------
# Sample XML fixtures
# ---------------------------------------------------------------------------

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

SAMPLE_SITEMAPINDEX = """\
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-products.xml</loc>
    <lastmod>2025-01-15</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-categories.xml</loc>
    <lastmod>2025-01-10</lastmod>
  </sitemap>
</sitemapindex>
"""

SAMPLE_EMPTY_URLSET = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>
"""

SAMPLE_MIXED = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/product/item-1</loc>
  </url>
  <url>
    <loc>  https://example.com/product/item-2  </loc>
  </url>
  <url>
    <loc></loc>
  </url>
  <url>
  </url>
</urlset>
"""


# ---------------------------------------------------------------------------
# Tests: fetch_sitemap
# ---------------------------------------------------------------------------

class TestFetchSitemap:
    """Test HTTP fetching of sitemap XML."""

    @patch("site_crawler.sitemap_parser.httpx.get")
    def test_success(self, mock_get):
        """Should return text on 200 response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<urlset></urlset>"
        mock_get.return_value = mock_resp

        result = fetch_sitemap("https://example.com/sitemap.xml")
        assert result == "<urlset></urlset>"
        mock_get.assert_called_once_with(
            "https://example.com/sitemap.xml", timeout=15, follow_redirects=True
        )

    @patch("site_crawler.sitemap_parser.httpx.get")
    def test_non_200_returns_none(self, mock_get):
        """Should return None on non-200 status."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        assert fetch_sitemap("https://example.com/sitemap.xml") is None

    @patch("site_crawler.sitemap_parser.httpx.get")
    def test_empty_body_returns_none(self, mock_get):
        """Should return None if response body is empty/whitespace."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "   \n  "
        mock_get.return_value = mock_resp

        assert fetch_sitemap("https://example.com/sitemap.xml") is None

    @patch("site_crawler.sitemap_parser.httpx.get")
    def test_network_error_returns_none(self, mock_get):
        """Should return None on network/timeout errors."""
        mock_get.side_effect = httpx.ConnectTimeout("timeout")

        assert fetch_sitemap("https://example.com/sitemap.xml") is None

    @patch("site_crawler.sitemap_parser.httpx.get")
    def test_generic_exception_returns_none(self, mock_get):
        """Should return None on any exception."""
        mock_get.side_effect = Exception("something broke")

        assert fetch_sitemap("https://example.com/sitemap.xml") is None


# ---------------------------------------------------------------------------
# Tests: parse_sitemap_xml
# ---------------------------------------------------------------------------

class TestParseSitemapXml:
    """Test XML parsing for both urlset and sitemapindex formats."""

    def test_urlset_entries(self):
        """Should extract URL entries from a <urlset>."""
        entries, child_sitemaps = parse_sitemap_xml(SAMPLE_URLSET)
        assert len(entries) == 3
        assert child_sitemaps == []

        # Check first entry has all fields
        e = entries[0]
        assert e.loc == "https://example.com/product/widget-123"
        assert e.lastmod == "2025-01-15"
        assert e.changefreq == "weekly"
        assert e.priority == 0.8

    def test_urlset_partial_fields(self):
        """Entries with missing optional fields should still parse."""
        entries, _ = parse_sitemap_xml(SAMPLE_URLSET)
        about_entry = entries[2]
        assert about_entry.loc == "https://example.com/about"
        assert about_entry.lastmod is None
        assert about_entry.changefreq is None
        assert about_entry.priority is None

    def test_sitemapindex(self):
        """Should extract child sitemap URLs from a <sitemapindex>."""
        entries, child_sitemaps = parse_sitemap_xml(SAMPLE_SITEMAPINDEX)
        assert entries == []
        assert len(child_sitemaps) == 2
        assert "https://example.com/sitemap-products.xml" in child_sitemaps
        assert "https://example.com/sitemap-categories.xml" in child_sitemaps

    def test_empty_urlset(self):
        """An empty <urlset> should return no entries."""
        entries, child_sitemaps = parse_sitemap_xml(SAMPLE_EMPTY_URLSET)
        assert entries == []
        assert child_sitemaps == []

    def test_whitespace_in_loc_is_stripped(self):
        """Whitespace around <loc> text should be stripped."""
        entries, _ = parse_sitemap_xml(SAMPLE_MIXED)
        # Should get 2 valid entries (empty <loc> and missing <loc> are skipped)
        assert len(entries) == 2
        assert entries[1].loc == "https://example.com/product/item-2"

    def test_entries_have_no_source_sitemap(self):
        """Parsed entries should have source_sitemap=None by default."""
        entries, _ = parse_sitemap_xml(SAMPLE_URLSET)
        for entry in entries:
            assert entry.source_sitemap is None


# ---------------------------------------------------------------------------
# Tests: fetch_and_parse_all_sitemaps
# ---------------------------------------------------------------------------

class TestFetchAndParseAllSitemaps:
    """Test recursive sitemap fetching & parsing."""

    @patch("site_crawler.sitemap_parser.fetch_sitemap")
    def test_simple_urlset(self, mock_fetch):
        """Single sitemap with URL entries → flat list."""
        mock_fetch.return_value = SAMPLE_URLSET

        entries = fetch_and_parse_all_sitemaps(["https://example.com/sitemap.xml"])
        assert len(entries) == 3
        # All entries should carry source_sitemap
        for e in entries:
            assert e.source_sitemap == "https://example.com/sitemap.xml"

    @patch("site_crawler.sitemap_parser.fetch_sitemap")
    def test_follows_sitemapindex(self, mock_fetch):
        """Should follow child sitemaps from a sitemapindex."""
        def side_effect(url):
            if url == "https://example.com/sitemap.xml":
                return SAMPLE_SITEMAPINDEX
            elif url == "https://example.com/sitemap-products.xml":
                return SAMPLE_URLSET
            elif url == "https://example.com/sitemap-categories.xml":
                return SAMPLE_EMPTY_URLSET
            return None

        mock_fetch.side_effect = side_effect

        entries = fetch_and_parse_all_sitemaps(["https://example.com/sitemap.xml"])
        assert len(entries) == 3
        # Entries came from the products child sitemap
        for e in entries:
            assert e.source_sitemap == "https://example.com/sitemap-products.xml"

    @patch("site_crawler.sitemap_parser.fetch_sitemap")
    def test_max_sitemaps_limit(self, mock_fetch):
        """Should stop after max_sitemaps files."""
        mock_fetch.return_value = SAMPLE_URLSET

        urls = [f"https://example.com/sitemap{i}.xml" for i in range(10)]
        entries = fetch_and_parse_all_sitemaps(urls, max_sitemaps=3)
        # Only 3 sitemaps processed → 3 * 3 entries
        assert len(entries) == 9

    @patch("site_crawler.sitemap_parser.fetch_sitemap")
    def test_skips_duplicates(self, mock_fetch):
        """Should not re-process the same sitemap URL."""
        mock_fetch.return_value = SAMPLE_URLSET

        entries = fetch_and_parse_all_sitemaps([
            "https://example.com/sitemap.xml",
            "https://example.com/sitemap.xml",
        ])
        assert len(entries) == 3
        assert mock_fetch.call_count == 1

    @patch("site_crawler.sitemap_parser.fetch_sitemap")
    def test_fetch_failure_skipped(self, mock_fetch):
        """If a sitemap fails to fetch, it's skipped and others continue."""
        def side_effect(url):
            if "bad" in url:
                return None
            return SAMPLE_URLSET

        mock_fetch.side_effect = side_effect

        entries = fetch_and_parse_all_sitemaps([
            "https://example.com/bad-sitemap.xml",
            "https://example.com/good-sitemap.xml",
        ])
        assert len(entries) == 3

    @patch("site_crawler.sitemap_parser.fetch_sitemap")
    def test_empty_input(self, mock_fetch):
        """Empty sitemap list → empty results."""
        entries = fetch_and_parse_all_sitemaps([])
        assert entries == []
        mock_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: classify_sitemap_name
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tests: _is_slug
# ---------------------------------------------------------------------------

class TestIsSlug:
    """Test the slug detection helper."""

    @pytest.mark.parametrize("segment", [
        "perfo-burin-sds-plus-hr2631ft",
        "perceuse-a-percussion-hp2070",
        "my-cool-product",
        "widget-123",
        "ab",
    ])
    def test_valid_slugs(self, segment):
        """Lowercase, hyphenated, 2+ char strings are slugs."""
        assert _is_slug(segment) is True

    @pytest.mark.parametrize("segment", [
        "123",           # pure digits
        "456789",        # pure digits
        "a",             # too short
        "A-PRODUCT",     # uppercase
        "Hello World",   # spaces
    ])
    def test_not_slugs(self, segment):
        """Pure numbers, single chars, uppercase, spaces are not slugs."""
        assert _is_slug(segment) is False


# ---------------------------------------------------------------------------
# Tests: _classify_by_depth
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tests: classify_url
# ---------------------------------------------------------------------------

class TestClassifyUrl:
    """Test the main URL classification function."""

    # --- Product patterns ---
    @pytest.mark.parametrize("url", [
        "https://example.com/product/widget-123",
        "https://example.com/produit/lampe-led",
        "https://shop.com/items/12345",
        "https://store.com/p/cool-thing",
        "https://prestashop.com/cool-widget-456.html",
        "https://woo.com/product/blue-widget/",
    ])
    def test_product_urls(self, url):
        """Known product URL patterns should be classified as PRODUCT."""
        assert classify_url(url) == UrlCategory.PRODUCT

    # --- Category patterns ---
    @pytest.mark.parametrize("url", [
        "https://example.com/category/electronics",
        "https://example.com/categories/tools",
        "https://shop.com/collection/summer-2025/",
        "https://store.com/collections/new-arrivals/",
        "https://example.com/catalogue/power-tools/",
    ])
    def test_category_urls(self, url):
        """Known category URL patterns should be classified as CATEGORY."""
        assert classify_url(url) == UrlCategory.CATEGORY

    # --- Content/info patterns are grouped with CATEGORY ---
    @pytest.mark.parametrize("url", [
        "https://example.com/about",
        "https://example.com/about-us",
        "https://example.com/qui-sommes-nous",
        "https://example.com/à-propos",
        "https://example.com/contact",
        "https://example.com/contactez-nous",
        "https://example.com/events/spring-sale",
        "https://example.com/blogs/company-news",
        "https://example.com/accueil",
        "https://example.com/acceuil",
        "https://example.com/actualité/promotions",
        "https://example.com/promotions",
    ])
    def test_content_urls_are_categories(self, url):
        """Content/info URLs should be classified as CATEGORY."""
        assert classify_url(url) == UrlCategory.CATEGORY

    @pytest.mark.parametrize("url", [
        "https://example.com/",
    ])
    def test_other_urls(self, url):
        """Generic URLs with no signal should be classified as OTHER."""
        assert classify_url(url) == UrlCategory.OTHER

    # --- Anti-patterns ---
    @pytest.mark.parametrize("url", [
        "https://example.com/blog/post-about-products/",
        "https://example.com/news/2024/01/article",
        "https://example.com/articles/tips-and-tricks",
        "https://example.com/posts/something",
        "https://example.com/tags/sale",
        "https://example.com/author/john",
        "https://example.com/page/2",
        "https://example.com/actualites/promo",
    ])
    def test_anti_patterns_override(self, url):
        """Anti-patterns (blog, news, articles, etc.) should be CATEGORY."""
        assert classify_url(url) == UrlCategory.CATEGORY

    # --- Depth-based classification ---
    @pytest.mark.parametrize("url", [
        "https://comptoir-hammami.com/shop/materiels-btp/electroportatifs-et-consommables/makita/perfo-burin-sds-plus-hr2631ft/",
        "https://comptoir-hammami.com/shop/materiels-btp/electroportatifs-et-consommables/makita/perceuse-a-percussion-hp2070/",
        "https://example.com/shop/cat1/cat2/cat3/my-cool-product/",
    ])
    def test_deep_shop_paths_are_products(self, url):
        """URLs with 3+ segments after /shop/ ending in a slug → PRODUCT."""
        assert classify_url(url) == UrlCategory.PRODUCT

    @pytest.mark.parametrize("url", [
        "https://comptoir-hammami.com/shop/",
        "https://comptoir-hammami.com/shop/materiels-btp/",
        "https://comptoir-hammami.com/shop/materiels-btp/electroportatifs-et-consommables/",
    ])
    def test_shallow_shop_paths_are_categories(self, url):
        """URLs with 0–2 segments after /shop/ → CATEGORY."""
        assert classify_url(url) == UrlCategory.CATEGORY

    # --- Priority: category before product ---
    def test_category_checked_before_product(self):
        """If a URL matches both category and product patterns, category wins."""
        # /category/product/widget-1 has both /category/ and /product/
        url = "https://example.com/category/product/widget-1"
        assert classify_url(url) == UrlCategory.CATEGORY

    # --- PrestaShop-style numeric category ---
    @pytest.mark.parametrize("url", [
        "https://example.com/3-accessories",
        "https://example.com/12-power-tools",
    ])
    def test_prestashop_category_pattern(self, url):
        """PrestaShop /N-slug pattern should be classified as CATEGORY."""
        assert classify_url(url) == UrlCategory.CATEGORY


# ---------------------------------------------------------------------------
# Tests: classify_sitemap_entries
# ---------------------------------------------------------------------------

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
