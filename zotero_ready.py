"""
Build reusable Zotero-ready article records from prioritized reading results.
"""

import json
from datetime import datetime


def _clean(value: str, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _normalize_tag(value: str) -> str:
    return _clean(value).lower()


def _build_tags(article: dict, prioritized: dict, result: dict) -> list:
    tags = []
    priority = _clean(article.get("priority"))
    if priority:
        tags.append(_normalize_tag(priority))
        if priority in {"Très pertinent", "Pertinent"}:
            tags.append("à lire")

    focus_label = _clean(prioritized.get("focus_label"))
    if focus_label:
        tags.append(_normalize_tag(focus_label))

    components = result.get("components") or {}
    geography = result.get("geography") or {}

    for key in ("population", "outcome", "intervention", "exposure"):
        value = _clean(components.get(key))
        if value:
            tags.append(_normalize_tag(value))

    for value in geography.values():
        cleaned = _clean(value)
        if cleaned:
            tags.append(_normalize_tag(cleaned))

    ranking_source = article.get("ranking_source")
    if ranking_source == "agent":
        tags.append("lecture abstract")

    return list(dict.fromkeys(tag for tag in tags if tag))


def _build_argument_note(article: dict, prioritized: dict) -> str:
    focus_label = _clean(prioritized.get("focus_label"), "l’objectif de lecture")
    reasons = article.get("reasons") or []
    primary_reason = _clean(reasons[0]) if reasons else "Semble utile pour le sujet, mais demande une vérification plus détaillée."
    priority = _clean(article.get("priority"), "À vérifier")

    if priority == "Très pertinent":
        opener = "Article prioritaire"
    elif priority == "Pertinent":
        opener = "Article utile à lire"
    else:
        opener = "Article à vérifier"

    return f"{opener} pour {focus_label} : {primary_reason}"


def build_zotero_ready_export(
    prioritized: dict,
    result: dict,
    *,
    user_question: str,
    reformulated_question: str,
    project_title: str = "",
) -> dict:
    exported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    articles = []

    for article in prioritized.get("articles", []):
        item = {
            "title": _clean(article.get("title")),
            "authors": article.get("authors", []),
            "year": _clean(article.get("year")),
            "source": _clean(article.get("journal")),
            "pmid": _clean(article.get("pmid")),
            "doi": _clean(article.get("doi")),
            "url": _clean(article.get("url")),
            "priority": _clean(article.get("priority")),
            "justification": _clean((article.get("reasons") or [""])[0]),
            "tags": _build_tags(article, prioritized, result),
            "argument_note": _build_argument_note(article, prioritized),
        }
        articles.append(item)

    return {
        "project_title": _clean(project_title),
        "user_question": _clean(user_question),
        "reformulated_question": _clean(reformulated_question),
        "focus_label": _clean(prioritized.get("focus_label")),
        "exported_at": exported_at,
        "articles": articles,
    }


def build_zotero_ready_markdown(export_data: dict) -> str:
    lines = [
        "# Articles retenus et argumentaire",
        "",
        f"- Projet : {_clean(export_data.get('project_title'), 'Sans projet')}",
        f"- Question initiale : {_clean(export_data.get('user_question'), 'Non précisée')}",
        f"- Question reformulée : {_clean(export_data.get('reformulated_question'), 'Non précisée')}",
        f"- Objectif de lecture : {_clean(export_data.get('focus_label'), 'Non précisé')}",
        f"- Exporté le : {_clean(export_data.get('exported_at'), 'Non précisé')}",
        "",
    ]

    for index, article in enumerate(export_data.get("articles", []), start=1):
        lines.extend([
            f"## {index}. {_clean(article.get('title'), 'Article sans titre')}",
            f"- Priorité : {_clean(article.get('priority'), 'À vérifier')}",
            f"- Auteurs : {', '.join(article.get('authors', [])) or 'Non précisés'}",
            f"- Année : {_clean(article.get('year'), 'Non précisée')}",
            f"- Source : {_clean(article.get('source'), 'Non précisée')}",
            f"- PMID : {_clean(article.get('pmid'), 'Non précisé')}",
            f"- DOI : {_clean(article.get('doi'), 'Non précisé')}",
            f"- Justification : {_clean(article.get('justification'), 'Non précisée')}",
            f"- Tags suggérés : {', '.join(article.get('tags', [])) or 'Aucun tag'}",
            f"- Note d’argumentaire : {_clean(article.get('argument_note'), 'Non précisée')}",
            "",
        ])

    return "\n".join(lines).strip() + "\n"


def build_zotero_ready_json(export_data: dict) -> str:
    return json.dumps(export_data, ensure_ascii=False, indent=2)
