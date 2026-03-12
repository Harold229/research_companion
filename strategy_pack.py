"""
Utilitaires de formatage pour le pack exporté de stratégie de recherche.
"""

from question_display import get_component_label
from question_display import get_question_presentation
from question_display import get_reformulated_question
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
        large_count = large.get("count")
        strict_count = strict.get("count")

        lines.append("**Stratégie large**")
        if isinstance(large_count, int) and large_count >= 0:
            lines.append(f"Nombre de résultats observé : {large_count}")
        lines.append(large.get("query") or "Indisponible")

        if is_identical:
            lines.append("")
            lines.append("**Stratégie restreinte**")
            lines.append("Identique à la stratégie large.")
        else:
            lines.append("")
            lines.append("**Stratégie restreinte**")
            if isinstance(strict_count, int) and strict_count >= 0:
                lines.append(f"Nombre de résultats observé : {strict_count}")
            lines.append(strict.get("query") or "Indisponible")

        sections.append("\n".join(lines))

    return "\n\n".join(sections) if sections else "Aucune requête plateforme disponible."


def _format_methodology_summary(
    presentation: dict,
    visible_explanation: str,
    strategy: dict,
    platform_outputs: dict,
) -> str:
    question_type = _clean_text(presentation.get("question_type"), "question descriptive")
    wide_labels = strategy.get("wide", {}).get("elements_used", [])
    narrow_labels = strategy.get("narrow", {}).get("elements_used", [])
    added_labels = [label for label in narrow_labels if label not in wide_labels]

    counts = []
    for platform_name, output in platform_outputs.items():
        large_count = output.get("large", {}).get("count")
        strict_count = output.get("strict", {}).get("count")
        if isinstance(large_count, int) and large_count >= 0:
            if strategy.get("is_identical"):
                counts.append(f"Sur {platform_name}, la stratégie visible renvoie {large_count} résultats.")
            elif isinstance(strict_count, int) and strict_count >= 0:
                counts.append(
                    f"Sur {platform_name}, la stratégie large renvoie {large_count} résultats et la stratégie restreinte {strict_count}."
                )
            else:
                counts.append(f"Sur {platform_name}, la stratégie large renvoie {large_count} résultats.")

    lines = [
        f"- Le sujet a été interprété comme une {question_type}.",
        f"- {visible_explanation}",
        (
            f"- La stratégie a été construite autour des concepts essentiels suivants : {', '.join(wide_labels)}."
            if wide_labels else
            "- Aucun concept central n’a été explicitement retenu dans la stratégie."
        ),
    ]

    if strategy.get("is_identical"):
        lines.append(
            "- Aucun filtre d’affinement supplémentaire n’a été jugé suffisamment pertinent pour produire une version restreinte distincte."
        )
    elif added_labels:
        lines.append(
            f"- La version restreinte ajoute les éléments suivants pour affiner la recherche : {', '.join(added_labels)}."
        )

    lines.extend(f"- {count_sentence}" for count_sentence in counts)
    return "\n".join(lines)


def _format_filter_rationale(excluded: list) -> str:
    if not excluded:
        return (
            "- Tous les concepts identifiés comme suffisamment utiles à la recherche documentaire ont été conservés dans la stratégie active."
        )

    lines = [
        "- Un concept n’est pas utilisé comme filtre actif lorsqu’un article pertinent pourrait rester utile même sans le mentionner explicitement dans les champs recherchés.",
        "- Cette approche limite les exclusions abusives et suit une logique de recherche d’abord large, puis progressivement affinée.",
    ]
    lines.extend(
        f"- {item.get('label', 'Concept')} : {item.get('reason', 'Sans justification')}"
        for item in excluded
    )
    return "\n".join(lines)


def _format_how_to_use(strategy: dict) -> str:
    wide_labels = strategy.get("wide", {}).get("elements_used", [])
    narrow_labels = strategy.get("narrow", {}).get("elements_used", [])
    added_labels = [label for label in narrow_labels if label not in wide_labels]

    if strategy.get("is_identical"):
        return "\n".join([
            "- Utilisez la stratégie affichée comme point de départ principal.",
            "- Si le volume de résultats reste trop large ou trop hétérogène, affinez ensuite par pays, contexte, population ou cadre d’étude.",
            "- Gardez la version actuelle comme référence de base pour documenter une première exploration rigoureuse.",
        ])

    return "\n".join([
        "- Commencez par la stratégie large pour repérer le volume global de littérature et vérifier que les concepts essentiels capturent bien le sujet.",
        (
            f"- Passez ensuite à la stratégie restreinte pour cibler plus précisément la littérature en ajoutant : {', '.join(added_labels)}."
            if added_labels else
            "- Passez ensuite à la stratégie restreinte pour cibler plus précisément la littérature."
        ),
        "- Si la version restreinte devient trop étroite, revenez à la version large puis réintroduisez les filtres un par un.",
    ])


