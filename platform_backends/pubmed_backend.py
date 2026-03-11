"""
PubMed backend — translate canonical strategy into PubMed queries.
"""

import requests
import xml.etree.ElementTree as ET


def build_block(label: str, mesh_block: str = None, tiab_term: str = None) -> str:
    """Build a PubMed query block for one concept."""
    mesh = mesh_block or ""
    tiab = f"({tiab_term})[Title/Abstract]" if tiab_term else ""

    if mesh and tiab:
        return f"(({mesh}) OR ({tiab}))"
    if mesh:
        return f"({mesh})"
    if tiab:
        return f"({tiab})"
    return ""


def count_results(query: str) -> int:
    """Return PubMed result count, or -1 if unavailable."""
    try:
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "xml",
            "retmax": 0,
        }
        response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params=params,
            timeout=10,
        )
        if response.status_code != 200:
            return -1
        root = ET.fromstring(response.text)
        count = root.find("Count")
        return int(count.text) if count is not None else -1
    except Exception:
        return -1


def build_pubmed_queries(strategy: dict) -> dict:
    """
    Translate canonical wide/narrow strategy into PubMed queries.
    """
    wide = strategy.get("wide", {})
    narrow = strategy.get("narrow", {})
    excluded = strategy.get("excluded", [])

    wide_elements = wide.get("elements", [])
    narrow_elements = narrow.get("elements", [])

    large_query = "\nAND ".join(
        build_block(
            e.get("label", "Concept"),
            mesh_block=e.get("mesh"),
            tiab_term=e.get("tiab"),
        )
        for e in wide_elements
    )

    strict_query = "\nAND ".join(
        build_block(
            e.get("label", "Concept"),
            mesh_block=e.get("mesh"),
            tiab_term=e.get("tiab"),
        )
        for e in narrow_elements
    )

    return {
        "large": {
            "query": large_query,
            "elements_used": wide.get("elements_used", []),
            "count": count_results(large_query),
        },
        "strict": {
            "query": strict_query,
            "elements_used": narrow.get("elements_used", []),
            "count": count_results(strict_query),
        },
        "excluded": excluded,
        "is_identical": strategy.get("is_identical", False),
    }


def count_geographic_scopes(base_query: str, geography: dict, geography_tiab: str = None) -> dict:
    """Count PubMed results by geography scope."""
    if not geography:
        return {}

    country = geography.get("country")
    region = geography.get("region")
    continent = geography.get("continent")

    scopes = {
        "global": {
            "label": "Monde entier (sans filtre géographique)",
            "query": base_query,
            "count": count_results(base_query),
        }
    }

    if geography_tiab:
        terms = [t.strip().strip('"') for t in geography_tiab.split(" OR ") if t.strip()]
        geo_blocks = [f'"{t}"[Title/Abstract]' for t in terms]
        query = base_query + f"\nAND ({' OR '.join(geo_blocks)})"
        scopes["geo_filter"] = {
            "label": "Filtre géographique",
            "query": query,
            "count": count_results(query),
        }

    if continent:
        query = base_query + f'\nAND ("{continent}"[Title/Abstract])'
        scopes["continent"] = {
            "label": continent,
            "query": query,
            "count": count_results(query),
        }

    if region:
        query = base_query + f'\nAND ("{region}"[Title/Abstract])'
        scopes["region"] = {
            "label": region,
            "query": query,
            "count": count_results(query),
        }

    if country:
        query = base_query + f'\nAND ("{country}"[Title/Abstract])'
        scopes["country"] = {
            "label": country,
            "query": query,
            "count": count_results(query),
        }

    return scopes
