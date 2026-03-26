import json
from pathlib import Path

from claude_helper import get_anthropic_client
from claude_helper import get_openai_client
from claude_helper import normalize_result
from claude_helper import parse_response
from services.concept_classifier import ROLE_LABELS


SKILL_DIR = Path(__file__).resolve().parent.parent / "files_2"
PROMPT_PATH = SKILL_DIR / "prompt.md"
EXAMPLES_PATH = SKILL_DIR / "examples.json"

DEFAULT_LIBRARIAN_PROMPT = """# System Prompt — Librarian Search Strategy Query Builder

You are a librarian-grade search strategy assistant with expertise in systematic and scoping
reviews, evidence synthesis, and database-specific query syntax.

Your role is to help the user transform any free-text research topic into a usable, transparent,
and well-documented bibliographic search strategy.

Core rules:
- Broad before narrow
- Fewer, stronger terms
- Never put ranking concepts in the query
- Context concepts enter the query only if central
- Do not force PICO when it does not fit
- Keep search terms in English for PubMed
- Use concept roles: core, refinement, ranking, context
- Comparators help understanding but should not become separate active filters by default
- Broad query must stay plausible and readable
"""


def _load_skill_assets() -> tuple[str, list]:
    prompt_text = DEFAULT_LIBRARIAN_PROMPT
    examples = []

    if PROMPT_PATH.exists():
        prompt_text = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if EXAMPLES_PATH.exists():
        examples = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))

    return prompt_text, examples


def _build_examples_snippet(examples: list) -> str:
    selected = []
    for example in examples[:2]:
        payload = example.get("expected_output") or example.get("expected_output_sketch") or {}
        selected.append(
            {
                "input": example.get("input", ""),
                "output": payload,
            }
        )
    if not selected:
        return "[]"
    return json.dumps(selected, ensure_ascii=False, indent=2)


def _build_librarian_prompt(question: str) -> str:
    prompt_text, examples = _load_skill_assets()
    examples_snippet = _build_examples_snippet(examples)
    return (
        f"{prompt_text}\n\n"
        "Return ONLY strict JSON using this schema:\n"
        "{\n"
        '  "understanding": "short restatement in user language",\n'
        '  "research_type": "short label",\n'
        '  "pico_applicable": true|false|null,\n'
        '  "concepts": [\n'
        "    {\n"
        '      "label": "string",\n'
        '      "role": "core|refinement|ranking|context",\n'
        '      "synonyms": ["string"],\n'
        '      "controlled_vocab": {"MeSH": "string or null"},\n'
        '      "note": "string or null"\n'
        "    }\n"
        "  ],\n"
        '  "broad_query": "PubMed query string",\n'
        '  "focused_query": "PubMed query string or empty string",\n'
        '  "notes": ["string"]\n'
        "}\n\n"
        "Use the examples below for calibration only.\n"
        f"{examples_snippet}\n\n"
        f'User topic: "{question}"'
    )


def _call_with_anthropic(prompt: str) -> dict:
    client = get_anthropic_client()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1400,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_response(message.content[0].text)


def _call_with_openai(prompt: str) -> dict:
    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1400,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_response(response.choices[0].message.content)


def _normalize_mesh_term(value: str) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned or cleaned.lower().startswith("no direct"):
        return None
    if "[mesh" in cleaned.lower():
        term = cleaned.split("[", 1)[0].strip().strip('"')
        return f'"{term}"[MeSH Terms]'
    return None


