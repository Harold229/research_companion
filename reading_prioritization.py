"""
Priorisation légère des articles selon un objectif de lecture.
"""

import re


FOCUS_OPTIONS = {
    "prevalence": "Prévalence",
    "factors": "Facteurs associés",
    "population": "Population spécifique",
    "geography": "Contexte géographique",
    "study_type": "Type d’étude",
    "tool": "Outil ou test",
    "validity": "Validité / performance",
    "other": "Autre objectif libre",
}

PRIORITY_ORDER = {"Très pertinent": 0, "Pertinent": 1, "À vérifier": 2}


FOCUS_KEYWORDS = {
    "prevalence": ["prevalence", "incidence", "frequency", "epidemiology", "burden"],
    "factors": ["risk factor", "associated", "association", "determinant", "predictor", "correlate"],
    "population": [],
    "geography": [],
    "study_type": ["cohort", "cross-sectional", "case-control", "trial", "systematic review", "meta-analysis"],
    "tool": ["test", "screening", "score", "algorithm", "instrument", "tool", "questionnaire"],
    "validity": ["validity", "validation", "performance", "sensitivity", "specificity", "accuracy", "roc", "auc"],
    "other": [],
}


def _normalize(text: str) -> str:
    return str(text or "").strip().lower()


def _extract_goal_terms(custom_goal: str) -> list:
    text = _normalize(custom_goal)
    if not text:
        return []

    stopwords = {
        "je", "veux", "surtout", "les", "des", "qui", "que", "dans", "pour", "avec",
        "sur", "une", "un", "du", "de", "la", "le", "et", "ou", "d'abord", "abord",
        "articles", "études", "etudes", "article",
    }
    chunks = re.split(r"[,\;\n]+", text)
    terms = [chunk.strip() for chunk in chunks if chunk.strip()]

    for word in re.findall(r"\b[\w'-]{5,}\b", text):
        if word not in stopwords:
            terms.append(word)

    return list(dict.fromkeys(term for term in terms if term))


def _contains_term(text: str, term: str) -> bool:
    normalized_text = _normalize(text)
    normalized_term = _normalize(term)
    if not normalized_text or not normalized_term:
        return False
    pattern = r"(?<!\w)" + re.escape(normalized_term) + r"(?!\w)"
    return re.search(pattern, normalized_text) is not None


def priority_rank(priority: str) -> int:
    return PRIORITY_ORDER.get(priority, 9)


def _build_focus_terms(result: dict, focus_key: str, custom_goal: str = "") -> list:
    components = result.get("components") or {}
    geography = result.get("geography") or {}
    terms = list(FOCUS_KEYWORDS.get(focus_key, []))
    custom_goal_normalized = _normalize(custom_goal)

    if focus_key == "population" and components.get("population"):
        terms.extend([components.get("population")])
    elif focus_key == "geography":
        terms.extend([value for value in geography.values() if value])
    elif focus_key == "tool":
        for key in ("intervention", "exposure", "outcome"):
            if components.get(key):
                terms.append(components.get(key))
    if custom_goal.strip():
        terms.extend(_extract_goal_terms(custom_goal))
        if any(token in custom_goal_normalized for token in ["population", "adulte", "adult", "enfant", "child", "patients", "personnes âgées", "older"]):
            if components.get("population"):
                terms.append(components.get("population"))
        if any(token in custom_goal_normalized for token in ["afric", "géograph", "geograph", "mali", "west africa", "country", "pays", "région", "region"]):
            terms.extend([value for value in geography.values() if value])
        if any(token in custom_goal_normalized for token in ["facteur", "associated", "association", "déterminant", "determinant", "risk"]):
            terms.extend(FOCUS_KEYWORDS["factors"])
        if any(token in custom_goal_normalized for token in ["valid", "performance", "référence", "reference", "test", "outil", "montre", "watch", "compare", "compar"]):
            terms.extend(FOCUS_KEYWORDS["tool"])
            terms.extend(FOCUS_KEYWORDS["validity"])
            for key in ("intervention", "comparison", "exposure"):
                if components.get(key):
                    terms.append(components.get(key))

    return [term for term in terms if _normalize(term)]


