import anthropic
import streamlit as st
import os
import time
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from prompt_core import PROMPT_CORE
from services.concept_classifier import build_classified_concepts
from services.concept_classifier import classify_concept_role

load_dotenv()


# ═══════════════════════════════════════════════════════════════
# CLIENTS API
# ═══════════════════════════════════════════════════════════════

def get_anthropic_client():
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"].strip()
    except Exception:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return anthropic.Anthropic(api_key=api_key)


def get_openai_client():
    try:
        api_key = st.secrets["OPENAI_API_KEY"].strip()
    except Exception:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
    return OpenAI(api_key=api_key)


# ═══════════════════════════════════════════════════════════════
# CHARGEMENT DES EXEMPLES
# ═══════════════════════════════════════════════════════════════

_EXAMPLES_CACHE = None
DEFAULT_CANONICAL_RESULT = {
    "intent": "structure",
    "framework": None,
    "components": {},
    "search_elements": [],
    "classified_concepts": [],
    "parsed_concepts": [],
    "geography": {
        "country": None,
        "region": None,
        "continent": None,
    },
    "research_level": 2,
}

def load_examples() -> list:
    """Charge examples.json une seule fois (cache mémoire)."""
    global _EXAMPLES_CACHE
    if _EXAMPLES_CACHE is not None:
        return _EXAMPLES_CACHE

    examples_path = Path(__file__).parent / "examples.json"
    if not examples_path.exists():
        raise FileNotFoundError(
            f"examples.json introuvable dans {examples_path.parent}. "
            "Place-le à côté de claude_helper.py."
        )
    with open(examples_path, "r", encoding="utf-8") as f:
        _EXAMPLES_CACHE = json.load(f)
    return _EXAMPLES_CACHE


# ═══════════════════════════════════════════════════════════════
# SÉLECTION DYNAMIQUE DES EXEMPLES
# ═══════════════════════════════════════════════════════════════

KEYWORD_TO_TAGS = {
    # Framework / concept triggers
    "connaissance": ["M-KAP", "PEO"],
    "savoir": ["M-KAP", "PEO"],
    "savent": ["M-KAP", "PEO"],
    "connaissent": ["M-KAP", "PEO"],
    "connaissances": ["M-KAP", "PEO"],
    "pratique": ["M-KAP", "PEO"],
    "pratiquent": ["M-KAP", "PEO"],
    "attitudes": ["M-KAP", "PEO"],
    "maîtrisent": ["M-KAP", "PEO"],
    "comprennent": ["M-KAP", "PEO"],
    "gèrent": ["M-KAP", "PEO"],
    "appliquent": ["M-KAP", "PEO"],
    "respectent": ["M-KAP", "PEO"],
    "adhérence": ["M-ADH", "PEO"],
    "observance": ["M-ADH", "PEO"],
    "compliance": ["M-ADH", "PEO"],
    "vécu": ["SPIDER", "qualitative"],
    "perception": ["SPIDER", "qualitative"],
    "expérience": ["SPIDER", "qualitative"],
    "barrières": ["SPIDER", "qualitative"],
    "prévalence": ["M-PREV", "PICO"],
    "incidence": ["M-PREV", "PICO"],
    "facteurs de risque": ["M-RISK", "PICO"],
    "déterminants": ["M-RISK", "PICO"],
    "mortalité": ["M-MORT", "PICO"],
    "morbidité": ["M-MORT", "PICO"],
    "survie": ["M-MORT", "PICO"],
    "traitement": ["M-THER", "PICO"],
    "prise en charge": ["M-THER", "PICO"],
    "efficacité": ["PICO", "comparison"],
    "vs": ["PICO", "comparison"],
    "éducation": ["M-EDU", "PICO"],
    "pairs": ["M-PEER", "PEO"],
    "influence sociale": ["M-PEER", "PEO"],
    # Geo triggers
    "afrique": ["geo_africa"],
    "bénin": ["geo_africa"],
    "mali": ["geo_africa"],
    "sénégal": ["geo_africa"],
    "cameroun": ["geo_africa"],
    "togo": ["geo_africa"],
    "niger": ["geo_africa"],
    "rwanda": ["geo_africa"],
    "éthiopie": ["geo_africa"],
    "burkina": ["geo_africa"],
    "côte d'ivoire": ["geo_africa"],
}