def _normalize_notes(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_controlled_vocab(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        return {"MeSH": value.strip()}
    return {}


def _query_contains_concept(query: str, concept: dict) -> bool:
    haystack = str(query or "").lower()
    label = str(concept.get("label") or "").lower()
    if label and label in haystack:
        return True
    for term in concept.get("synonyms") or []:
        normalized = str(term or "").strip().strip('"').lower()
        if normalized and normalized in haystack:
            return True
    return False


def _map_role_to_filter_state(role: str, broad_query: str, concept: dict) -> tuple[bool, int | None]:
    if role == "core":
        return True, 1
    if role == "refinement":
        return True, 2
    if role == "context":
        return (True, 1) if _query_contains_concept(broad_query, concept) else (True, 2)
    return False, None


def _build_internal_concepts(payload: dict) -> tuple[list, list]:
    broad_query = payload.get("broad_query", "") or ""
    search_elements = []
    classified_concepts = []

    for index, concept in enumerate(payload.get("concepts") or []):
        if not isinstance(concept, dict):
            continue
        role = concept.get("role")
        if role not in ROLE_LABELS:
            role = "core"
        raw_synonyms = concept.get("synonyms") or []
        if isinstance(raw_synonyms, str):
            raw_synonyms = [raw_synonyms]
        synonyms = [str(item).strip() for item in raw_synonyms if str(item).strip()]
        if not synonyms:
            label = str(concept.get("label") or f"Concept {index + 1}").strip()
            if label:
                synonyms = [label]
        search_filter, priority = _map_role_to_filter_state(role, broad_query, concept)
        controlled_vocab = _normalize_controlled_vocab(concept.get("controlled_vocab"))
        mesh = _normalize_mesh_term(controlled_vocab.get("MeSH"))
        tiab = " OR ".join(dict.fromkeys(synonyms))
        label = concept.get("label", f"Concept {index + 1}")
        note = str(concept.get("note") or "")

        search_elements.append(
            {
                "label": label,
                "tiab": tiab,
                "mesh": mesh,
                "search_filter": search_filter,
                "priority": priority,
                "reason": note,
            }
        )
        classified_concepts.append(
            {
                "id": f"concept_{index}",
                "label": label,
                "role": role,
                "synonyms": synonyms,
                "controlled_terms": [mesh] if mesh else [],
                "search_filter": search_filter,
                "priority": priority,
                "reason": note,
            }
        )

    return search_elements, classified_concepts


def _build_query_package_from_payload(result: dict, payload: dict) -> dict:
    broad_query = str(payload.get("broad_query") or "").strip()
    focused_query = str(payload.get("focused_query") or "").strip()
    if not focused_query:
        focused_query = broad_query

    search_elements = result.get("search_elements") or []
    large_elements_used = [element.get("label", "Concept") for element in search_elements if element.get("search_filter") and element.get("priority") == 1]
    strict_elements_used = [element.get("label", "Concept") for element in search_elements if element.get("search_filter")]
    excluded = [
        {"label": element.get("label", "Concept"), "reason": element.get("reason", "")}
        for element in search_elements
        if not element.get("search_filter")
    ]

    return {
        "result": result,
        "strategy_source": "librarian_strategy",
        "strategy": {
            "wide": {"elements": [e for e in search_elements if e.get("search_filter") and e.get("priority") == 1], "elements_used": large_elements_used},
            "narrow": {"elements": [e for e in search_elements if e.get("search_filter")], "elements_used": strict_elements_used},
            "excluded": excluded,
            "is_identical": broad_query == focused_query,
        },
        "platform_outputs": {
            "PubMed": {
                "large": {
                    "query": broad_query,
                    "elements_used": large_elements_used,
                    "count": -1,
                },
                "strict": {
                    "query": focused_query,
                    "elements_used": strict_elements_used,
                    "count": -1,
                },
                "excluded": excluded,
                "is_identical": broad_query == focused_query,
            }
        },
        "broad_query": broad_query,
        "focused_query": focused_query,
        "strict_query": focused_query,
    }


def adapt_librarian_strategy_payload(question: str, payload: dict) -> dict | None:
    if not isinstance(payload, dict):
        return None

    broad_query = str(
        payload.get("broad_query")
        or payload.get("broad_query_pubmed")
        or ""
    ).strip()
    if not broad_query:
        return None

    normalized_payload = dict(payload)
    normalized_payload["understanding"] = (
        payload.get("understanding")
        or payload.get("topic_restatement")
        or question
    )
    normalized_payload["research_type"] = (
        payload.get("research_type")
        or payload.get("topic_type")
        or ""
    )
    normalized_payload["notes"] = _normalize_notes(payload.get("notes"))
    normalized_payload["broad_query"] = broad_query
    normalized_payload["focused_query"] = str(
        payload.get("focused_query") or payload.get("focused_query_pubmed") or ""
    ).strip()

    search_elements, classified_concepts = _build_internal_concepts(normalized_payload)
    result = normalize_result(
        {
            "intent": "structure",
            "framework": "PICO" if normalized_payload.get("pico_applicable") else None,
            "components": {},
            "search_elements": search_elements,
            "classified_concepts": classified_concepts,
            "parsed_concepts": classified_concepts,
            "research_question_fr": normalized_payload.get("understanding"),
            "research_question_en": normalized_payload.get("understanding"),
            "explanation": normalized_payload.get("research_type") or normalized_payload.get("understanding"),
            "librarian_strategy": {
                "raw": normalized_payload,
                "understanding": normalized_payload.get("understanding"),
                "research_type": normalized_payload.get("research_type"),
                "broad_query": normalized_payload.get("broad_query"),
                "focused_query": normalized_payload.get("focused_query"),
                "notes": normalized_payload.get("notes") or [],
            },
            "strategy_source": "librarian_strategy",
        }
    )
    result["classified_concepts"] = classified_concepts
    result["parsed_concepts"] = classified_concepts
    query_package = _build_query_package_from_payload(result, normalized_payload)
    return {
        "result": result,
        "query_package": query_package,
        "raw_skill_output": normalized_payload,
    }


def analyze_with_librarian_strategy(question: str) -> dict:
    prompt = _build_librarian_prompt(question)
    try:
        return _call_with_anthropic(prompt)
    except Exception:
        return _call_with_openai(prompt)


def get_librarian_strategy_analysis(question: str) -> dict | None:
    try:
        raw_payload = analyze_with_librarian_strategy(question)
        return adapt_librarian_strategy_payload(question, raw_payload)
    except Exception:
        return None


def build_query_package_from_librarian_result(result: dict) -> dict | None:
    strategy = (result or {}).get("librarian_strategy") or {}
    broad_query = str(strategy.get("broad_query") or "").strip()
    if not broad_query:
        return None
    payload = {
        "broad_query": broad_query,
        "focused_query": str(strategy.get("focused_query") or "").strip(),
    }
    return _build_query_package_from_payload(result or {}, payload)