def _format_refinement_paths(result: dict, strategy: dict) -> str:
    suggestions = []
    geography = result.get("geography") or {}
    components = result.get("components") or {}
    excluded_labels = {str(item.get("label", "")).lower() for item in strategy.get("excluded", [])}

    if not any(v for v in geography.values() if v):
        suggestions.append("Préciser un pays, une région ou un périmètre géographique si cela a du sens pour votre sujet.")
    if not components.get("population"):
        suggestions.append("Préciser la population concernée si vous visez un sous-groupe particulier.")
    if not components.get("setting"):
        suggestions.append("Ajouter un contexte de soins, un type de structure ou un cadre d’étude si cela peut aider à resserrer la recherche.")
    if "géographie" not in excluded_labels and strategy.get("is_identical"):
        suggestions.append("Ajouter un cadre géographique peut être la première piste d’affinement la plus simple.")
    if any(label in excluded_labels for label in {"mesure épidémiologique", "validité", "complications génériques"}):
        suggestions.append("Éviter d’ajouter comme filtres des notions transversales trop larges si elles ne sont pas au cœur du sujet.")

    if not suggestions:
        suggestions.append("La stratégie actuelle est déjà cohérente ; les ajustements futurs peuvent porter sur le contexte, la population ou la période étudiée.")

    return "\n".join(f"- {suggestion}" for suggestion in suggestions)


def _build_reusable_text(
    user_question: str,
    reformulated_question: str,
    presentation: dict,
    strategy: dict,
    result_filters: dict = None,
) -> str:
    subject_type = _clean_text(presentation.get("question_type"), "question descriptive")
    wide_labels = strategy.get("wide", {}).get("elements_used", [])
    narrow_labels = strategy.get("narrow", {}).get("elements_used", [])
    excluded_labels = [item.get("label", "Concept") for item in strategy.get("excluded", [])]

    if strategy.get("is_identical"):
        strategy_sentence = (
            f"La stratégie de recherche a retenu les concepts suivants comme noyau principal : {', '.join(wide_labels) or 'aucun concept actif explicite'}."
        )
    else:
        strategy_sentence = (
            f"La version large repose sur {', '.join(wide_labels) or 'aucun concept actif explicite'}, "
            f"puis une version restreinte ajoute {', '.join(label for label in narrow_labels if label not in wide_labels) or 'des éléments d’affinement complémentaires'}."
        )

    excluded_sentence = (
        f"Les notions suivantes ont été laissées hors du filtrage actif afin d’éviter une stratégie trop restrictive : {', '.join(excluded_labels)}."
        if excluded_labels else
        "Aucun concept supplémentaire n’a dû être explicitement écarté du filtrage actif."
    )

    filter_text = ""
    time_filter = (result_filters or {}).get("time") or {}
    if time_filter.get("label"):
        filter_text = (
            f" Un filtre temporel secondaire a ensuite été appliqué aux résultats affichés pour se concentrer sur la période {time_filter.get('label')}, "
            "sans modifier la stratégie initiale."
        )

    return (
        f"À partir du sujet initial « {user_question} », une reformulation opérationnelle a été retenue : "
        f"« {reformulated_question} ». Le sujet correspond à une {subject_type}. {strategy_sentence} "
        f"{excluded_sentence}{filter_text} Cette stratégie peut être utilisée telle quelle pour une première recherche, puis ajustée selon le volume et la pertinence des résultats."
    )


def build_search_strategy_pack(
    user_question: str,
    result: dict,
    strategy: dict,
    platform_outputs: dict,
    result_filters: dict = None,
) -> str:
    """
    Construit un export markdown lisible pour l’analyse courante.
    """
    framework = result.get("framework")
    is_identical = strategy.get("is_identical", False)
    presentation = get_question_presentation(result, user_question)
    reformulated_question = get_reformulated_question(user_question, result, presentation)
    visible_explanation = get_visible_explanation(result, presentation)
    excluded = strategy.get("excluded", [])
    time_filter = (result_filters or {}).get("time") or {}
    time_filter_label = time_filter.get("label")

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
        f"- Type de sujet : {_clean_text(presentation.get('question_type'), 'Question descriptive')}",
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
        _format_excluded_concepts(excluded),
        "",
        "## 7. Résumé méthodologique",
        _format_methodology_summary(presentation, visible_explanation, strategy, platform_outputs),
        "",
        "## 8. Pourquoi certains concepts ne sont pas utilisés comme filtres",
        _format_filter_rationale(excluded),
        "",
        "## 9. Stratégie canonique",
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
        "## 10. Comment utiliser la version large et la version restreinte",
        _format_how_to_use(strategy),
        "",
        "## 11. Pistes d’affinement",
        _format_refinement_paths(result, strategy),
        "",
        "## 12. Requêtes par plateforme disponible",
        _format_platform_queries(platform_outputs, is_identical),
        "",
    ])

    if time_filter_label:
        sections.extend([
            "## 13. Filtre temporel appliqué aux résultats",
            f"- Période retenue : {time_filter_label}",
            "- Ce filtre temporel a été appliqué aux résultats affichés et à leur priorisation, sans modifier la stratégie de recherche initiale.",
            "",
        ])

    text_section_number = "13" if not time_filter_label else "14"
    note_section_number = "14" if not time_filter_label else "15"

    sections.extend([
        f"## {text_section_number}. Texte prêt à réutiliser dans un mémoire, protocole ou document de travail",
        _build_reusable_text(
            user_question,
            reformulated_question,
            presentation,
            strategy,
            result_filters=result_filters,
        ),
        "",
        f"## {note_section_number}. Note méthodologique",
        methodology_note,
    ])

    return "\n".join(sections).strip() + "\n"
