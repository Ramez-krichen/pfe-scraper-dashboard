import pytest
from unittest.mock import patch, MagicMock
import httpx

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from site_crawler.sitemap_parser import classify_url
from site_crawler.models import UrlCategory

class TestClassifyUrl:

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
        assert classify_url(url) == UrlCategory.PRODUCT




    # --- Category patterns ---
    @pytest.mark.parametrize("url", [
        # "https://example.com/category/electronics",
        # "https://example.com/categories/tools",
        # "https://shop.com/collection/summer-2025/",
        # "https://store.com/collections/new-arrivals/",
        "https://example.com/catalogue/power-tools/",
        "https://example.com/14-velos/",
        "https://bricola.tn/419-bouteille-et-bidon-de-conservation-"
        'https://www.technoquip-tn.com/nos-marques/'
        'https://www.technoquip-tn.com/shop/'
    ])
    def test_category_urls(self, url):
        assert classify_url(url) == UrlCategory.CATEGORY




    # --- Content/info patterns are grouped with CATEGORY ---
    @pytest.mark.parametrize("url", [
        ("https://example.com/about", UrlCategory.ABOUT),
        ("https://example.com/about-us", UrlCategory.ABOUT),
        ("https://example.com/qui-sommes-nous", UrlCategory.ABOUT),
        ("https://example.com/à-propos", UrlCategory.ABOUT),
        ("https://example.com/contact", UrlCategory.CONTACT),
        ("https://example.com/contact-v2", UrlCategory.CONTACT),
        ("https://example.com/contactez-nous", UrlCategory.CONTACT),
        ("https://example.com/events/spring-sale", UrlCategory.EVENT),
        ("https://example.com/blogs/company-news", UrlCategory.BLOG),
        ("https://example.com/accueil", UrlCategory.CATEGORY),
        ("https://example.com/actualité/promotions", UrlCategory.NEWS),
        ("https://example.com/promotions", UrlCategory.PROMO),
        ('https://www.technoquip-tn.com/blog-2/', UrlCategory.BLOG),
        ('https://www.technoquip-tn.com/blog-2/page/2/', UrlCategory.BLOG),
        ('https://www.technoquip-tn.com/conseils-masque-respiratoire-tunisie/', UrlCategory.FAQ),
        ('https://www.technoquip-tn.com/faq/', UrlCategory.FAQ),
        ('https://www.technoquip-tn.com/astuce-longevite-du-tuyau-flexible/', UrlCategory.FAQ),
        ('https://www.technoquip-tn.com/promotions/', UrlCategory.PROMO),
        ('https://www.technoquip-tn.com/conditions-de-livraisons/', UrlCategory.RULES),
        ('https://www.technoquip-tn.com/a-propos-de-nous/', UrlCategory.ABOUT),
        ('https://www.technoquip-tn.com/politique-de-confidentialite/', UrlCategory.RULES),
        ('https://www.technoquip-tn.com/conditions-generales-de-vente/', UrlCategory.RULES),
        ('https://www.technoquip-tn.com/conditions-generales-d-utilisation/', UrlCategory.RULES),
        ('https://www.technoquip-tn.com/conditions-generales-de-vente/', UrlCategory.RULES),
    ])
    def test_content_urls_are_categories(self, url):
        url, expected = url
        res = classify_url(url)
        assert res == expected

    @pytest.mark.parametrize("url", [
        "https://example.com/",
    ])
    def test_other_urls(self, url):
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
