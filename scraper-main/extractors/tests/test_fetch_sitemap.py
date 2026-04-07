import pytest
from unittest.mock import patch, MagicMock
import httpx
from site_crawler.sitemap_parser import fetch_sitemap

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
