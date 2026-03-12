"""
PubMed backend — translate canonical strategy into PubMed queries.
"""

import requests
import xml.etree.ElementTree as ET


def _safe_text(element, path: str, default: str = "") -> str:
    if element is None:
        return default
    node = element.find(path)
    if node is None:
        return default
    text = "".join(node.itertext()).strip()
    return text or default


def _extract_pub_year(article) -> str:
    journal_issue = article.find(".//JournalIssue/PubDate")
    if journal_issue is None:
        return ""

    year = _safe_text(journal_issue, "Year")
    if year:
        return year

    medline_date = _safe_text(journal_issue, "MedlineDate")
    if medline_date:
        return medline_date[:4]

    return ""


def _extract_authors(article) -> list:
    authors = []
    for author in article.findall(".//AuthorList/Author"):
        last_name = _safe_text(author, "LastName")
        initials = _safe_text(author, "Initials")
        collective_name = _safe_text(author, "CollectiveName")
        if collective_name:
            authors.append(collective_name)
        elif last_name:
            authors.append(f"{last_name} {initials}".strip())
        if len(authors) >= 3:
            break
    return authors


def _extract_doi(article) -> str:
    for article_id in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
        if article_id.attrib.get("IdType") == "doi":
            text = "".join(article_id.itertext()).strip()
            if text:
                return text
    return ""


def build_pubmed_date_filter(start_year: str = "", end_year: str = "") -> str:
    """Build a PubMed publication date range filter."""
    start = str(start_year or "").strip()
    end = str(end_year or "").strip()

    if not start and not end:
        return ""

    start_bound = f"{start}/01/01" if start else "1000/01/01"
    end_bound = f"{end}/12/31" if end else "3000/12/31"
    return f'("{start_bound}"[Date - Publication] : "{end_bound}"[Date - Publication])'


def apply_pubmed_date_filter(query: str, start_year: str = "", end_year: str = "") -> str:
    """Apply a publication date filter to an existing PubMed query."""
    if not query:
        return ""

    date_filter = build_pubmed_date_filter(start_year, end_year)
    if not date_filter:
        return query

    return f"({query})\nAND {date_filter}"


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


def fetch_articles(query: str, max_results: int = 12) -> list:
    """Return a lightweight list of PubMed articles for a query."""
    if not query:
        return []

    try:
        search_response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": query,
                "retmode": "xml",
                "retmax": max_results,
                "sort": "relevance",
            },
            timeout=10,
        )
        if search_response.status_code != 200:
            return []

        search_root = ET.fromstring(search_response.text)
        ids = [node.text for node in search_root.findall(".//IdList/Id") if node.text]
        if not ids:
            return []

        fetch_response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={
                "db": "pubmed",
                "id": ",".join(ids),
                "retmode": "xml",
            },
            timeout=10,
        )
        if fetch_response.status_code != 200:
            return []

        fetch_root = ET.fromstring(fetch_response.text)
        articles = []
        for article in fetch_root.findall(".//PubmedArticle"):
            pmid = _safe_text(article, ".//MedlineCitation/PMID")
            title = _safe_text(article, ".//Article/ArticleTitle")
            abstract_parts = [
                "".join(node.itertext()).strip()
                for node in article.findall(".//Article/Abstract/AbstractText")
                if "".join(node.itertext()).strip()
            ]
            articles.append({
                "pmid": pmid,
                "doi": _extract_doi(article),
                "title": title,
                "abstract": " ".join(abstract_parts),
                "journal": _safe_text(article, ".//Journal/Title"),
                "year": _extract_pub_year(article),
                "authors": _extract_authors(article),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            })

        return articles
    except Exception:
        return []


def build_pubmed_queries(strategy: dict) -> dict:
    """
    Translate canonical wide/narrow strategy into PubMed queries.
    """
    wide = strategy.get("wide", {})
    narrow = strategy.get("narrow", {})
    excluded = strategy.get("excluded", [])

    wide_elements = wide.get("elements", [])
    narrow_elements = narrow.get("elements", [])

    large_blocks = [
        build_block(
            e.get("label", "Concept"),
            mesh_block=e.get("mesh"),
            tiab_term=e.get("tiab"),
        )
        for e in wide_elements
    ]
    large_query = "\nAND ".join(block for block in large_blocks if block)

    strict_blocks = [
        build_block(
            e.get("label", "Concept"),
            mesh_block=e.get("mesh"),
            tiab_term=e.get("tiab"),
        )
        for e in narrow_elements
    ]
    strict_query = "\nAND ".join(block for block in strict_blocks if block)

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
