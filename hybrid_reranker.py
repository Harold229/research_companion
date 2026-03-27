"""
Reranking hybride léger pour remonter les articles centraux au sujet exact.
"""

from collections import Counter
from difflib import SequenceMatcher
import math
import re


STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "among", "using",
    "use", "used", "study", "studies", "paper", "papers", "article", "articles",
    "dans", "pour", "avec", "chez", "une", "des", "les", "sur", "par", "est",
    "sont", "and", "or", "of", "in", "on", "to", "by", "de", "du", "la", "le",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _tokenize(text: str) -> list:
    tokens = re.findall(r"\b[a-z0-9][a-z0-9\-]{2,}\b", _normalize(text))
    return [token for token in tokens if token not in STOPWORDS]


def _token_overlap(anchor_tokens: list, text_tokens: list) -> float:
    if not anchor_tokens or not text_tokens:
        return 0.0
    anchor_set = set(anchor_tokens)
    text_set = set(text_tokens)
    return len(anchor_set & text_set) / max(len(anchor_set), 1)


def _matching_tokens(anchor_tokens: list, text_tokens: list) -> list:
    if not anchor_tokens or not text_tokens:
        return []
    text_set = set(text_tokens)
    return [token for token in anchor_tokens if token in text_set]


def _bigram_overlap(anchor_tokens: list, text_tokens: list) -> float:
    if len(anchor_tokens) < 2 or len(text_tokens) < 2:
        return 0.0
    anchor_bigrams = set(zip(anchor_tokens, anchor_tokens[1:]))
    text_bigrams = set(zip(text_tokens, text_tokens[1:]))
    if not anchor_bigrams:
        return 0.0
    return len(anchor_bigrams & text_bigrams) / len(anchor_bigrams)


def _char_ngram_counter(text: str, n: int = 3) -> Counter:
    cleaned = re.sub(r"\s+", " ", _normalize(text))
    if len(cleaned) < n:
        return Counter()
    return Counter(cleaned[index:index + n] for index in range(len(cleaned) - n + 1))


def _cosine_similarity(counter_a: Counter, counter_b: Counter) -> float:
    if not counter_a or not counter_b:
        return 0.0
    common = set(counter_a) & set(counter_b)
    numerator = sum(counter_a[key] * counter_b[key] for key in common)
    denom_a = math.sqrt(sum(value * value for value in counter_a.values()))
    denom_b = math.sqrt(sum(value * value for value in counter_b.values()))
    if not denom_a or not denom_b:
        return 0.0
    return numerator / (denom_a * denom_b)


def _title_exactness(anchor_text: str, title_text: str, anchor_tokens: list, title_tokens: list) -> float:
    anchor = _normalize(anchor_text)
    title = _normalize(title_text)
    if not anchor or not title:
        return 0.0

    phrase_match = 1.0 if anchor in title else 0.0
    sequence_ratio = SequenceMatcher(None, anchor, title).ratio()
    bigram_score = _bigram_overlap(anchor_tokens, title_tokens)
    return max(phrase_match, (sequence_ratio * 0.55) + (bigram_score * 0.45))


def rerank_articles_hybrid(articles: list, subject_text: str, focus_text: str = "") -> dict:
    anchor_text = _normalize(subject_text)
    focus = _normalize(focus_text)
    anchor_tokens = _tokenize(anchor_text)
    focus_tokens = _tokenize(focus)
    anchor_vector = _char_ngram_counter(anchor_text)

    reranked = []
    for article in articles or []:
        title = article.get("title", "")
        abstract = article.get("abstract", "")
        title_tokens = _tokenize(title)
        abstract_tokens = _tokenize(abstract)
        combined_text = f"{title} {abstract}".strip()
        title_matches = _matching_tokens(anchor_tokens, title_tokens)
        abstract_matches = _matching_tokens(anchor_tokens, abstract_tokens)

        title_overlap = _token_overlap(anchor_tokens, title_tokens)
        abstract_overlap = _token_overlap(anchor_tokens, abstract_tokens)
        exact_title = _title_exactness(anchor_text, title, anchor_tokens, title_tokens)
        semantic_similarity = _cosine_similarity(anchor_vector, _char_ngram_counter(combined_text))
        focus_overlap = _token_overlap(focus_tokens, title_tokens + abstract_tokens) if focus_tokens else 0.0

        penalty = 0.0
        if title_overlap < 0.2 and exact_title < 0.25 and abstract_overlap < 0.35:
            penalty += 0.12
        elif title_overlap < 0.35 and exact_title < 0.35 and abstract_overlap < 0.5:
            penalty += 0.06

        hybrid_score = (
            (exact_title * 0.34) +
            (title_overlap * 0.26) +
            (abstract_overlap * 0.16) +
            (semantic_similarity * 0.18) +
            (focus_overlap * 0.12) -
            penalty
        )
        hybrid_score = max(0.0, hybrid_score)

        reasons = []
        if exact_title >= 0.72 or (exact_title >= 0.64 and title_overlap >= 0.58):
            reasons.append("titre quasi directement aligné avec le sujet")
        elif exact_title >= 0.62:
            reasons.append("titre très proche du sujet exact")
        elif title_overlap >= 0.45:
            reasons.append("reprend plusieurs termes centraux dans le titre")
        if title_matches:
            reasons.append(f"concepts visibles dans le titre : {', '.join(title_matches[:4])}")
        elif abstract_matches:
            reasons.append(f"concepts surtout portés par l'abstract : {', '.join(abstract_matches[:4])}")
        if semantic_similarity >= 0.34:
            reasons.append("abstract proche du sujet complet")
        if focus_overlap >= 0.4 and focus_tokens:
            reasons.append("correspond aussi à l'angle de lecture demandé")
        if penalty >= 0.1:
            reasons.append("reste plus général que le sujet exact")

        reranked.append({
            **article,
            "hybrid_score": round(hybrid_score, 4),
            "hybrid_signals": {
                "title_overlap": round(title_overlap, 4),
                "abstract_overlap": round(abstract_overlap, 4),
                "exact_title": round(exact_title, 4),
                "semantic_similarity": round(semantic_similarity, 4),
                "focus_overlap": round(focus_overlap, 4),
                "penalty": round(penalty, 4),
                "title_matches": title_matches[:6],
                "abstract_matches": abstract_matches[:6],
            },
            "hybrid_reasons": reasons,
        })

    reranked = sorted(
        reranked,
        key=lambda item: (
            -item.get("hybrid_score", 0.0),
            -(int(item["year"]) if str(item.get("year", "")).isdigit() else 0),
            item.get("title", ""),
        ),
    )

    return {
        "articles": reranked,
        "signals_used": [
            "correspondance lexicale",
            "proximité forte du titre avec le sujet exact",
            "similarité textuelle globale sujet ↔ titre/abstract",
            "pénalisation des articles trop généraux",
        ],
    }
