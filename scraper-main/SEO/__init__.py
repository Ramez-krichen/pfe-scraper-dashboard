# modules/__init__.py
# This file makes the 'modules' directory a Python package.

# modules/__init__.py
# This file makes the 'modules' directory a Python package.

# You can optionally import module classes here to make them available
# directly from the package, e.g.:
from .on_page import OnPageAnalyzer
from .technical import TechnicalSEOAnalyzer
from .content import ContentAnalyzer
from .scoring import ScoringModule

# For now, we'll keep it simple and import them directly in main.py
