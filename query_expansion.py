"""
Expansion contrôlée de requête à partir d'un petit noyau d'articles.
"""

import json
from copy import deepcopy

import anthropic

from claude_helper import get_anthropic_client
from claude_helper import get_openai_client


EXPANSION_SHORTLIST_MAX = 12
RECOMMENDATION_LABELS = {
    "forte": "Recommandation forte",
    "utile": "Recommandation utile",
    "prudente": "Recommandation prudente",
}


def _truncate(text: str, max_chars: int = 1400) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def _parse_json(text: str) -> dict:
    clean = str(text or "").strip()
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
        raise


def build_expansion_shortlist(articles: list, max_articles: int = EXPANSION_SHORTLIST_MAX) -> list:
    shortlist = []
    for index, article in enumerate((articles or [])[:max_articles], start=1):
        shortlist.append({
            "article_id": f"E{index}",
            "pmid": article.get("pmid"),
            "title": article.get("title"),
            "abstract": _truncate(article.get("abstract")),
            "journal": article.get("journal"),
            "year": article.get("year"),
            "authors": article.get("authors", []),
        })
    return shortlist


def _build_expansion_prompt(shortlist: list, search_elements: list, user_question: str) -> str:
    concept_summary = []
    for element in search_elements or []:
        concept_summary.append({
            "label": element.get("label", "Concept"),
            "current_terms": element.get("tiab", ""),
            "mesh": element.get("mesh"),
            "search_filter": element.get("search_filter"),
            "priority": element.get("priority"),
        })

    return f"""
Tu aides à proposer une expansion prudente de requête bibliographique.

Sujet initial : {user_question}

Règles :
- base-toi uniquement sur les titres, abstracts et métadonnées fournis
- propose au maximum 6 termes en anglais réellement utilisés dans la littérature
- rattache chaque terme à un concept existant uniquement
- n'invente pas de nouveau concept AND séparé
- évite les termes trop génériques, transversaux ou spéculatifs
- privilégie des synonymes, formulations du champ ou termes méthodologiques réellement utiles
- pour chaque proposition, donne :
  - un terme en anglais
  - un concept cible parmi les labels existants
  - une recommandation simple : forte, utile ou prudente
  - une justification courte en français

Retourne uniquement un JSON valide de cette forme :
{{
  "proposals": [
    {{
      "proposal_id": "T1",
      "term": "continuous glucose monitoring",
      "target_concept": "Condition",
      "recommendation": "forte",
      "reason": "Expression retrouvée dans plusieurs abstracts pour désigner le phénomène étudié."
    }}
  ]
}}

Concepts existants :
{json.dumps(concept_summary, ensure_ascii=False, indent=2)}

Shortlist :
{json.dumps(shortlist, ensure_ascii=False, indent=2)}
""".strip()


def _propose_with_openai(prompt: str) -> dict:
    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(response.choices[0].message.content)


def _propose_with_anthropic(prompt: str) -> dict:
    client = get_anthropic_client()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(message.content[0].text)


def propose_query_expansion(shortlist: list, search_elements: list, user_question: str) -> dict:
    prompt = _build_expansion_prompt(shortlist, search_elements, user_question)

    try:
        result = _propose_with_openai(prompt)
    except Exception:
        result = None

    if result is None:
        try:
            result = _propose_with_anthropic(prompt)
        except anthropic.APIStatusError:
            raise
        except Exception:
            raise

    allowed_labels = {item.get("label", "Concept") for item in (search_elements or [])}
    proposals = []
    for item in (result or {}).get("proposals", []):
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", "")).strip()
        target = str(item.get("target_concept", "")).strip()
        if not term or not target or target not in allowed_labels:
            continue
        recommendation = str(item.get("recommendation", "utile")).strip().lower()
        if recommendation not in RECOMMENDATION_LABELS:
            recommendation = "utile"
        proposals.append({
            "proposal_id": item.get("proposal_id") or f"T{len(proposals) + 1}",
            "term": term,
            "target_concept": target,
            "recommendation": recommendation,
            "reason": str(item.get("reason", "")).strip() or "Terme observé dans les premiers articles.",
        })
        if len(proposals) >= 6:
            break

    return {"proposals": proposals}


def apply_expansion_terms(search_elements: list, selected_proposals: list) -> list:
    updated = [deepcopy(element) for element in (search_elements or []) if isinstance(element, dict)]
    grouped = {}
    for proposal in selected_proposals or []:
        target = proposal.get("target_concept")
        term = str(proposal.get("term", "")).strip()
        if target and term:
            grouped.setdefault(target, []).append(term)

    for element in updated:
        label = element.get("label", "Concept")
        additions = grouped.get(label, [])
        if not additions:
            continue
        current_terms = [term.strip() for term in str(element.get("tiab") or "").split(" OR ") if term.strip()]
        for term in additions:
            if term not in current_terms:
                current_terms.append(term)
        element["tiab"] = " OR ".join(current_terms)

    return updated
