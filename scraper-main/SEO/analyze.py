from datetime import datetime
import json
import os
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from SEO.config import DEFAULT_CONFIG
from SEO.content.analyzer import ContentAnalyzer
from SEO.on_page.analyzer import OnPageAnalyzer
from SEO.scoring.analyzer import ScoringModule
from SEO.technical.analyzer import TechnicalSEOAnalyzer


def normalize_url(url):
    if not url.startswith(('http://', 'https://')):
        return 'http://' + url
    return url

def save_report_to_file(domain, report, output_format: str = "json", filename_prefix="seo_report"): # Renamed for clarity
    if not os.path.exists("reports"):
        os.makedirs("reports")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_domain_name = domain.replace(".", "_")
    filename = f"reports/{filename_prefix}_{safe_domain_name}_{timestamp}.{output_format}"
    try:
        with open(filename, "w") as f:
            if output_format == "json": json.dump(report, f, indent=4)
            else: f.write(str(report))
        print(f"Report saved to {filename}")
        return filename
    except IOError as e:
        print(f"Error saving report: {e}")
        return None

def analyze_seo(target_url: str, html, response, metrics, assets: dict) -> dict:
    url = normalize_url(target_url)
    domain = urlparse(url).netloc
    soup = BeautifulSoup(html, "html.parser") if html else None
    report = {
        "analysis_timestamp": datetime.now().isoformat(),
        "target_url": url,
        "domain": domain,
        "seo_attributes": {}
    }

    content_cfg = DEFAULT_CONFIG.get("ContentAnalyzer", {}).copy()
    on_page_cfg = DEFAULT_CONFIG.get("OnPageAnalyzer", {}).copy()
    tech_cfg = DEFAULT_CONFIG.get("TechnicalSEOAnalyzer", {}).copy()
    scoring_cfg = DEFAULT_CONFIG.get("ScoringModule", {})
    modules = [OnPageAnalyzer(soup, config=on_page_cfg), TechnicalSEOAnalyzer(html, soup, response, metrics, assets, config=tech_cfg), ContentAnalyzer(soup, config=content_cfg)]
    scoring_module_instance = ScoringModule(config=scoring_cfg)

    for module in modules:
        try:
            # print(f"Running module: {module.__class__.__name__}...") # Verbose
            module_results = module.analyze(url)
            report["seo_attributes"].update(module_results)
            # print(f"Module {module.__class__.__name__} completed.") # Verbose
        except Exception as e:
            print(f"Error running module {module.__class__.__name__}: {e}")
            report["seo_attributes"][module.__class__.__name__ + "_error"] = str(e)

    try:
        # print(f"Running module: {scoring_module_instance.__class__.__name__}...") # Verbose
        scoring_data = scoring_module_instance.analyze(url=url, full_report_data=report["seo_attributes"])
        report["seo_attributes"].update(scoring_data)
        # print(f"Module {scoring_module_instance.__class__.__name__} completed.") # Verbose
    except Exception as e:
        print(f"Error running module {scoring_module_instance.__class__.__name__}: {e}")
        report["seo_attributes"][scoring_module_instance.__class__.__name__ + "_error"] = str(e)

    return report