def select_examples(question: str, intent: str, max_examples: int = 3) -> str:
    """
    Sélectionne les 2-3 exemples les plus pertinents depuis examples.json.
    Retourne le texte formaté prêt à injecter dans le prompt.
    """
    examples_db = load_examples()
    question_lower = question.lower()

    # 1. Construire les tags cibles
    # intent vide = auto-détection LLM → ne pas polluer les tags avec ""
    target_tags = {intent} if intent else set()
    for keyword, tags in KEYWORD_TO_TAGS.items():
        if keyword in question_lower:
            target_tags.update(tags)

    # 2. Scorer chaque exemple
    scored = []
    for ex in examples_db:
        ex_tags = set(ex["tags"])
        overlap = len(target_tags & ex_tags)
        scored.append((overlap, ex))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 3. Sélectionner top N en diversifiant les frameworks
    selected = []
    frameworks_seen = set()

    for score, ex in scored:
        if len(selected) >= max_examples:
            break

        fw = None
        for tag in ex["tags"]:
            if tag in ("PEO", "PICO", "SPIDER", "PICOTS"):
                fw = tag
                break

        if fw and fw in frameworks_seen and len(selected) < max_examples - 1:
            continue

        selected.append(ex)
        if fw:
            frameworks_seen.add(fw)

    # 4. Pour structure (explicite ou détectée), toujours inclure exemple J (démo mesh null)
    _structure_tags = {"PICO", "PEO", "SPIDER", "M-KAP", "M-ADH", "M-PREV",
                       "M-RISK", "M-MORT", "M-THER", "M-EDU", "M-PEER"}
    is_structure = (intent == "structure") or (
        not intent and bool(target_tags & _structure_tags)
    )
    if is_structure:
        j_example = next((ex for ex in examples_db if ex["id"] == "J"), None)
        if j_example and j_example not in selected:
            if len(selected) >= max_examples:
                selected[-1] = j_example
            else:
                selected.append(j_example)

    # 5. Formater pour injection
    parts = []
    for ex in selected:
        example_json_str = json.dumps(ex["example_json"], indent=2, ensure_ascii=False)
        parts.append(
            f'--- Exemple {ex["id"]} ---\n'
            f'Question : "{ex["question_fr"]}"\n'
            f'Intent : {ex["intent"]}\n\n'
            f'{example_json_str}'
        )

    return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# CONSTRUCTION DU PROMPT FINAL
# ═══════════════════════════════════════════════════════════════

def build_prompt(question: str, intent: str) -> str:
    """Assemble le prompt core + les exemples dynamiques."""
    examples_text = select_examples(question, intent, max_examples=3)
    return PROMPT_CORE.format(
        question=question,
        intent=intent,
        examples=examples_text
    )


# ═══════════════════════════════════════════════════════════════
# PARSING RÉPONSE
# ═══════════════════════════════════════════════════════════════

def parse_response(text: str) -> dict:
    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1 and start < end:
            return json.loads(clean[start:end + 1])
        raise ValueError("Invalid JSON response from AI provider.")


def normalize_search_elements(search_elements) -> list:
    if not isinstance(search_elements, list):
        return []

    normalized = []
    for element in search_elements:
        if not isinstance(element, dict):
            continue
        normalized.append({
            **element,
            "label": element.get("label", "Concept"),
            "tiab": element.get("tiab"),
            "mesh": element.get("mesh"),
            "search_filter": bool(element.get("search_filter")),
            "priority": element.get("priority"),
            "reason": element.get("reason", ""),
        })
    return normalized


