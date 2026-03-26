"""
search_strategy.py — Construction de la stratégie canonique indépendante
de toute plateforme.

Fonction exposée :
  - build_search_strategy(json_result) -> dict
"""

import re

from services.concept_classifier import classify_concept_role


def _build_role_map(json_result: dict) -> dict:
    role_map = {}
    for concept in (json_result.get("classified_concepts") or []):
        if isinstance(concept, dict) and concept.get("label"):
            role_map[concept["label"]] = concept.get("role")
    return role_map


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _split_or_terms(value: str) -> list[str]:
    return [term.strip().strip('"') for term in str(value or "").split(" OR ") if term.strip()]


def _is_outcome_like_in_wide(element: dict, json_result: dict) -> bool:
    components = (json_result or {}).get("components") or {}
    outcome_text = _normalize_text(components.get("outcome"))
    label = _normalize_text(element.get("label"))
    terms = [_normalize_text(term) for term in _split_or_terms(element.get("tiab"))]

    explicit_markers = (
        "outcome",
        "mesure",
        "measure",
        "safety",
        "adverse",
        "complication",
        "prevalence",
        "incidence",
        "mortality",
        "survival",
        "adherence",
        "compliance",
        "control",
    )

    if any(marker in label for marker in explicit_markers):
        return True

    if outcome_text:
        outcome_tokens = [token for token in outcome_text.replace("-", " ").split() if len(token) > 2]
        if outcome_text == label or outcome_text in label or label in outcome_text:
            return True
        for term in terms:
            if term == outcome_text or outcome_text in term or term in outcome_text:
                return True
            if outcome_tokens and all(token in term for token in outcome_tokens):
                return True

    return False


def _should_keep_in_wide(element: dict, role_map: dict) -> bool:
    role = role_map.get(element.get("label", "")) or classify_concept_role(element)
    return role == "core"


def build_search_strategy(json_result: dict) -> dict:
    """
    Construit la stratégie canonique wide / narrow à partir du JSON LLM.

    Logique Bramer inchangée :
      - search_filter=True  -> élément actif
      - search_filter=False -> élément exclu
      - priority 1          -> stratégie wide
      - priority 1 + 2      -> stratégie narrow
    """
    elements = json_result.get("search_elements") or []

    active = [e for e in elements if e.get("search_filter")]
    priority_1 = [e for e in active if e.get("priority") == 1]
    priority_2 = [e for e in active if e.get("priority") == 2]
    role_map = _build_role_map(json_result)

    # SPEC rule: wide = tous les search_elements actifs avec priority = 1.
    # Pas de filtre de rôle supplémentaire — la priorité assignée par le LLM
    # est la seule source de vérité pour la stratégie large.
    wide_elements = list(priority_1)
    narrow_elements = priority_1 + priority_2

    return {
        "wide": {
            "elements": wide_elements,
            "elements_used": [e.get("label", "Concept") for e in wide_elements],
        },
        "narrow": {
            "elements": narrow_elements,
            "elements_used": [e.get("label", "Concept") for e in narrow_elements],
        },
        "excluded": [
            {"label": e.get("label", "Concept"), "reason": e.get("reason", "")}
            for e in elements
            if not e.get("search_filter")
        ],
        "is_identical": wide_elements == narrow_elements,
    }
