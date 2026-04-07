from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
import sys


# Allow running this file directly (python page_classifier/example_usage.py)

# by ensuring the repo root is on sys.path.

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from extractors.product_list import extract_product_list_items

from page_classifier.job_builder import classify_page_from_html


def run_example(label: str, url: str, html: str) -> None:

    job = classify_page_from_html(url, html)

    print(f"\n=== {label} ===")

    print(job.to_dict())


def main():

    product_list = Path("extractors/mock_data/emtop/product-list.html").read_text(
        encoding="utf-8"
    )

    products = extract_product_list_items(
        product_list, "https://emtoptunisie.com/product-category/outils-sans-fil/"
    )
    return products


if __name__ == "__main__":
    main()
