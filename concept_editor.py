"""
Outils légers pour éditer les concepts de recherche dans l'interface.
"""

from copy import deepcopy
import re


EDITOR_STATE_OPTIONS = {
    "large": "Recherche large",
    "narrow": "Recherche restreinte",
    "excluded": "Non utilisé comme filtre",
}


def clone_search_elements(search_elements: list) -> list:
    return [deepcopy(element) for element in (search_elements or []) if isinstance(element, dict)]


def get_editor_state(element: dict) -> str:
    if not element.get("search_filter"):
        return "excluded"
    return "large" if element.get("priority") == 1 else "narrow"


def serialize_terms(value: str) -> str:
    terms = [term.strip() for term in str(value or "").split(" OR ") if term.strip()]
    return "\n".join(terms)


def normalize_terms_input(value: str) -> str:
    chunks = re.split(r"\n+", str(value or ""))
    terms = []
    for chunk in chunks:
        for term in chunk.split(" OR "):
            cleaned = term.strip()
            if cleaned and cleaned not in terms:
                terms.append(cleaned)
    return " OR ".join(terms)


def apply_editor_changes(base_elements: list, edited_rows: list) -> list:
    updated_elements = []

    for element, row in zip(base_elements or [], edited_rows or []):
        if row.get("removed"):
            continue

        updated = deepcopy(element)
        updated["tiab"] = normalize_terms_input(row.get("tiab", ""))
        updated["mesh"] = str(row.get("mesh", "")).strip() or None

        state = row.get("state", get_editor_state(updated))
        if not updated.get("tiab") and not updated.get("mesh"):
            updated["search_filter"] = False
            updated["priority"] = None
            updated["reason"] = "Aucun terme conservé dans l'éditeur."
        elif state == "large":
            updated["search_filter"] = True
            updated["priority"] = 1
            updated["reason"] = ""
        elif state == "narrow":
            updated["search_filter"] = True
            updated["priority"] = 2
            updated["reason"] = ""
        else:
            updated["search_filter"] = False
            updated["priority"] = None
            updated["reason"] = updated.get("reason") or "Concept désactivé dans l'éditeur."

        updated_elements.append(updated)

    return updated_elements
