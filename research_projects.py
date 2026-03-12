"""
Lightweight project storage for grouping searches, packs and future assets.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


PROJECTS_PATH = Path(__file__).parent / "projects.json"
LEGACY_HISTORY_PATH = Path(__file__).parent / "recent_searches.json"
MAX_RECENT_ENTRIES = 8


def _now() -> datetime:
    return datetime.now()


def _build_project(title: str, now: Optional[datetime] = None) -> dict:
    current = now or _now()
    project_id = current.strftime("P%Y%m%d%H%M%S%f")
    timestamp = current.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "id": project_id,
        "title": title.strip() or "Projet sans titre",
        "created_at": timestamp,
        "updated_at": timestamp,
        "questions": [],
        "entries": [],
        "saved_articles": [],
        "arguments": [],
        "notes": [],
        "zotero": {
            "library": {},
            "target_collection": {},
            "item_mapping": {},
        },
    }


def _safe_load_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _save_projects(projects: list) -> None:
    PROJECTS_PATH.write_text(
        json.dumps(projects, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _infer_project_title(entry: dict) -> str:
    return (
        entry.get("reformulated_question")
        or entry.get("user_question")
        or "Projet de recherche"
    )


def migrate_legacy_history() -> list:
    if PROJECTS_PATH.exists():
        return _safe_load_json(PROJECTS_PATH, [])

    legacy_entries = _safe_load_json(LEGACY_HISTORY_PATH, [])
    if not isinstance(legacy_entries, list) or not legacy_entries:
        return []

    projects = []
    for entry in reversed(legacy_entries):
        project = _build_project(_infer_project_title(entry), _now())
        project["questions"] = [entry.get("user_question")] if entry.get("user_question") else []
        project["entries"] = [{**entry, "project_id": project["id"], "project_title": project["title"]}]
        if project["entries"]:
            project["updated_at"] = project["entries"][0].get("created_at", project["updated_at"])
        projects.append(project)

    _save_projects(projects)
    return projects


def load_projects() -> list:
    data = _safe_load_json(PROJECTS_PATH, None)
    if isinstance(data, list):
        return data
    return migrate_legacy_history()


def create_project(title: str) -> dict:
    projects = load_projects()
    normalized_title = title.strip()
    existing = next((project for project in projects if project.get("title", "").strip().lower() == normalized_title.lower()), None)
    if existing:
        return existing

    project = _build_project(normalized_title)
    projects.insert(0, project)
    _save_projects(projects)
    return project


def save_entry_to_project(entry: dict, *, project_id: Optional[str] = None, project_title: Optional[str] = None) -> dict:
    projects = load_projects()
    normalized_title = (project_title or "").strip()

    project = None
    if project_id:
        project = next((item for item in projects if item.get("id") == project_id), None)
    if project is None and normalized_title:
        project = next((item for item in projects if item.get("title", "").strip().lower() == normalized_title.lower()), None)
    if project is None:
        project = _build_project(normalized_title or _infer_project_title(entry))
        projects.insert(0, project)

    updated_entry = {
        **entry,
        "project_id": project["id"],
        "project_title": project["title"],
    }

    entries = [item for item in project.get("entries", []) if item.get("id") != updated_entry.get("id")]
    entries.insert(0, updated_entry)
    project["entries"] = entries

    question = updated_entry.get("user_question")
    questions = [item for item in project.get("questions", []) if item]
    if question and question not in questions:
        questions.insert(0, question)
    project["questions"] = questions[:20]
    project["updated_at"] = updated_entry.get("created_at", project.get("updated_at"))

    projects = [item for item in projects if item.get("id") != project["id"]]
    projects.insert(0, project)
    _save_projects(projects)
    return updated_entry


def get_recent_entries(projects: list, max_items: int = MAX_RECENT_ENTRIES) -> list:
    entries = []
    for project in projects:
        for entry in project.get("entries", []):
            entries.append({
                **entry,
                "project_id": project.get("id"),
                "project_title": project.get("title"),
            })

    entries.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return entries[:max_items]


def get_project_by_id(projects: list, project_id: str):
    return next((project for project in projects if project.get("id") == project_id), None)


def save_project_articles(project_id: str, articles_export: dict) -> None:
    projects = load_projects()
    project = get_project_by_id(projects, project_id)
    if not project:
        return

    saved_articles = []
    for article in articles_export.get("articles", []):
        article_key = article.get("pmid") or article.get("doi") or article.get("title")
        if not article_key:
            continue
        saved_articles = [
            item for item in saved_articles if (item.get("pmid") or item.get("doi") or item.get("title")) != article_key
        ]
        saved_articles.append(article)

    existing = project.get("saved_articles", [])
    deduped = {}
    for item in existing + saved_articles:
        key = item.get("pmid") or item.get("doi") or item.get("title")
        if key:
            deduped[key] = item

    project["saved_articles"] = list(deduped.values())
    project["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_projects(projects)


def save_project_zotero_target(project_id: str, zotero_mapping: dict) -> None:
    projects = load_projects()
    project = get_project_by_id(projects, project_id)
    if not project:
        return

    project["zotero"] = {
        "library": zotero_mapping.get("library", {}),
        "target_collection": zotero_mapping.get("target_collection", {}),
        "item_mapping": {
            "prepared_articles": len(zotero_mapping.get("articles", [])),
            "last_sync_preview": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    project["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_projects(projects)
