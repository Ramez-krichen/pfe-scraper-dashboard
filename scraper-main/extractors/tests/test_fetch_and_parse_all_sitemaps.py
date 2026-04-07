import pytest
from unittest.mock import patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from site_crawler.sitemap_parser import fetch_and_parse_all_sitemaps
from site_crawler.sitemap_parser import classify_url
from site_crawler.models import UrlCategory

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
    <loc>https://bricola.tn/sitemap/category.xml</loc>
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

class TestFetchAndParseAllSitemaps:
    """Test recursive sitemap fetching & parsing."""

    # @patch("site_crawler.sitemap_parser.fetch_sitemap")
    def test_simple_urlset(self):
        entries = fetch_and_parse_all_sitemaps(["https://bricola.tn/sitemap/category.xml"])
        classified = [classify_url(e.loc) for e in entries]
        assert all(c == UrlCategory.CATEGORY for c in classified)

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
