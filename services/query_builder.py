from copy import deepcopy

from platform_backends import pubmed_backend
from platform_backends.pubmed_backend import build_block
from search_strategy import build_search_strategy
from services.concept_classifier import classify_concept_role
from services.concept_classifier import ROLE_LABELS
from services.concept_classifier import split_controlled_terms
from services.concept_classifier import split_synonyms
from services.librarian_strategy_adapter import build_query_package_from_librarian_result

ROLE_DESCRIPTIONS = {
    "core": "Concepts au coeur du sujet. Ils structurent la recherche de base.",
    "refinement": "Concepts utiles pour recentrer la recherche sans la rendre trop étroite trop tôt.",
    "ranking": "Concepts utiles pour lire et prioriser les résultats, mais pas forcément comme filtres.",
    "context": "Contexte, géographie ou cadre d'étude utilisé pour resserrer la recherche si besoin.",
}

STATUS_OPTIONS = {
    "required": "obligatoire",
    "optional": "optionnel",
    "ranking_only": "priorité seulement",
    "ignore": "ignorer",
}

STATUS_DESCRIPTIONS = {
    "required": "Le concept doit rester dans toutes les variantes de requête.",
    "optional": "Le concept peut être ajouté dans les variantes plus ciblées.",
    "ranking_only": "Le concept aide à prioriser la lecture, sans filtrer la requête.",
    "ignore": "Le concept est retiré de cette stratégie.",
}

VARIANT_DEFINITIONS = {
    "large": {
        "label": "Large",
        "description": "Maximise la récupération.",
    },
    "focused": {
        "label": "Ciblée",
        "description": "Recentre sur les concepts principaux.",
    },
    "strict": {
        "label": "Stricte",
        "description": "Formulation plus restrictive pour tester une hypothèse précise.",
    },
}

ROLE_RELAXATION_LABELS = {
    "ranking": "concepts de ranking",
    "context": "concepts de contexte",
    "refinement": "concepts de refinement",
}


def build_query_package(result: dict) -> dict:
    librarian_query_package = build_query_package_from_librarian_result(result or {})
    if librarian_query_package:
        return librarian_query_package

    return _build_standard_query_package(result or {})


def _build_standard_query_package(result: dict) -> dict:
    strategy = build_search_strategy(result or {})
    pubmed_queries = pubmed_backend.build_pubmed_queries(strategy)
    return {
        "result": result or {},
        "strategy": strategy,
        "platform_outputs": {"PubMed": pubmed_queries},
        "broad_query": (pubmed_queries.get("large") or {}).get("query", ""),
        "focused_query": (pubmed_queries.get("strict") or {}).get("query", ""),
        "strict_query": (pubmed_queries.get("strict") or {}).get("query", ""),
    }


def build_query_package_for_elements(result: dict, search_elements: list) -> dict:
    effective_result = dict(result or {})
    effective_result["search_elements"] = deepcopy(search_elements or [])
    if list(search_elements or []) == list((result or {}).get("search_elements") or []):
        librarian_query_package = build_query_package_from_librarian_result(effective_result)
        if librarian_query_package:
            return librarian_query_package
    return _build_standard_query_package(effective_result)


def get_preferred_discovery_query(query_package: dict) -> str:
    pubmed_queries = (query_package or {}).get("platform_outputs", {}).get("PubMed", {})
    if not pubmed_queries:
        return ""
    large_query = (pubmed_queries.get("large") or {}).get("query", "")
    strict_query = (pubmed_queries.get("strict") or {}).get("query", "")
    return large_query or strict_query


def _relax_roles_in_elements(result: dict, roles_to_relax: set[str]) -> list:
    classified_concepts = {
        concept.get("label"): concept
        for concept in ((result or {}).get("classified_concepts") or [])
        if isinstance(concept, dict)
    }
    relaxed_elements = []
    for element in deepcopy((result or {}).get("search_elements") or []):
        if not isinstance(element, dict):
            continue
        role = (classified_concepts.get(element.get("label", "")) or {}).get("role") or classify_concept_role(element)
        if element.get("search_filter") and role in roles_to_relax:
            element["search_filter"] = False
            element["priority"] = None
            element["reason"] = element.get("reason") or f"Concept relâché automatiquement ({role})."
        relaxed_elements.append(element)
    return relaxed_elements


def build_fallback_query_attempts(result: dict) -> list:
    attempts = []
    original_package = build_query_package(result or {})
    attempts.append({
        "key": "original",
        "query_package": original_package,
        "query": get_preferred_discovery_query(original_package),
        "relaxed_roles": [],
        "relaxed_labels": [],
    })

    relaxation_steps = [
        {"key": "ranking", "roles": {"ranking"}},
        {"key": "ranking_context", "roles": {"ranking", "context"}},
        {"key": "ranking_context_refinement", "roles": {"ranking", "context", "refinement"}},
    ]
    seen_queries = {attempts[0]["query"]}

    for step in relaxation_steps:
        relaxed_result = dict(result or {})
        relaxed_result["search_elements"] = _relax_roles_in_elements(result or {}, step["roles"])
        relaxed_package = build_query_package(relaxed_result)
        relaxed_query = get_preferred_discovery_query(relaxed_package)
        if not relaxed_query or relaxed_query in seen_queries:
            continue
        attempts.append({
            "key": step["key"],
            "query_package": relaxed_package,
            "query": relaxed_query,
            "relaxed_roles": list(step["roles"]),
            "relaxed_labels": [ROLE_RELAXATION_LABELS[role] for role in step["roles"] if role in ROLE_RELAXATION_LABELS],
        })
        seen_queries.add(relaxed_query)

    return attempts

