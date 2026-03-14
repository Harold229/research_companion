from uuid import uuid4


SEARCH_STATE_PREFIXES = (
    "concept_editor_",
    "concept_state_",
    "concept_tiab_",
    "concept_mesh_",
    "concept_remove_",
    "query_expansion_",
    "time_filter_",
    "reading_focus_",
    "prioritized_articles_",
    "selected_central_article_",
    "article_feedback_",
    "article_cache_",
    "related_articles_",
    "cited_refs_",
    "feedback_rating_",
    "feedback_comment_",
    "show_paywall_",
    "paywall_",
    "pack_preview_",
    "download_pack_preview_",
    "download_zotero_",
    "strategy_builder_",
)

SEARCH_STATE_EXACT_KEYS = (
    "current_analysis",
    "search_session_id",
)


def is_search_state_key(key: str) -> bool:
    if key in SEARCH_STATE_EXACT_KEYS:
        return True
    return any(key.startswith(prefix) for prefix in SEARCH_STATE_PREFIXES)


def reset_search_state(
    session_state,
    new_question: str = "",
    clear_question: bool = False,
    update_question: bool = True,
) -> str:
    for key in list(session_state.keys()):
        if key == "question_input" and not clear_question:
            continue
        if is_search_state_key(key):
            del session_state[key]

    if clear_question and update_question:
        session_state.pop("question_input", None)
    elif new_question and update_question:
        session_state["question_input"] = new_question

    search_session_id = uuid4().hex
    session_state["search_session_id"] = search_session_id
    return search_session_id


def load_analysis_entry(session_state, entry: dict) -> dict:
    search_session_id = reset_search_state(
        session_state,
        entry.get("user_question", ""),
    )
    if entry.get("search_session_id"):
        search_session_id = entry["search_session_id"]
        session_state["search_session_id"] = search_session_id

    hydrated_entry = dict(entry)
    hydrated_entry["search_session_id"] = search_session_id
    session_state["current_analysis"] = hydrated_entry
    return hydrated_entry
