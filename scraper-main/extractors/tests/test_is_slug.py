import pytest
from site_crawler.sitemap_parser import _is_slug

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