def default_status_for_element(element: dict, role: str) -> str:
    if element.get("search_filter"):
        return "required" if element.get("priority") == 1 else "optional"
    return "ranking_only" if role == "ranking" else "ignore"


def get_workspace_base_elements(entry: dict, session_state) -> list:
    entry_id = entry.get("id")
    editor_key = f"concept_editor_elements_{entry_id}"
    edited_elements = session_state.get(editor_key)
    if isinstance(edited_elements, list):
        return edited_elements
    return (entry.get("result") or {}).get("search_elements") or []


def build_workspace_concepts(entry: dict, session_state) -> list:
    classified_concepts = {
        concept.get("label"): concept
        for concept in ((entry.get("result") or {}).get("classified_concepts") or [])
        if isinstance(concept, dict)
    }
    concepts = []
    for index, element in enumerate(get_workspace_base_elements(entry, session_state)):
        if not isinstance(element, dict):
            continue
        classified = classified_concepts.get(element.get("label", ""))
        role = (classified or {}).get("role") or classify_concept_role(element)
        concepts.append({
            "id": f"concept_{index}",
            "index": index,
            "label": element.get("label", f"Concept {index + 1}"),
            "role": role,
            "status": default_status_for_element(element, role),
            "tiab": str(element.get("tiab") or ""),
            "mesh": str(element.get("mesh") or ""),
            "synonyms": (classified or {}).get("synonyms") or split_synonyms(element.get("tiab")),
            "controlled_terms": (classified or {}).get("controlled_terms") or split_controlled_terms(element.get("mesh")),
            "reason": str(element.get("reason") or ""),
            "search_filter": bool(element.get("search_filter")),
            "priority": element.get("priority"),
            "source": deepcopy(element),
        })
    return concepts


def get_strategy_builder_state(entry: dict, session_state) -> tuple[str, list]:
    search_session_id = session_state.get("search_session_id") or entry.get("search_session_id") or entry.get("id")
    workspace_key = f"strategy_builder_workspace_{search_session_id}"
    source_signature = (
        entry.get("id"),
        tuple(
            (
                concept.get("label", ""),
                concept.get("tiab", ""),
                concept.get("mesh", ""),
                concept.get("search_filter"),
                concept.get("priority"),
            )
            for concept in get_workspace_base_elements(entry, session_state)
            if isinstance(concept, dict)
        ),
    )
    signature_key = f"strategy_builder_signature_{search_session_id}"

    if session_state.get(signature_key) != source_signature or workspace_key not in session_state:
        session_state[workspace_key] = build_workspace_concepts(entry, session_state)
        session_state[signature_key] = source_signature

    return search_session_id, session_state[workspace_key]


def update_workspace_statuses(concepts: list, session_state, search_session_id: str) -> list:
    updated = []
    for concept in concepts:
        updated_concept = deepcopy(concept)
        status_key = f"strategy_builder_status_{search_session_id}_{concept['id']}"
        updated_concept["status"] = session_state.get(status_key, concept["status"])
        updated.append(updated_concept)
    return updated


def group_concepts_by_role(concepts: list) -> dict:
    grouped = {role: [] for role in ROLE_LABELS}
    for concept in concepts:
        grouped.setdefault(concept["role"], []).append(concept)
    return grouped


def _should_include(concept: dict, variant: str) -> bool:
    status = concept.get("status")
    role = concept.get("role")

    if status == "ignore" or status == "ranking_only":
        return False
    if status == "required":
        return True

    if variant == "large":
        return role == "core"
    if variant == "focused":
        return role in {"core", "refinement"}
    if variant == "strict":
        return role in {"core", "refinement", "context"}
    return False


def build_query_variants(concepts: list) -> dict:
    variants = {}

    for variant_key, definition in VARIANT_DEFINITIONS.items():
        selected_concepts = [concept for concept in concepts if _should_include(concept, variant_key)]
        blocks = [
            build_block(
                concept.get("label", "Concept"),
                mesh_block=concept.get("mesh") or None,
                tiab_term=concept.get("tiab") or None,
            )
            for concept in selected_concepts
        ]
        query = "\nAND ".join(block for block in blocks if block)
        variants[variant_key] = {
            "label": definition["label"],
            "description": definition["description"],
            "query": query,
            "concepts_used": [concept.get("label", "Concept") for concept in selected_concepts],
        }

    return variants
