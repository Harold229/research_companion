"""
Presentation helpers for pedagogical question typing and component labels.
"""


def get_question_presentation(result: dict) -> dict:
    framework = result.get("framework")
    intent = result.get("intent")
    explanation = (result.get("explanation") or "").lower()
    components = result.get("components") or {}
    has_exposure = bool(components.get("exposure"))

    text = " ".join(
        str(value).lower()
        for value in [
            explanation,
            components.get("intervention"),
            components.get("outcome"),
            components.get("exposure"),
            components.get("comparison"),
        ]
        if value
    )

    if intent == "explore":
        question_type = "question exploratoire"
    elif framework == "SPIDER" or any(word in text for word in ["qualitative", "perception", "vécu", "expérience", "barrières"]):
        question_type = "question qualitative"
    elif any(word in text for word in ["prévalence", "prevalence", "incidence"]):
        question_type = "question de prévalence"
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
        question_type = "question de facteurs associés"
    elif any(word in text for word in ["intervention", "treatment", "traitement", "efficacité", "education", "éducation"]):
        question_type = "question interventionnelle"
    else:
        question_type = "question descriptive"

    show_framework = framework in {"PEO", "SPIDER"} or (
        framework == "PICO" and question_type == "question interventionnelle"
    )

    return {
        "question_type": question_type,
        "show_framework": show_framework,
        "framework": framework,
    }


def get_visible_explanation(result: dict, presentation: dict) -> str:
    question_type = presentation.get("question_type")
    raw_explanation = (result.get("explanation") or "").strip()

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
            raw_explanation or
            "Question interventionnelle visant à évaluer l’effet d’une intervention sur un critère de jugement."
        ),
        "question qualitative": (
            raw_explanation or
            "Question qualitative visant à comprendre des perceptions, expériences, barrières ou facilitateurs."
        ),
    }

    if question_type in {"question de prévalence", "question descriptive", "question de facteurs associés", "question exploratoire"}:
        return explanations[question_type]

    return explanations.get(question_type) or raw_explanation


def get_component_label(key: str, presentation: dict) -> str:
    question_type = presentation.get("question_type")

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
            "outcome": "Événement ou critère étudié",
        },
        "question interventionnelle": {
            "intervention": "Intervention étudiée",
            "outcome": "Critère de jugement",
        },
        "question qualitative": {
            "outcome": "Phénomène étudié",
            "exposure": "Contexte ou sujet étudié",
        },
    }

    return adapted_labels.get(question_type, {}).get(key, default_labels.get(key, key.capitalize()))
