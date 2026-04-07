"""Page classification and job routing for search-result URLs."""

from .classifier import classify_page

from .job_builder import classify_page_from_html
from .models import PageClassification, PageType, PaginationInfo, ScrapeJob

__all__ = [
    "classify_page",
    "build_job_from_html",
    "PageClassification",
    "PageType",
    "PaginationInfo",
    "ScrapeJob",
]
