import re

from services.concept_classifier import classify_concept_role


ROLE_WEIGHTS = {
    "core": 2.4,
    "refinement": 1.2,
    "ranking": 0.6,
    "context": 0.5,
}


def _normalize(text: str) -> str:
    return str(text or "").strip().lower()


def _contains_term(text: str, term: str) -> bool:
    normalized_text = _normalize(text)
    normalized_term = _normalize(term)
    if not normalized_text or not normalized_term:
        return False
    pattern = r"(?<!\w)" + re.escape(normalized_term) + r"(?!\w)"
    return re.search(pattern, normalized_text) is not None


def _split_terms(value: str) -> list:
    terms = re.split(r"\s+OR\s+", str(value or ""))
    cleaned = []
    for term in terms:
        normalized = str(term or "").strip().strip('"')
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _build_reason(label: str, role: str, matched_terms: list) -> str:
    label_text = _normalize(label)
    joined_terms = " ".join(_normalize(term) for term in matched_terms)

    if "compar" in label_text or any(token in joined_terms for token in ("versus", "vs", "placebo", "control", "comparison")):
        return "proche du comparateur demandé"
    if any(token in label_text for token in ("population", "patient", "participant", "adult", "child", "older", "personne")):
        return "cible la population recherchée"
    if any(token in label_text for token in ("safety", "adverse", "complication", "incident")):
        return "parle de sécurité"
    if any(token in label_text for token in ("geograph", "country", "region", "context", "setting", "location")) or role == "context":
        return "correspond au contexte géographique"
    if any(token in label_text for token in ("intervention", "treatment", "therapy", "drug", "exposure")):
        return "compare les traitements" if any(token in joined_terms for token in ("compare", "versus", "vs")) else "correspond au traitement étudié"
    if any(token in label_text for token in ("pathology", "condition", "disease", "maladie", "condition étudiée")) or role == "core":
        return "correspond à la pathologie"
    if role == "ranking":
        return "couvre un angle utile pour prioriser la lecture"
    if matched_terms:
        return f"reprend le concept {matched_terms[0]}"
    return "proche du sujet recherché"


def _extract_detected_concepts(result: dict) -> list:
    concepts = []
    for element in (result.get("search_elements") or []):
        if not isinstance(element, dict):
            continue
        terms = _split_terms(element.get("tiab"))
        if not terms:
            continue
        role = classify_concept_role(element)
        concepts.append({
            "label": element.get("label", "Concept"),
            "role": role,
            "terms": terms,
        })
    return concepts


def score_article_against_detected_concepts(article: dict, result: dict) -> dict:
    haystack = " ".join(
        part for part in [
            article.get("title", ""),
            article.get("abstract", ""),
            article.get("journal", ""),
        ] if part
    )

    matched_by_role = {"core": [], "refinement": [], "ranking": [], "context": []}
    reasons = []
    score = 0.0

    for concept in _extract_detected_concepts(result):
        matched_terms = [term for term in concept["terms"] if _contains_term(haystack, term)]
        if not matched_terms:
            continue
        matched_by_role[concept["role"]].append({
            "label": concept["label"],
            "terms": matched_terms,
        })
        score += ROLE_WEIGHTS.get(concept["role"], 0.0)
        reason = _build_reason(concept["label"], concept["role"], matched_terms)
        if reason not in reasons:
            reasons.append(reason)

    if not reasons:
        reasons.append("reprend au moins un élément du sujet")

    return {
        "concept_score": score,
        "matched_by_role": matched_by_role,
        "reasons": reasons[:3],
    }
