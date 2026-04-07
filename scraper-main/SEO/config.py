DEFAULT_CONFIG = {
    "OnPageAnalyzer": {
        "title_min_length": 20, "title_max_length": 70,
        "desc_min_length": 70, "desc_max_length": 160,
        "content_min_words": 300, "links_min_count": 5,
        "active_check_limit": 10, "url_max_length": 100, "url_max_depth": 4
    },
    "TechnicalSEOAnalyzer": {
        "enable_pagespeed_insights": True,
    },
    "ContentAnalyzer": {"top_n_keywords_count": 10, "spellcheck_language": "fr"},
    "ScoringModule": {
        "weights": {}, # Users can override specific scoring weights here
        "category_weights": {"OnPage": 0.40, "Technical": 0.30, "Content": 0.30}
    },
    "FullSiteAudit": {
        "max_pages": 100,
        "max_depth": 3,
        "respect_robots": True,
        "same_domain_only": True,
        "include_subdomains": False,
        "rate_limit_rps": 0.0
    },
    "Global": {"request_timeout": 10}
}