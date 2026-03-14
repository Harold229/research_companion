"""
search_strategy.py — Construction de la stratégie canonique indépendante
de toute plateforme.

Fonction exposée :
  - build_search_strategy(json_result) -> dict
"""

from services.concept_classifier import classify_concept_role


def _build_role_map(json_result: dict) -> dict:
    role_map = {}
    for concept in (json_result.get("classified_concepts") or []):
        if isinstance(concept, dict) and concept.get("label"):
            role_map[concept["label"]] = concept.get("role")
    return role_map


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

    wide_elements = [e for e in priority_1 if _should_keep_in_wide(e, role_map)]
    if not wide_elements:
        wide_elements = priority_1
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
