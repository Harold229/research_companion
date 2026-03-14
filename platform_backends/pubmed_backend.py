"""
PubMed backend — translate canonical strategy into PubMed queries.
"""

import re
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


def _extract_keywords(article) -> list:
    keywords = []
    for keyword in article.findall(".//KeywordList/Keyword"):
        text = "".join(keyword.itertext()).strip()
        if text and text not in keywords:
            keywords.append(text)
        if len(keywords) >= 8:
            break
    return keywords


def _extract_mesh_terms(article) -> list:
    mesh_terms = []
    for heading in article.findall(".//MeshHeadingList/MeshHeading"):
        descriptor = _safe_text(heading, "DescriptorName")
        if descriptor and descriptor not in mesh_terms:
            mesh_terms.append(descriptor)
        if len(mesh_terms) >= 8:
            break
    return mesh_terms


def _parse_pubmed_articles(fetch_root, rank_map: dict = None) -> list:
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
            "keywords": _extract_keywords(article),
            "mesh_terms": _extract_mesh_terms(article),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            "pubmed_rank": (rank_map or {}).get(pmid),
        })
    if rank_map:
        articles.sort(key=lambda item: (rank_map.get(item.get("pmid"), 999999), item.get("title", "")))
    return articles


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


def _split_tiab_terms(value: str) -> list:
    text = str(value or "").strip()
    if not text:
        return []
    parts = re.split(r"\s+OR\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _format_tiab_term(term: str) -> str:
    cleaned = str(term or "").strip()
    if not cleaned:
        return ""
    if "[" in cleaned and "]" in cleaned:
        return cleaned

    if cleaned.startswith('"') and cleaned.endswith('"'):
        quoted = cleaned
    elif " " in cleaned or "-" in cleaned:
        quoted = f'"{cleaned}"'
    else:
        quoted = cleaned

    return f"{quoted}[tiab]"


def build_block(label: str, mesh_block: str = None, tiab_term: str = None) -> str:
    """Build a PubMed query block for one concept."""
    mesh = mesh_block or ""
    tiab_terms = [_format_tiab_term(term) for term in _split_tiab_terms(tiab_term)]
    tiab_terms = [term for term in tiab_terms if term]
    tiab = f"({' OR '.join(tiab_terms)})" if tiab_terms else ""

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
        rank_map = {pmid: index for index, pmid in enumerate(ids, start=1)}

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
        return _parse_pubmed_articles(fetch_root, rank_map=rank_map)
    except Exception:
        return []


def fetch_cited_articles(pmid: str, max_results: int = 12) -> list:
    """Return a lightweight list of references cited by a PubMed article when available."""
    if not str(pmid or "").strip():
        return []

    try:
        link_response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi",
            params={
                "dbfrom": "pubmed",
                "db": "pubmed",
                "id": str(pmid).strip(),
                "linkname": "pubmed_pubmed_refs",
                "retmode": "xml",
            },
            timeout=10,
        )
        if link_response.status_code != 200:
            return []

        link_root = ET.fromstring(link_response.text)
        linked_ids = [node.text for node in link_root.findall(".//LinkSetDb/Link/Id") if node.text]
        if not linked_ids:
            return []

        fetch_response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={
                "db": "pubmed",
                "id": ",".join(linked_ids[:max_results]),
                "retmode": "xml",
            },
            timeout=10,
        )
        if fetch_response.status_code != 200:
            return []

        fetch_root = ET.fromstring(fetch_response.text)
        return _parse_pubmed_articles(fetch_root)
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
        geo_blocks = [f'"{t}"[tiab]' for t in terms]
        query = base_query + f"\nAND ({' OR '.join(geo_blocks)})"
        scopes["geo_filter"] = {
            "label": "Filtre géographique",
            "query": query,
            "count": count_results(query),
        }

    if continent:
        query = base_query + f'\nAND ("{continent}"[tiab])'
        scopes["continent"] = {
            "label": continent,
            "query": query,
            "count": count_results(query),
        }

    if region:
        query = base_query + f'\nAND ("{region}"[tiab])'
        scopes["region"] = {
            "label": region,
            "query": query,
            "count": count_results(query),
        }

    if country:
        query = base_query + f'\nAND ("{country}"[tiab])'
        scopes["country"] = {
            "label": country,
            "query": query,
            "count": count_results(query),
        }

    return scopes
