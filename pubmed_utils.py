"""
Transitional wrappers around the dedicated PubMed backend.
"""

from platform_backends.pubmed_backend import build_pubmed_queries
from platform_backends.pubmed_backend import count_geographic_scopes
from platform_backends.pubmed_backend import count_results


__all__ = [
    "build_pubmed_queries",
    "count_geographic_scopes",
    "count_results",
]
