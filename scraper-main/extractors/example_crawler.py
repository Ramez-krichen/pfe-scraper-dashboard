"""
example_usage.py — Demonstrates the site_crawler URL discovery component.

Usage:
    cd c:/Users/arp/Desktop/scraper/scraper
    python -m extractors.example_crawler
"""
import logging
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent.parent))

from extractors import discover_urls

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def main():
    # Example: crawl egm.tn (has robots.txt + sitemap)
    # comptoir
    # brico-direct
    # egm
    # brico
    # bps
    # sqes
    # qfm-quincaillerie
    # arkan -----
    # sbcom
    # totaltools
    # sovaq (crawl)
    # espace2f (crawl)
    # ceg (crawl)
    target_url = "http://127.0.0.1:8080"

    print(f"\n{'='*60}")
    print(f"  Site Crawler — URL Discovery")
    print(f"  Target: {target_url}")
    print(f"{'='*60}\n")

    with sync_playwright() as playwright:
        # sb = sb_cdp.Chrome(headless=True, locale="fr-TN")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="fr-TN")
        page = context.new_page()
        # result = discover_urls(target_url, sb)
        result = discover_urls(target_url, page)

        print(f"\n{'='*60}")
        print(f"  Results")
        print(f"{'='*60}")
        print(f"  Source:            {result.source.value}")
        print(f"  Sitemaps found:    {result.sitemap_urls_found}")
        print(f"  Disallowed paths:  {len(result.disallowed_paths)}")
        print(f"  Total URLs:        {sum(len(v) for v in result.urls.values())}")
        print(f"  Category URLs:     {len(result.urls['category'])}")
        print(f"  Product URLs:      {len(result.urls['product'])}")
        print(f"  Other URLs:        {len(result.urls['other'])}")

        if result.error:
            print(f"  ERROR:             {result.error}")

        # Print a sample of category URLs
        if result.urls['category']:
            print(f"\n  -- Category URLs (first 10) --")
            for u in result.urls['category'][:10]:
                print(f"    {u.url}")

        # Print a sample of product URLs
        if result.urls['product']:
            print(f"\n  -- Product URLs (first 10) --")
            for u in result.urls['product'][:10]:
                print(f"    {u.url}")

        print()
        # sb.close_active_tab()
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
