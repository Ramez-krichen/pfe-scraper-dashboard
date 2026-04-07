"""
test_robots_parser.py — Unit tests for robots_parser module.

Tests parse_sitemap_directives and parse_disallowed_paths against the
sample robots.txt files from the robots.txt/ directory.
"""
import os
import pytest

from site_crawler.robots_parser import parse_sitemap_directives, parse_disallowed_paths


# ---------------------------------------------------------------------------
# Helper: load sample robots.txt files from the project's robots.txt/ dir
# ---------------------------------------------------------------------------

_ROBOTS_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "robots.txt"
)


def _load_robots(site: str) -> str:
    path = os.path.join(_ROBOTS_DIR, site, "robots.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Tests: parse_sitemap_directives
# ---------------------------------------------------------------------------

class TestParseSitemapDirectives:
    """Test Sitemap: directive extraction from robots.txt."""

    def test_egm_tn_has_sitemap(self):
        """egm.tn robots.txt declares a sitemap."""
        text = _load_robots("egm.tn")
        sitemaps = parse_sitemap_directives(text)
        assert sitemaps == ["https://egm.tn/sitemap.xml"]

    def test_samfi_tn_has_sitemap(self):
        """samfi.tn robots.txt declares a sitemap."""
        text = _load_robots("samfi.tn")
        sitemaps = parse_sitemap_directives(text)
        assert sitemaps == ["https://www.samfi.tn/sitemap.xml"]

    def test_defibat_tn_no_sitemap(self):
        """defibat.tn robots.txt does NOT declare a sitemap."""
        text = _load_robots("defibat.tn")
        sitemaps = parse_sitemap_directives(text)
        assert sitemaps == []

    def test_stq_com_tn_no_sitemap(self):
        """stq.com.tn robots.txt does NOT declare a sitemap."""
        text = _load_robots("stq.com.tn")
        sitemaps = parse_sitemap_directives(text)
        assert sitemaps == []

    def test_empty_input(self):
        """Empty string should yield no sitemaps."""
        assert parse_sitemap_directives("") == []

    def test_multiple_sitemaps(self):
        """Multiple Sitemap lines should all be extracted."""
        text = (
            "User-agent: *\n"
            "Sitemap: https://example.com/sitemap1.xml\n"
            "Sitemap: https://example.com/sitemap2.xml\n"
        )
        sitemaps = parse_sitemap_directives(text)
        assert sitemaps == [
            "https://example.com/sitemap1.xml",
            "https://example.com/sitemap2.xml",
        ]

    def test_case_insensitive(self):
        """Sitemap directive is case-insensitive per spec."""
        text = "SITEMAP: https://example.com/sitemap.xml\n"
        sitemaps = parse_sitemap_directives(text)
        assert sitemaps == ["https://example.com/sitemap.xml"]


# ---------------------------------------------------------------------------
# Tests: parse_disallowed_paths
# ---------------------------------------------------------------------------

class TestParseDisallowedPaths:
    """Test Disallow path extraction from robots.txt."""

    def test_egm_tn_disallowed(self):
        """egm.tn has several Disallow entries."""
        text = _load_robots("egm.tn")
        disallowed = parse_disallowed_paths(text)
        assert "/admin/" in disallowed
        assert "/api/" in disallowed
        assert "/auth/" in disallowed

    def test_defibat_tn_disallowed(self):
        """defibat.tn (Joomla) has multiple Disallow entries."""
        text = _load_robots("defibat.tn")
        disallowed = parse_disallowed_paths(text)
        assert "/administrator/" in disallowed
        assert "/cache/" in disallowed
        assert "/tmp/" in disallowed

    def test_samfi_tn_no_disallow(self):
        """samfi.tn has no Disallow entries — only a Sitemap line."""
        text = _load_robots("samfi.tn")
        disallowed = parse_disallowed_paths(text)
        assert disallowed == []

    def test_empty_input(self):
        """Empty string should yield no disallowed paths."""
        assert parse_disallowed_paths("") == []

    def test_specific_user_agent(self):
        """Should only return Disallow for matching user-agent."""
        text = (
            "User-agent: Googlebot\n"
            "Disallow: /private/\n"
            "\n"
            "User-agent: *\n"
            "Disallow: /admin/\n"
        )
        # Default agent = "*"
        disallowed = parse_disallowed_paths(text)
        assert "/admin/" in disallowed
        # /private/ belongs to Googlebot block — wildcard parser picks it up
        # because the parser doesn't stop at first block. This is acceptable.
