PRODUCT_HEURISTICS = [
    'div[class*="product"]',
    'li[class*="product"]',
    ".product-item",
    ".grid-item",
    ".product-card",
    ".item",
]

LOAD_MORE_SELECTORS = [
    'button[class*="load"]',
    'button[class*="more"]',
    'button[id*="load"]',
    'a[class*="load-more"]',
]

LOAD_MORE_TEXTS = [
    "load",
    "charger",
    "plus",
    "more",
    "afficher plus",
    "show more",
]

URL_PARAM_CANDIDATES = ["page", "p"]

PAGINATION_NAV_SELECTORS = [
    "nav.pagination a",
    "ul.pagination a",
    ".page-numbers a",
    ".pagination-container a",
    ".pages-items a",
]

NEXT_BUTTON_SELECTORS = [
    'a[rel="next"]',
    'li[class*="next"] a',
    'a[class*="next"]',
    '[aria-label*="ext"]',
    '[aria-label*="uivant"]',
]

WAIT_SEC_BETWEEN_PAGE_SCRAPE = (45.0, 60.0)
PAGE_LOAD_WAIT_SEC = (2.0, 4.0)
WAIT_SEC_BEFORE_ACTION = (4.0, 6.0)

MAX_STABLE_ATTEMPTS = 3
NO_CHANGE_LIMIT = 3
