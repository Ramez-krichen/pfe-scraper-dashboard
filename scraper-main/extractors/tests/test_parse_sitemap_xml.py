import pytest
from site_crawler.sitemap_parser import parse_sitemap_xml

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
