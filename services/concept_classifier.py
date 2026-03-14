import re


ROLE_LABELS = {
    "core": "core",
    "refinement": "refinement",
    "ranking": "ranking",
    "context": "context",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def split_synonyms(value: str) -> list:
    parts = re.split(r"\s+OR\s+", str(value or "").strip())
    synonyms = []
    for part in parts:
        cleaned = part.strip().strip('"')
        if cleaned and cleaned not in synonyms:
            synonyms.append(cleaned)
    return synonyms


def split_controlled_terms(value) -> list:
    if isinstance(value, list):
        raw_terms = value
    else:
        raw_terms = [value]

    controlled_terms = []
    for raw_term in raw_terms:
        cleaned = str(raw_term or "").strip()
        if not cleaned:
            continue
        if cleaned not in controlled_terms:
            controlled_terms.append(cleaned)
    return controlled_terms


def classify_concept_role(element: dict) -> str:
    label = _normalize_text(element.get("label"))
    reason = _normalize_text(element.get("reason"))
    terms = _normalize_text(element.get("tiab"))

    context_patterns = (
        "geo",
        "geograph",
        "country",
        "region",
        "continent",
        "context",
        "contexte",
        "setting",
        "cadre",
        "location",
        "database",
        "registre",
        "registry",
        "hospital",
        "hôpital",
        "period",
        "time period",
        "africa",
        "europe",
        "asia",
    )
    ranking_patterns = (
        "prevalence",
        "incidence",
        "frequency",
        "epidemiolog",
        "burden",
        "adverse",
        "complication",
        "safety",
        "outcome",
        "measure",
        "mesure",
        "performance",
        "prognos",
        "pronostic",
        "survival",
        "mortal",
        "morbid",
    )
    refinement_patterns = (
        "population",
        "subgroup",
        "sub-group",
        "age",
        "aged",
        "elderly",
        "older",
        "child",
        "adolescent",
        "young",
        "compar",
        "factor",
        "associated",
        "risk",
        "diagnos",
        "test",
        "tool",
        "method",
        "study",
        "design",
        "subtype",
        "stage",
    )

    if any(pattern in label or pattern in terms for pattern in context_patterns):
        return "context"
    if any(pattern in label or pattern in reason or pattern in terms for pattern in ranking_patterns):
        return "ranking"
    if any(pattern in label or pattern in terms for pattern in refinement_patterns):
        return "refinement"
    if element.get("priority") == 2:
        return "refinement"
    return "core"


def build_classified_concepts(search_elements: list) -> list:
    concepts = []
    for index, element in enumerate(search_elements or []):
        if not isinstance(element, dict):
            continue
        concepts.append({
            "id": f"concept_{index}",
            "label": element.get("label", f"Concept {index + 1}"),
            "role": classify_concept_role(element),
            "synonyms": split_synonyms(element.get("tiab")),
            "controlled_terms": split_controlled_terms(element.get("mesh")),
            "search_filter": bool(element.get("search_filter")),
            "priority": element.get("priority"),
            "reason": element.get("reason", ""),
        })
    return concepts
