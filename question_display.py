"""
Presentation helpers for pedagogical subject typing and reformulation.
"""


GENERIC_REFORMULATION_COMMENTS = {
    "votre question est bien formulée.",
    "your question is well formulated.",
}


def _clean_text(value) -> str:
    return str(value or "").strip()


def _normalize_sentence(text: str) -> str:
    sentence = " ".join(_clean_text(text).split())
    if not sentence:
        return ""
    sentence = sentence[0].upper() + sentence[1:]
    if sentence[-1] not in ".!?":
        sentence += " ?"
    return sentence


def _join_parts(prefix: str, *parts: str) -> str:
    values = [part.strip() for part in parts if _clean_text(part)]
    if not values:
        return ""
    return prefix + "".join(values)


def _starts_with_article_or_prep(text: str) -> bool:
    lowered = _clean_text(text).lower()
    return lowered.startswith((
        "le ",
        "la ",
        "les ",
        "l'",
        "un ",
        "une ",
        "des ",
        "du ",
        "de ",
        "d'",
        "au ",
        "aux ",
        "en ",
        "dans ",
        "sur ",
        "chez ",
    ))


def _format_population_clause(population: str) -> str:
    if not _clean_text(population):
        return ""
    if _starts_with_article_or_prep(population):
        return f" chez {population}"
    return f" chez les {population}"


def _format_setting_clause(setting: str) -> str:
    if not _clean_text(setting):
        return ""
    if _starts_with_article_or_prep(setting):
        return f" {setting}"
    return f" dans {setting}"


def _format_de_clause(target: str) -> str:
    cleaned = _clean_text(target)
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered.startswith(("l'", "d'")):
        return f"de {cleaned}"
    if _starts_with_article_or_prep(cleaned):
        return f"de {cleaned}"
    if lowered[0] in "aeiouyàâäéèêëîïôöùûüh":
        return f"de l'{cleaned}"
    return f"de {cleaned}"


