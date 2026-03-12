"""
Agent léger de lecture titre + abstract pour prioriser une shortlist.
"""

import json

import anthropic

from claude_helper import get_anthropic_client
from claude_helper import get_openai_client
from reading_prioritization import priority_rank


SHORTLIST_MAX_ARTICLES = 10


def _truncate(text: str, max_chars: int = 1800) -> str:
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


def build_shortlist_for_agent(prioritized: dict, max_articles: int = SHORTLIST_MAX_ARTICLES) -> list:
    articles = prioritized.get("articles", [])
    sorted_articles = sorted(
        articles,
        key=lambda item: (priority_rank(item.get("priority")), -item.get("score", 0), item.get("title", "")),
    )

    shortlist = []
    for index, article in enumerate(sorted_articles[:max_articles], start=1):
        shortlist.append({
            "article_id": f"A{index}",
            "pmid": article.get("pmid"),
            "title": article.get("title"),
            "abstract": _truncate(article.get("abstract")),
            "journal": article.get("journal"),
            "year": article.get("year"),
            "authors": article.get("authors", []),
        })
    return shortlist


def _build_agent_prompt(shortlist: list, focus_label: str, custom_goal: str = "") -> str:
    goal_text = custom_goal.strip() or focus_label
    shortlist_json = json.dumps(shortlist, ensure_ascii=False, indent=2)

    return f"""
Tu aides à prioriser une shortlist d'articles pour la lecture.

Objectif de lecture prioritaire : {goal_text}

Règles :
- base-toi uniquement sur le titre, l'abstract et les métadonnées fournies
- ne prétends pas avoir lu le full text
- classe chaque article en :
  - Très pertinent
  - Pertinent
  - À vérifier
- donne une justification courte et concrète
- la justification doit rester sobre, en français, et expliquer pourquoi l'article remonte
- si l'article semble seulement partiellement lié à l'objectif, dis-le explicitement

Retourne uniquement un JSON valide de cette forme :
{{
  "articles": [
    {{
      "article_id": "A1",
      "priority": "Très pertinent",
      "reason": "Répond directement à l’objectif de lecture et correspond à la population étudiée."
    }}
  ]
}}

Shortlist :
{shortlist_json}
""".strip()


def _assess_with_openai(prompt: str) -> dict:
    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(response.choices[0].message.content)


def _assess_with_anthropic(prompt: str) -> dict:
    client = get_anthropic_client()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(message.content[0].text)


def assess_shortlist_with_agent(shortlist: list, focus_label: str, custom_goal: str = "") -> dict:
    prompt = _build_agent_prompt(shortlist, focus_label, custom_goal)

    try:
        return _assess_with_openai(prompt)
    except Exception:
        pass

    try:
        return _assess_with_anthropic(prompt)
    except anthropic.APIStatusError:
        raise
    except Exception:
        raise