def _score_article(article: dict, focus_terms: list, focus_label: str) -> dict:
    title = _normalize(article.get("title"))
    abstract = _normalize(article.get("abstract"))
    haystack = f"{title} {abstract}".strip()

    hybrid_score = float(article.get("hybrid_score", 0.0) or 0.0)
    signals = article.get("hybrid_signals", {}) or {}
    exact_title = float(signals.get("exact_title", 0.0) or 0.0)
    title_overlap = float(signals.get("title_overlap", 0.0) or 0.0)
    abstract_overlap = float(signals.get("abstract_overlap", 0.0) or 0.0)
    semantic_similarity = float(signals.get("semantic_similarity", 0.0) or 0.0)
    penalty = float(signals.get("penalty", 0.0) or 0.0)

    score = hybrid_score * 5.5
    reasons = []
    matched_terms = []

    if (
        exact_title >= 0.72
        or (exact_title >= 0.64 and title_overlap >= 0.58)
        or (title_overlap >= 0.5 and abstract_overlap >= 0.7 and semantic_similarity >= 0.55 and penalty < 0.05)
    ):
        reasons.append("titre quasi directement aligné avec le sujet")
        score += 3.0
    elif hybrid_score >= 0.56:
        reasons.append("très central pour le sujet exact")
        score += 1.3
    elif hybrid_score >= 0.36:
        reasons.append("proche du sujet exact")

    title_matches = signals.get("title_matches", []) or []
    abstract_matches = signals.get("abstract_matches", []) or []
    if title_matches:
        reasons.append(f"concepts couverts dans le titre : {', '.join(title_matches[:3])}")
    elif abstract_matches:
        reasons.append(f"concepts surtout retrouvés dans l’abstract : {', '.join(abstract_matches[:3])}")
    if abstract_overlap >= 0.45 or semantic_similarity >= 0.38:
        reasons.append("l’abstract traite directement la combinaison des concepts du sujet")
    if penalty >= 0.1:
        reasons.append("article plus général que le sujet exact")

    for term in focus_terms:
        normalized_term = _normalize(term)
        if not normalized_term:
            continue
        if _contains_term(title, normalized_term):
            score += 3
            matched_terms.append(term)
        elif _contains_term(abstract, normalized_term):
            score += 2
            matched_terms.append(term)

    if article.get("year") and article.get("year").isdigit() and int(article["year"]) >= 2020:
        score += 0.35
        if not reasons:
            reasons.append("publication récente")

    if matched_terms:
        unique_matches = list(dict.fromkeys(matched_terms))
        reasons.append(f"mentionne des termes liés à l’objectif : {', '.join(unique_matches[:3])}")

    if focus_label == "Population spécifique" and matched_terms:
        reasons.append("correspond à la population recherchée")
    elif focus_label == "Contexte géographique" and matched_terms:
        reasons.append("correspond au contexte géographique")
    elif focus_label == "Outil ou test" and matched_terms:
        reasons.append("mentionne l’outil ou le test étudié")
    elif focus_label == "Validité / performance" and matched_terms:
        reasons.append("traite explicitement des performances ou de la validité")

    if (
        exact_title >= 0.72
        or (exact_title >= 0.64 and title_overlap >= 0.58 and penalty < 0.08)
        or (title_overlap >= 0.5 and abstract_overlap >= 0.7 and semantic_similarity >= 0.55 and penalty < 0.05)
    ):
        priority = "Très pertinent"
    elif hybrid_score >= 0.56 and penalty < 0.08:
        priority = "Très pertinent"
    elif score >= 4.2:
        priority = "Très pertinent"
    elif score >= 2.2:
        priority = "Pertinent"
    else:
        priority = "À vérifier"

    if penalty >= 0.12 and hybrid_score < 0.3 and not matched_terms:
        priority = "À vérifier"

    ordered_reasons = []
    for reason in reasons:
        if reason and reason not in ordered_reasons:
            ordered_reasons.append(reason)

    return {
        **article,
        "score": score,
        "priority": priority,
        "reasons": ordered_reasons or ["correspondance partielle avec l’objectif de lecture"],
        "centrality_band": (
            "central"
            if priority == "Très pertinent"
            else "useful" if priority == "Pertinent"
            else "contextual"
        ),
    }


def prioritize_articles(
    articles: list,
    result: dict,
    focus_key: str,
    custom_goal: str = "",
) -> dict:
    focus_label = custom_goal.strip() or FOCUS_OPTIONS.get(focus_key, FOCUS_OPTIONS["other"])
    focus_terms = _build_focus_terms(result, focus_key, custom_goal)

    ranked = [
        _score_article(article, focus_terms, focus_label)
        for article in articles
    ]

    ranked.sort(
        key=lambda item: (
            priority_rank(item["priority"]),
            -item.get("score", 0),
            -float(item.get("hybrid_score", 0.0) or 0.0),
            item.get("title", ""),
        )
    )

    return {
        "focus_key": focus_key,
        "focus_label": focus_label,
        "focus_terms": focus_terms,
        "articles": ranked,
        "display_articles": [
            article
            for article in ranked
            if article.get("priority") != "À vérifier"
            or float(article.get("hybrid_score", 0.0) or 0.0) >= 0.18
            or article.get("score", 0) >= 1.8
        ],
    }


def apply_agent_assessment(prioritized: dict, shortlist: list, assessment: dict) -> dict:
    assessment_items = assessment.get("articles", []) if isinstance(assessment, dict) else []
    assessment_by_id = {
        item.get("article_id"): item
        for item in assessment_items
        if isinstance(item, dict) and item.get("article_id")
    }
    shortlist_by_pmid = {
        item.get("pmid"): item.get("article_id")
        for item in shortlist
        if item.get("pmid")
    }

    updated_articles = []
    for article in prioritized.get("articles", []):
        article_id = shortlist_by_pmid.get(article.get("pmid"))
        assessed = assessment_by_id.get(article_id)
        if assessed:
            assessed_priority = assessed.get("priority")
            if assessed_priority not in PRIORITY_ORDER:
                assessed_priority = article.get("priority")
            updated_articles.append({
                **article,
                "priority": assessed_priority,
                "reasons": [assessed.get("reason", "Classé par lecture rapide du titre et de l’abstract.")],
                "ranking_source": "agent",
            })
        else:
            updated_articles.append({
                **article,
                "ranking_source": article.get("ranking_source", "keywords"),
            })

    updated_articles.sort(
        key=lambda item: (
            priority_rank(item.get("priority")),
            0 if item.get("ranking_source") == "agent" else 1,
            -item.get("score", 0),
            item.get("title", ""),
        )
    )

    return {
        **prioritized,
        "articles": updated_articles,
        "agent_enabled": True,
    }
