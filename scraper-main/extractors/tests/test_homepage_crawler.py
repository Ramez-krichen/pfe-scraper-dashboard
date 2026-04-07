"""
test_homepage_crawler.py — Unit tests for the homepage_crawler fallback path.

Uses mocked HTML content to test link extraction and classification
without requiring a browser or network access.
"""
import pytest
from unittest.mock import MagicMock, patch

from extractors.homepage import crawl_homepage
from extractors.models import UrlCategory, DiscoverySource


# ---------------------------------------------------------------------------
# Sample HTML
# ---------------------------------------------------------------------------

SAMPLE_HOMEPAGE_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Test Store</title></head>
<body>
  <nav>
    <a href="/category/electronics">Electronics</a>
    <a href="/category/tools">Tools</a>
    <a href="/collection/new-arrivals">New Arrivals</a>
  </nav>
  <main>
    <a href="/product/widget-123">Cool Widget</a>
    <a href="/produit/lampe-456">Lampe LED</a>
    <a href="/about">About Us</a>
    <a href="/contact">Contact</a>
  </main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCrawlHomepage:
    """Test the homepage fallback crawler."""

    def _make_mock_page(self, html: str) -> MagicMock:
        """Create a mock Playwright page instance."""
        page = MagicMock()
        # sb.get_page_source.return_value = html
        page.content.return_value = html
        return page

    @patch("extractors.homepage.extract_homepage_urls")
    def test_delegates_to_extractor(self, mock_extract):
        """Should call extract_homepage_urls with the page source."""
        from extractors.models import HomepageUrls

        mock_extract.return_value = HomepageUrls(
            url="https://test.com",
            result={
                "category": ["https://test.com/category/a", "https://test.com/about"],
                "product": ["https://test.com/product/b"],
                "other": [],
            }
        )

        page = self._make_mock_page(SAMPLE_HOMEPAGE_HTML)
        result = crawl_homepage("https://test.com", page)

        # sb.open.assert_called_once_with("https://test.com")
        page.goto.assert_called_once_with("https://test.com")
        mock_extract.assert_called_once()

        assert result.source == DiscoverySource.HOMEPAGE
        assert len(result.urls.get("category", [])) == 2
        assert len(result.urls.get("product", [])) == 1
        assert len(result.urls.get("other", [])) == 0

    def test_empty_html_returns_error(self):
        """Empty page source should set an error on the result."""
        page = self._make_mock_page("")
        result = crawl_homepage("https://test.com", page)

        assert result.error is not None
        assert "empty" in result.error.lower()
        assert result.urls == []

    def test_exception_is_caught(self):
        """Browser exceptions should be caught and reported as errors."""
        page = MagicMock()
        # sb.open.side_effect = Exception("Connection refused")
        page.goto.side_effect = Exception("Connection refused")

        result = crawl_homepage("https://test.com", page)

        assert result.error is not None
        assert "Connection refused" in result.error
        assert result.urls == []

    @patch("extractors.homepage.extract_homepage_urls")
    def test_url_categories_correct(self, mock_extract):
        """Discovered URLs should have correct category labels."""
        from extractors.models import HomepageUrls

        mock_extract.return_value = HomepageUrls(
            url="https://shop.com",
            result={
                "category": [
                    "https://shop.com/category/electronics",
                    "https://shop.com/category/tools",
                ],
                "product": [
                    "https://shop.com/product/widget-123",
                ],
                "other": [],
            }
        )

        page = self._make_mock_page("<html></html>")
        result = crawl_homepage("https://shop.com", page)

        categories = result.urls.get("category", [])
        products = result.urls.get("product", [])
        assert len(categories) == 2
        assert all(u.category == UrlCategory.CATEGORY for u in categories)
        assert len(products) == 1
        assert products[0].category == UrlCategory.PRODUCT

    def test_multilingual_info_links_are_other(self):
        """Homepage info/content links should be classified as OTHER."""
        html = """\
<!DOCTYPE html>
<html>
<body>
  <nav>
    <a href="/qui-sommes-nous">Qui sommes nous</a>
    <a href="/contactez-nous">Contact</a>
    <a href="/evenements/salon-2026">Evenements</a>
    <a href="/blogs/actualite-marque">Blog</a>
    <a href="/actualite/promotions">Actualité</a>
    <a href="/promotions">Promotions</a>
    <a href="/accueil">Accueil</a>
    <a href="/category/outillage">Outillage</a>
    <a href="/product/perceuse-123">Perceuse</a>
  </nav>
</body>
</html>
"""
        page = self._make_mock_page(html)
        result = crawl_homepage("https://shop.com", page)

        categories = result.urls.get("category", [])
        products = result.urls.get("product", [])
        others = result.urls.get("other", [])
        
        category_urls = {u.url for u in categories}
        assert "https://shop.com/qui-sommes-nous" in category_urls
        assert "https://shop.com/contactez-nous" in category_urls
        assert "https://shop.com/evenements/salon-2026" in category_urls
        assert "https://shop.com/blogs/actualite-marque" in category_urls
        assert "https://shop.com/actualite/promotions" in category_urls
        assert "https://shop.com/promotions" in category_urls
        assert "https://shop.com/accueil" in category_urls
        assert "https://shop.com/category/outillage" in category_urls
        assert {u.url for u in products} == {"https://shop.com/product/perceuse-123"}
        assert len(others) == 0