def _normalize_text(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _split_or_terms(value: str) -> list:
    return [term.strip() for term in str(value or "").split(" OR ") if term.strip()]


def _split_treatment_candidates(value: str) -> list:
    normalized = str(value or "").strip()
    if not normalized:
        return []

    pieces = [normalized]
    separators = (" versus ", " vs ", " compared with ", " compared to ", " against ", " and ", " or ", "/")

    for separator in separators:
        updated = []
        for piece in pieces:
            if separator in piece.lower():
                marker = separator.strip()
                updated.extend(part.strip(" ,;:") for part in piece.split(marker))
            else:
                updated.append(piece)
        pieces = updated

    candidates = []
    for piece in pieces:
        candidate = _normalize_text(piece)
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _tokenize_for_quality(value: str) -> list:
    return [
        token
        for token in _normalize_text(value).replace("-", " ").split()
        if token
    ]


def _is_acronym(term: str) -> bool:
    cleaned = str(term or "").replace(".", "").strip()
    return cleaned.isupper() and 2 <= len(cleaned) <= 6


def _is_prevalence_topic(data: dict) -> bool:
    components = data.get("components") or {}
    text = " ".join(
        _normalize_text(value)
        for value in (
            components.get("outcome"),
            data.get("explanation"),
            data.get("research_question_fr"),
            data.get("research_question_en"),
        )
        if value
    )
    prevalence_markers = (
        "prévalence",
        "prevalence",
        "question de prévalence",
    )
    return any(marker in text for marker in prevalence_markers)


def _is_comparison_element(element: dict, comparison_text: str) -> bool:
    comparison_candidates = _split_treatment_candidates(comparison_text)
    if not comparison_candidates:
        return False

    label = _normalize_text(element.get("label"))
    reason = _normalize_text(element.get("reason"))
    tiab_terms = [_normalize_text(term).strip('"') for term in _split_or_terms(element.get("tiab", ""))]

    if any(keyword in label or keyword in reason for keyword in ("compar", "comparateur", "comparator", "reference standard", "gold standard")):
        return True
    if any(candidate == label for candidate in comparison_candidates):
        return True
    if any(candidate in tiab_terms for candidate in comparison_candidates):
        return True
    return False


def _is_intervention_element(element: dict, intervention_text: str) -> bool:
    intervention_candidates = _split_treatment_candidates(intervention_text)
    if not intervention_candidates:
        return False

    label = _normalize_text(element.get("label"))
    tiab_terms = [_normalize_text(term).strip('"') for term in _split_or_terms(element.get("tiab", ""))]

    if any(candidate == label for candidate in intervention_candidates):
        return True
    if any(candidate in tiab_terms for candidate in intervention_candidates):
        return True
    return False


def _is_reference_like_comparison(comparison_text: str) -> bool:
    comparison = _normalize_text(comparison_text)
    markers = (
        "reference",
        "gold standard",
        "standard care",
        "usual care",
        "placebo",
        "control",
        "comparateur",
        "comparateur de référence",
        "test de référence",
    )
    return any(marker in comparison for marker in markers)


def _merge_unique_terms(primary_value: str, secondary_value: str) -> str:
    merged = []
    for term in _split_or_terms(primary_value) + _split_or_terms(secondary_value):
        if term not in merged:
            merged.append(term)
    return " OR ".join(merged)


def _merge_intervention_and_comparison_elements(search_elements: list, components: dict) -> list:
    intervention_text = (components or {}).get("intervention")
    comparison_text = (components or {}).get("comparison")

    if not intervention_text or not comparison_text or _is_reference_like_comparison(comparison_text):
        return search_elements

    intervention_index = None
    comparison_index = None
    merged = [dict(element) for element in search_elements]

    for index, element in enumerate(merged):
        if intervention_index is None and _is_intervention_element(element, intervention_text):
            intervention_index = index
        if comparison_index is None and _is_comparison_element(element, comparison_text):
            comparison_index = index

    if intervention_index is None or comparison_index is None or intervention_index == comparison_index:
        return merged

    intervention_element = dict(merged[intervention_index])
    comparison_element = dict(merged[comparison_index])

    intervention_element["tiab"] = _merge_unique_terms(
        intervention_element.get("tiab", ""),
        comparison_element.get("tiab", ""),
    )
    intervention_element["mesh"] = _merge_unique_terms(
        intervention_element.get("mesh", ""),
        comparison_element.get("mesh", ""),
    ) or None
    intervention_element["reason"] = (
        intervention_element.get("reason")
        or "Bloc intervention élargi pour couvrir aussi le produit comparé."
    )

    comparison_element["search_filter"] = False
    comparison_element["priority"] = None
    comparison_element["reason"] = (
        "Produit comparé absorbé dans le même bloc que l'intervention, puis retiré comme filtre séparé."
    )

    merged[intervention_index] = intervention_element
    merged[comparison_index] = comparison_element
    return merged


def _merge_intervention_family_elements(search_elements: list, components: dict) -> list:
    intervention_text = (components or {}).get("intervention")
    comparison_text = (components or {}).get("comparison")

    candidates = _split_treatment_candidates(intervention_text)
    if comparison_text and not _is_reference_like_comparison(comparison_text):
        for candidate in _split_treatment_candidates(comparison_text):
            if candidate not in candidates:
                candidates.append(candidate)

    if len(candidates) < 2:
        return [dict(element) for element in search_elements]

    merged = [dict(element) for element in search_elements]
    matched_indices = []
    for index, element in enumerate(merged):
        if _is_intervention_element(element, intervention_text) or _is_comparison_element(element, comparison_text):
            matched_indices.append(index)

    if len(matched_indices) < 2:
        return merged

    anchor_index = next((index for index in matched_indices if merged[index].get("search_filter")), matched_indices[0])
    anchor = dict(merged[anchor_index])

    for index in matched_indices:
        if index == anchor_index:
            continue
        other = dict(merged[index])
        anchor["tiab"] = _merge_unique_terms(anchor.get("tiab", ""), other.get("tiab", ""))
        anchor["mesh"] = _merge_unique_terms(anchor.get("mesh", ""), other.get("mesh", "")) or None
        if not anchor.get("reason"):
            anchor["reason"] = "Interventions regroupées dans un seul bloc OR."

        other["search_filter"] = False
        other["priority"] = None
        other["reason"] = "Intervention regroupée avec les autres produits dans un seul bloc OR, puis retirée comme filtre séparé."
        merged[index] = other

    merged[anchor_index] = anchor
    return merged


def _sanitize_comparison_search_elements(search_elements: list, components: dict) -> list:
    intervention_text = (components or {}).get("intervention")
    comparison_text = (components or {}).get("comparison")
    if not comparison_text:
        return search_elements

    sanitized = _merge_intervention_family_elements(search_elements, components)
    sanitized = _merge_intervention_and_comparison_elements(sanitized, components)
    final_elements = []
    for element in sanitized:
        normalized = dict(element)
        if _is_comparison_element(normalized, comparison_text) and not _is_intervention_element(normalized, intervention_text):
            if normalized.get("search_filter"):
                normalized["search_filter"] = False
                normalized["priority"] = None
                normalized["reason"] = "Comparateur gardé visible pour la compréhension, mais retiré du filtrage de la requête."
        final_elements.append(normalized)
    return final_elements


def _is_methodological_topic(data: dict) -> bool:
    components = data.get("components") or {}
    text = " ".join(
        _normalize_text(value)
        for value in (
            data.get("explanation"),
            data.get("research_question_fr"),
            data.get("research_question_en"),
            components.get("intervention"),
            components.get("exposure"),
            components.get("outcome"),
        )
        if value
    )
    markers = (
        "méthodolog",
        "methodolog",
        "statist",
        "causal inference",
        "time discret",
        "missing data",
        "imputation",
        "regression",
        "g-formula",
        "tmle",
        "inverse probability",
    )
    return any(marker in text for marker in markers)


def _is_prevalence_measure_element(element: dict) -> bool:
    label = _normalize_text(element.get("label"))
    reason = _normalize_text(element.get("reason"))
    terms = [_normalize_text(term) for term in _split_or_terms(element.get("tiab", ""))]
    generic_terms = {
        "prevalence",
        "incidence",
        "frequency",
        "epidemiology",
        "burden",
    }

    if "preval" in label or "epidemiolog" in label or "mesure" in label:
        return True
    if any(keyword in reason for keyword in ("prévalence", "prevalence", "épidémiolog", "epidemiolog")):
        return True
    if terms and all(term in generic_terms for term in terms):
        return True
    return False


def _sanitize_prevalence_search_elements(search_elements: list) -> list:
    explicit_prevalence_terms = {
        "prevalence",
        "point prevalence",
        "period prevalence",
        "lifetime prevalence",
    }
    sanitized = []

    for element in search_elements:
        normalized = dict(element)
        if _is_prevalence_measure_element(normalized):
            terms = _split_or_terms(normalized.get("tiab", ""))
            kept_terms = [term for term in terms if _normalize_text(term) in explicit_prevalence_terms]
            normalized["tiab"] = " OR ".join(kept_terms) if kept_terms else "prevalence"
            normalized["mesh"] = None

            if normalized.get("search_filter"):
                if normalized.get("priority") == 2:
                    normalized["search_filter"] = True
                    normalized["priority"] = 2
                    normalized["reason"] = (
                        "Concept de prévalence conservé seulement comme affinement explicite."
                    )
                else:
                    normalized["search_filter"] = False
                    normalized["priority"] = None
                    normalized["reason"] = (
                        "Concept de prévalence gardé visible mais retiré du filtrage large pour éviter une requête trop rigide."
                    )
        sanitized.append(normalized)

    return sanitized


def _sanitize_methodological_search_elements(search_elements: list) -> list:
    generic_weak_terms = {
        "analysis",
        "analyses",
        "bias",
        "causality",
        "method",
        "methods",
        "methodological",
        "model",
        "models",
        "statistical",
        "statistics",
        "study",
        "studies",
    }
    sanitized = []

    for element in search_elements:
        normalized = dict(element)
        role = classify_concept_role(normalized)
        if role == "context":
            sanitized.append(normalized)
            continue

        label_tokens = set(_tokenize_for_quality(normalized.get("label", "")))
        kept_terms = []
        for term in _split_or_terms(normalized.get("tiab", "")):
            normalized_term = _normalize_text(term)
            term_tokens = set(_tokenize_for_quality(term))
            if normalized_term in generic_weak_terms:
                continue
            if len(label_tokens) >= 2 and not _is_acronym(term):
                if term_tokens and not (term_tokens & label_tokens):
                    continue
            if term not in kept_terms:
                kept_terms.append(term)

        if kept_terms:
            normalized["tiab"] = " OR ".join(kept_terms[:4])

        sanitized.append(normalized)

    return sanitized


def normalize_result(result: dict | None) -> dict:
    """Apply the minimal JSON fallbacks required by the SPEC."""
    data = result if isinstance(result, dict) else {}

    intent = data.get("intent")
    if intent not in {"explore", "structure"}:
        intent = "structure"

    framework = data.get("framework")
    if framework not in {"PICO", "PEO", "SPIDER"}:
        framework = None

    components = data.get("components")
    if not isinstance(components, dict):
        components = {}

    search_elements = normalize_search_elements(data.get("search_elements"))
    search_elements = _sanitize_comparison_search_elements(search_elements, components)
    if _is_prevalence_topic(data):
        search_elements = _sanitize_prevalence_search_elements(search_elements)
    if _is_methodological_topic(data):
        search_elements = _sanitize_methodological_search_elements(search_elements)
    classified_concepts = build_classified_concepts(search_elements)

    geography = data.get("geography")
    if not isinstance(geography, dict):
        geography = {}

    research_level = data.get("research_level")
    if research_level not in {1, 2, 3}:
        research_level = 2

    return {
        **DEFAULT_CANONICAL_RESULT,
        **data,
        "intent": intent,
        "framework": framework,
        "components": components,
        "search_elements": search_elements,
        "classified_concepts": classified_concepts,
        "parsed_concepts": classified_concepts,
        "geography": {
            "country": geography.get("country"),
            "region": geography.get("region"),
            "continent": geography.get("continent"),
        },
        "research_level": research_level,
    }


# ═══════════════════════════════════════════════════════════════
# APPELS API
# ═══════════════════════════════════════════════════════════════

def analyze_with_claude(question: str, intent: str = "") -> dict:
    client = get_anthropic_client()
    prompt = build_prompt(question, intent)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return normalize_result(parse_response(message.content[0].text))


def analyze_with_openai(question: str, intent: str = "") -> dict:
    client = get_openai_client()
    prompt = build_prompt(question, intent)
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return normalize_result(parse_response(response.choices[0].message.content))


def analyze_research_question(question: str, intent: str = "") -> dict:
    """Essaie Claude, fallback sur OpenAI."""
    for attempt in range(2):
        try:
            return analyze_with_claude(question, intent)
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 1:
                time.sleep(3)
            else:
                break
        except Exception:
            break

    try:
        return analyze_with_openai(question, intent)
    except Exception:
        raise Exception("Both AI providers are unavailable. Please try again later.")


# ═══════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    questions = [
        ("est-ce qu'il y a des études sur l'hyperkaliémie chez les enfants", "explore"),
        ("connaissance des médecins sur la prise en charge de l'hyperkaliémie au Bénin", "structure"),
        ("prévalence du diabète chez les enfants au Mali", "structure"),
        ("adhérence au traitement antirétroviral chez les adolescents au Cameroun", "structure"),
    ]

    for question, intent in questions:
        print(f"\n{'='*60}")
        print(f"INTENT: {intent.upper()}")
        print(f"QUESTION: {question}")

        # Montrer quels exemples sont sélectionnés
        examples_db = load_examples()
        target_tags = {intent}
        q_lower = question.lower()
        for kw, tags in KEYWORD_TO_TAGS.items():
            if kw in q_lower:
                target_tags.update(tags)
        print(f"TAGS DÉTECTÉS: {sorted(target_tags)}")

        examples_text = select_examples(question, intent)
        for line in examples_text.split("\n"):
            if line.startswith("--- Exemple"):
                print(f"  → {line}")

        prompt = build_prompt(question, intent)
        print(f"TAILLE PROMPT: {len(prompt)} caractères")

        result = analyze_research_question(question, intent=intent)
        print(json.dumps(result, indent=2, ensure_ascii=False))