def _is_meaningful_reformulation(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return False
    return cleaned.lower() not in GENERIC_REFORMULATION_COMMENTS


def get_question_presentation(result: dict, user_question: str = "") -> dict:
    framework = result.get("framework")
    intent = result.get("intent")
    explanation = _clean_text(result.get("explanation")).lower()
    components = result.get("components") or {}
    question_text = _clean_text(user_question).lower()

    text = " ".join(
        str(value).lower()
        for value in [
            question_text,
            explanation,
            result.get("research_question_fr"),
            result.get("research_question_en"),
            components.get("population"),
            components.get("intervention"),
            components.get("outcome"),
            components.get("exposure"),
            components.get("comparison"),
            components.get("setting"),
        ]
        if value
    )

    has_exposure = bool(components.get("exposure"))
    has_comparison = bool(components.get("comparison"))

    if intent == "explore":
        subject_type = "question exploratoire"
    elif framework == "SPIDER" or any(word in text for word in [
        "qualitative",
        "perception",
        "vécu",
        "vecu",
        "expérience",
        "experience",
        "barrières",
        "barrier",
        "facilitateur",
    ]):
        subject_type = "question qualitative"
    elif any(word in text for word in [
        "validité",
        "validation",
        "validity",
        "validate",
        "validation study",
        "reliability",
        "reproductibilité",
        "reproductibility",
        "agreement",
        "concordance",
    ]):
        subject_type = "question de validité / validation"
    elif any(word in text for word in [
        "diagnostic",
        "diagnosis",
        "screening",
        "sensitivity",
        "specificity",
        "sensibilité",
        "spécificité",
        "roc",
        "auc",
    ]):
        subject_type = "question diagnostique"
    elif any(word in text for word in [
        "pronostic",
        "prognostic",
        "prediction",
        "predictive",
        "predictor",
        "survival",
        "survie",
        "risk score",
        "score pronostique",
    ]):
        subject_type = "question pronostique"
    elif any(word in text for word in [
        "score de propension",
        "propensity score",
        "iptw",
        "inverse probability",
        "multiple imputation",
        "imputation multiple",
        "modèle statistique",
        "statistique",
        "statistical",
        "regression",
        "régression",
        "cox",
        "kaplan-meier",
    ]):
        subject_type = "question statistique"
    elif any(word in text for word in [
        "méthode",
        "method",
        "methodological",
        "méthodologique",
        "missing data",
        "données manquantes",
        "study design",
        "protocole",
        "protocol",
        "measurement method",
    ]):
        subject_type = "question méthodologique"
    elif any(word in text for word in ["prévalence", "prevalence", "incidence", "fréquence", "frequency"]):
        subject_type = "question de prévalence"
    elif has_exposure or any(word in text for word in [
        "facteurs de risque",
        "risk factors",
        "déterminants",
        "association",
        "associations",
        "associated",
        "associé",
        "associés",
    ]):
        subject_type = "question de facteurs associés"
    elif any(word in text for word in [
        "intervention",
        "treatment",
        "traitement",
        "efficacité",
        "education",
        "éducation",
        "randomized",
        "randomisé",
    ]) or (framework == "PICO" and has_comparison):
        subject_type = "question interventionnelle"
    else:
        subject_type = "question descriptive"

    show_framework = framework in {"PEO", "SPIDER"} or (
        framework == "PICO" and subject_type == "question interventionnelle"
    )

    return {
        "question_type": subject_type,
        "show_framework": show_framework,
        "framework": framework,
    }


def get_visible_explanation(result: dict, presentation: dict) -> str:
    subject_type = presentation.get("question_type")
    raw_explanation = _clean_text(result.get("explanation"))

    explanations = {
        "question exploratoire": (
            "Question encore large, utile pour repérer rapidement si la littérature existe sur ce sujet."
        ),
        "question de prévalence": (
            "Question descriptive visant à estimer la fréquence d’un problème de santé dans une population ou un contexte donné."
        ),
        "question descriptive": (
            "Question descriptive visant à mieux caractériser un problème de santé, une situation ou un contexte."
        ),
        "question de facteurs associés": (
            "Question analytique visant à étudier les facteurs associés à un événement, un état de santé ou un résultat."
        ),
        "question interventionnelle": (
            raw_explanation
            or "Question interventionnelle visant à évaluer l’effet d’une intervention sur un critère de jugement."
        ),
        "question pronostique": (
            "Question visant à estimer l’évolution probable d’un état de santé ou la survenue d’un événement futur."
        ),
        "question diagnostique": (
            "Question visant à évaluer la capacité d’un test, d’un score ou d’un outil à identifier correctement une condition."
        ),
        "question de validité / validation": (
            "Question visant à évaluer la validité, la fiabilité ou les performances d’un outil, d’un test ou d’un algorithme."
        ),
        "question qualitative": (
            raw_explanation
            or "Question qualitative visant à comprendre des perceptions, expériences, barrières ou facilitateurs."
        ),
        "question méthodologique": (
            "Question portant sur le choix, l’usage ou la pertinence d’une méthode d’étude ou d’analyse."
        ),
        "question statistique": (
            "Question portant sur la comparaison ou le choix d’une méthode statistique pour analyser des données."
        ),
    }

    if subject_type in {
        "question exploratoire",
        "question de prévalence",
        "question descriptive",
        "question de facteurs associés",
        "question pronostique",
        "question diagnostique",
        "question de validité / validation",
        "question méthodologique",
        "question statistique",
    }:
        return explanations[subject_type]

    return explanations.get(subject_type) or raw_explanation


def get_reformulated_question(user_question: str, result: dict, presentation: dict) -> str:
    subject_type = presentation.get("question_type")
    components = result.get("components") or {}

    direct_reformulation = (
        result.get("research_question_fr")
        or result.get("research_question_en")
    )
    if _is_meaningful_reformulation(direct_reformulation):
        return _normalize_sentence(direct_reformulation)

    normalized_user_question = _normalize_sentence(user_question)

    population = _clean_text(components.get("population"))
    intervention = _clean_text(components.get("intervention"))
    exposure = _clean_text(components.get("exposure"))
    outcome = _clean_text(components.get("outcome"))
    setting = _clean_text(components.get("setting"))

    population_clause = _format_population_clause(population)
    setting_clause = _format_setting_clause(setting)

    if subject_type == "question de prévalence" and (intervention or exposure):
        target = intervention or exposure
        return _normalize_sentence(
            f"Quelle est la prévalence observée pour {target}{population_clause}{setting_clause}"
        )

    if subject_type == "question de facteurs associés" and outcome:
        return _normalize_sentence(
            f"Quels sont les facteurs associés à {outcome}{population_clause}{setting_clause}"
        )

    if subject_type == "question de validité / validation" and (intervention or exposure):
        target = intervention or exposure
        return _normalize_sentence(
            f"Quelle est la validité {_format_de_clause(target)}{population_clause}{setting_clause}"
        )

    if subject_type == "question diagnostique" and (intervention or exposure):
        target = intervention or exposure
        return _normalize_sentence(
            f"Quelle est la performance diagnostique {_format_de_clause(target)}{population_clause}{setting_clause}"
        )

    if subject_type == "question pronostique" and outcome:
        return _normalize_sentence(
            f"Quels sont les facteurs pronostiques de {outcome}{population_clause}{setting_clause}"
        )

    if subject_type in {
        "question méthodologique",
        "question statistique",
        "question interventionnelle",
        "question qualitative",
        "question descriptive",
        "question exploratoire",
    } and normalized_user_question:
        return normalized_user_question

    return normalized_user_question or "Reformulation non disponible."


def get_component_label(key: str, presentation: dict) -> str:
    subject_type = presentation.get("question_type")

    default_labels = {
        "population": "Population",
        "intervention": "Intervention",
        "comparison": "Comparateur",
        "outcome": "Critère étudié",
        "exposure": "Exposition ou sujet étudié",
        "setting": "Contexte",
    }

    adapted_labels = {
        "question de prévalence": {
            "intervention": "Phénomène ou condition étudiée",
            "outcome": "Mesure étudiée",
        },
        "question descriptive": {
            "intervention": "Phénomène ou condition étudiée",
            "outcome": "Mesure étudiée",
        },
        "question de facteurs associés": {
            "intervention": "Facteur ou exposition étudiée",
            "exposure": "Facteur ou exposition étudié",
            "outcome": "Événement ou critère étudié",
        },
        "question interventionnelle": {
            "intervention": "Intervention étudiée",
            "outcome": "Critère de jugement",
        },
        "question pronostique": {
            "intervention": "Facteur ou modèle pronostique",
            "exposure": "Facteur ou modèle pronostique",
            "outcome": "Événement pronostique",
        },
        "question diagnostique": {
            "intervention": "Test ou outil évalué",
            "comparison": "Référence diagnostique",
            "outcome": "Performance diagnostique",
        },
        "question de validité / validation": {
            "intervention": "Outil, test ou algorithme évalué",
            "comparison": "Référence ou comparateur",
            "outcome": "Propriété évaluée",
        },
        "question qualitative": {
            "outcome": "Phénomène étudié",
            "exposure": "Contexte ou sujet étudié",
        },
        "question méthodologique": {
            "population": "Population ou données concernées",
            "intervention": "Méthode ou approche étudiée",
            "comparison": "Méthode de comparaison",
            "outcome": "Problème méthodologique ou aspect évalué",
            "exposure": "Méthode ou sujet étudié",
        },
        "question statistique": {
            "population": "Population ou jeu de données concerné",
            "intervention": "Méthode statistique étudiée",
            "comparison": "Méthode statistique de comparaison",
            "outcome": "Critère de comparaison",
            "exposure": "Variable ou approche étudiée",
        },
    }

    return adapted_labels.get(subject_type, {}).get(key, default_labels.get(key, key.capitalize()))
