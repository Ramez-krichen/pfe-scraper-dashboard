"""

Example usage for the page_classifier module with mock HTML inputs.
"""

from __future__ import annotations

from pathlib import Path

import sys


# Allow running this file directly (python page_classifier/example_usage.py)

# by ensuring the repo root is on sys.path.

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from page_classifier.job_builder import classify_page_from_html


def run_example(label: str, url: str, html: str) -> None:
    job = classify_page_from_html(url, html)

    print(f"\n=== {label} ===")

    print(job.to_dict())


def main():

    homepage = Path("page_classifier/mock_data/emtop/homepage.html").read_text(
        encoding="utf-8"
    )

    product_list = Path("page_classifier/mock_data/emtop/product-list.html").read_text(
        encoding="utf-8"
    )

    product_detail = Path(
        "page_classifier/mock_data/emtop/product-detail.html"
    ).read_text(encoding="utf-8")

    # run_example("Homepage", "https://brico-direct.tn/", homepage)

    # run_example("Product List", "https://brico-direct.tn/visseuses/", product_list)

    # run_example("Product Detail", "https://brico-direct.tn/visseuses/8452-visseuse-12v-li-ion-2x2ah-bosch-gsr120li-3165140955645.html", product_detail)

    run_example("Homepage", "https://emtoptunisie.com/", homepage)

    run_example(
        "Product List",
        "https://emtoptunisie.com/product-category/outils-sans-fil/ponceuse/",
        product_list,
    )

    run_example(
        "Product Detail",
        "https://emtoptunisie.com/product/polisseuse-150-42v-1b2ah-emtop-elap42151/",
        product_detail,
    )

    # run_example("Content List", "https://example.com/blog", content_list_html)


if __name__ == "__main__":
    main()
