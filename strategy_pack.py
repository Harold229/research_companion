"""
Utilitaires de formatage pour le pack exporté de stratégie de recherche.
"""

from question_display import get_component_label
from question_display import get_question_presentation
from question_display import get_visible_explanation


def _clean_text(value, fallback="Non précisé") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _format_components(components: dict, presentation: dict) -> str:
    if not components:
        return "- Aucune composante structurée disponible"

    lines = []
    for key, value in components.items():
        if value:
            label = get_component_label(key, presentation)
            lines.append(f"- {label} : {value}")
    return "\n".join(lines) if lines else "- Aucune composante structurée disponible"


def _format_retained_concepts(strategy: dict) -> str:
    wide_elements = strategy.get("wide", {}).get("elements", [])
    narrow_elements = strategy.get("narrow", {}).get("elements", [])

    concept_levels = {}
    for element in wide_elements:
        concept_levels[element.get("label", "Concept")] = "large"
    for element in narrow_elements:
        label = element.get("label", "Concept")
        concept_levels[label] = "large + restreinte" if label in concept_levels else "restreinte"

    if not concept_levels:
        return "- Aucun concept actif"

    return "\n".join(
        f"- {label} ({level})"
        for label, level in concept_levels.items()
    )


def _format_excluded_concepts(excluded: list) -> str:
    if not excluded:
        return "- Aucun concept exclu"

    return "\n".join(
        f"- {item.get('label', 'Concept')} : {item.get('reason', 'Sans justification')}"
        for item in excluded
    )


def _format_platform_queries(platform_outputs: dict, is_identical: bool) -> str:
    sections = []
    for platform_name, output in platform_outputs.items():
        large = output.get("large", {})
        strict = output.get("strict", {})

        lines = [f"### {platform_name}"]
        lines.append("**Stratégie large**")
        lines.append(large.get("query") or "Indisponible")

        if is_identical:
            lines.append("")
            lines.append("**Stratégie restreinte**")
            lines.append("Identique à la stratégie large.")
        else:
            lines.append("")
            lines.append("**Stratégie restreinte**")
            lines.append(strict.get("query") or "Indisponible")

        sections.append("\n".join(lines))

    return "\n\n".join(sections) if sections else "Aucune requête plateforme disponible."


def build_search_strategy_pack(
    user_question: str,
    result: dict,
    strategy: dict,
    platform_outputs: dict,
) -> str:
    """
    Construit un export markdown lisible pour l’analyse courante.
    """
    reformulated_question = (
        result.get("research_question_fr")
        or result.get("research_question_en")
        or result.get("research_question_comment")
        or "Aucune reformulation nécessaire."
    )
    framework = result.get("framework")
    is_identical = strategy.get("is_identical", False)
    presentation = get_question_presentation(result)
    visible_explanation = get_visible_explanation(result, presentation)

    wide = strategy.get("wide", {})
    narrow = strategy.get("narrow", {})

    methodology_note = (
        "Aucun filtre supplémentaire pertinent n’a été identifié. "
        "Vous pouvez affiner en précisant un pays, un contexte, une population ou un cadre d’étude."
        if is_identical else
        "La stratégie large utilise les concepts essentiels (priority = 1). "
        "La stratégie restreinte ajoute les concepts d’affinement (priority = 2) "
        "pour réduire le volume de résultats."
    )

    sections = [
        "# Pack de stratégie de recherche",
        "",
        "## 1. Question initiale",
        _clean_text(user_question),
        "",
        "## 2. Question reformulée",
        _clean_text(reformulated_question),
        "",
        "## 3. Compréhension",
        f"- Type de question : {_clean_text(presentation.get('question_type'), 'Question descriptive')}",
    ]

    if presentation.get("show_framework") and framework:
        sections.append(f"- Framework méthodologique : {_clean_text(framework)}")

    sections.extend([
        f"- Niveau de recherche : {_clean_text(result.get('research_level'), '2')}",
        f"- Explication : {_clean_text(visible_explanation, 'Non précisée')}",
        "",
        "## 4. Composantes identifiées",
        _format_components(result.get("components") or {}, presentation),
        "",
        "## 5. Concepts retenus pour la recherche",
        _format_retained_concepts(strategy),
        "",
        "## 6. Concepts exclus du filtrage",
        _format_excluded_concepts(strategy.get("excluded", [])),
        "",
        "## 7. Stratégie canonique",
        f"- Stratégie large : {', '.join(wide.get('elements_used', [])) or 'Aucun concept actif'}",
    ])

    if is_identical:
        sections.append("- Stratégie restreinte : identique à la stratégie large")
    else:
        sections.append(
            f"- Stratégie restreinte : {', '.join(narrow.get('elements_used', [])) or 'Aucun concept actif'}"
        )

    sections.extend([
        "",
        "## 8. Requêtes par plateforme disponible",
        _format_platform_queries(platform_outputs, is_identical),
        "",
        "## 9. Note méthodologique",
        methodology_note,
    ])

    return "\n".join(sections).strip() + "\n"
