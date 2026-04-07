"""
product_list.py — BaseExtractor ABC + HeuristicExtractor + PlatformHintAdapter.

This module hosts product list extraction logic and can be used directly
or via ProductListDetector.
"""
from __future__ import annotations

from typing import List
from playwright.async_api import Page

async def extract_product_list_items(
    page: Page, extract_from_schema_org: bool = False
) -> List[str]:
    if extract_from_schema_org:
        urls = []
        schemas = await page.evaluate("""() => Array.from(document.querySelectorAll("script[type='application/ld+json']")).map(src => JSON.parse(src.innerText))""")
        for schema in schemas:
            if schema.get("@type") == "ItemList" and "itemListElement" in schema:
                items = []
                for element in schema["itemListElement"]:
                    if isinstance(element, dict):
                        url = element.get("url") or element.get("item", {}).get("url")
                        if url:
                            items.append(url)
                if items:
                    return items
            if schema.get("@type") == "Product":
                url = schema.get("url")
                if url:
                    urls.append(url)
                elif "offers" in schema and isinstance(schema["offers"], dict):
                    url = schema["offers"].get("url")
                    if url:
                        urls.append(url)
        if urls:
            return urls


    links = await page.evaluate("""
() => {
    function isElementInViewport(el) {
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    let pattern = new RegExp('(ajouter|acheter|lire la suite|fiche technique|plus de détail|add to cart|sold out|sur command|chariot|feuilleter|ref|réf|stock|[0-9+\\\\,0-9+] (TND|DT))', 'i');

    let anchors = document.querySelectorAll("a[href], button, span");
    let res = [];

    anchors.forEach(el => {
        if ((pattern.test(el.innerText) || pattern.test(el.textContent)) && isElementInViewport(el)) {
            res.push(el);
        }
    });

    let links = new Set();

    res.forEach(el => {
        if (/fiche technique|feuilleter|plus de détail/i.test(el.textContent)) {
            links.add(el.getAttribute("href"));
            return;
        }

        let parent = el.parentElement;
        let url = [];

        while (parent && parent.getBoundingClientRect().width + 50 < window.innerWidth && url.length === 0) {
            let anchorAsHeading = parent.querySelector("a[title]");

            if (anchorAsHeading) {
                if (
                    anchorAsHeading.getAttribute("href") !== "#" &&
                    anchorAsHeading.getAttribute("title") === anchorAsHeading.innerText
                ) {
                    url = [anchorAsHeading];
                    break;
                }
            }

            url = parent.querySelectorAll(
                "h1 a, h2 a, h3 a, h4 a, h5 a, h6 a, a[title]:has(img), a[href]:has(img[title])"
            );

            parent = parent.parentElement;
        }

        url.forEach(u => links.add(u.getAttribute("href")));
    });

    return Array.from(links);
}
""")
    return links
