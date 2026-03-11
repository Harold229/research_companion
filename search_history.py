"""
Lightweight local history for recent searches and exported packs.
"""

import json
from datetime import datetime
from pathlib import Path


HISTORY_PATH = Path(__file__).parent / "recent_searches.json"
MAX_HISTORY_ITEMS = 8


def load_recent_searches() -> list:
    if not HISTORY_PATH.exists():
        return []

    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    return data if isinstance(data, list) else []


def save_recent_search(entry: dict) -> None:
    history = load_recent_searches()

    entry_id = entry.get("id")
    if entry_id:
        history = [item for item in history if item.get("id") != entry_id]

    history.insert(0, entry)
    trimmed = history[:MAX_HISTORY_ITEMS]
    HISTORY_PATH.write_text(
        json.dumps(trimmed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_history_entry(
    user_question: str,
    result: dict,
    strategy: dict,
    platform_outputs: dict,
    pack: str,
) -> dict:
    now = datetime.now()
    reformulated = (
        result.get("research_question_fr")
        or result.get("research_question_en")
        or result.get("research_question_comment")
    )

    return {
        "id": now.strftime("%Y%m%d%H%M%S%f"),
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "user_question": user_question,
        "reformulated_question": reformulated,
        "framework": result.get("framework"),
        "result": result,
        "strategy": strategy,
        "platform_outputs": platform_outputs,
        "pack": pack,
    }
