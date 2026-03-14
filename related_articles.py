"""
Construction simple d'une requête d'articles connexes à partir d'un article choisi.
"""

import re


STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "among", "using",
    "study", "studies", "article", "articles", "dans", "pour", "avec", "chez",
    "une", "des", "les", "sur", "par", "est", "sont", "de", "du", "la", "le",
}

WEAK_CONTEXT_TERMS = {
    "africa", "asia", "europe", "hospital", "registry", "register", "database",
    "cohort", "cohorts", "public", "health", "administrative", "national",
    "italian", "french", "danish",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _tokenize(text: str) -> list:
    tokens = re.findall(r"\b[a-z0-9][a-z0-9\-]{2,}\b", _normalize(text))
    return [token for token in tokens if token not in STOPWORDS]


def extract_related_signals(
    article: dict,
    subject_text: str = "",
    max_text_terms: int = 5,
    max_mesh_terms: int = 3,
) -> dict:
    title = article.get("title", "")
    abstract = article.get("abstract", "")
    keywords = [str(item).strip() for item in (article.get("keywords") or []) if str(item).strip()]
    mesh_terms = [str(item).strip() for item in (article.get("mesh_terms") or []) if str(item).strip()]
    subject_tokens = set(_tokenize(subject_text))

    text_terms = []
    for source in [keywords, _tokenize(title), _tokenize(abstract)]:
        for term in source:
            normalized_term = _normalize(term)
            term_tokens = set(_tokenize(normalized_term))
            if not normalized_term or normalized_term in text_terms:
                continue
            if subject_tokens:
                if term_tokens and not (term_tokens & subject_tokens):
                    continue
                if normalized_term in WEAK_CONTEXT_TERMS:
                    continue
            if term:
                text_terms.append(term)
            if len(text_terms) >= max_text_terms:
                break
        if len(text_terms) >= max_text_terms:
            break

    aligned_mesh_terms = []
    for term in mesh_terms:
        normalized_term = _normalize(term)
        term_tokens = set(_tokenize(normalized_term))
        if subject_tokens:
            if term_tokens and not (term_tokens & subject_tokens):
                continue
            if normalized_term in WEAK_CONTEXT_TERMS:
                continue
        if term not in aligned_mesh_terms:
            aligned_mesh_terms.append(term)
        if len(aligned_mesh_terms) >= max_mesh_terms:
            break

    return {
        "text_terms": text_terms[:max_text_terms],
        "mesh_terms": aligned_mesh_terms[:max_mesh_terms],
    }


def build_related_articles_query(base_query: str, article: dict, subject_text: str = "") -> str:
    if not base_query:
        return ""

    signals = extract_related_signals(article, subject_text=subject_text)
    clauses = []

    for term in signals.get("mesh_terms", []):
        clauses.append(f'"{term}"[MeSH Terms]')
    for term in signals.get("text_terms", []):
        clauses.append(f'"{term}"[tiab]')

    if not clauses:
        return base_query

    return f"({base_query})\nAND ({' OR '.join(clauses)})"
