from claude_helper import analyze_research_question
from hybrid_reranker import rerank_articles_hybrid
from platform_backends import pubmed_backend
from reading_prioritization import prioritize_articles
from services.librarian_strategy_adapter import get_librarian_strategy_analysis
from services.query_builder import build_fallback_query_attempts
from services.query_builder import build_query_package
from services.query_builder import get_preferred_discovery_query


def _normalize_time_filter(time_filter: dict | None = None) -> dict:
    data = time_filter if isinstance(time_filter, dict) else {}
    return {
        "enabled": bool(data.get("enabled")),
        "valid": bool(data.get("valid", True)),
        "start_year": data.get("start_year", "") or "",
        "end_year": data.get("end_year", "") or "",
        "label": data.get("label", "") or "",
        "error": data.get("error", "") or "",
    }


def discover_articles(
    *,
    question: str,
    result: dict,
    query: str,
    focus_key: str = "other",
    custom_goal: str = "",
    max_results: int = 50,
    time_filter: dict | None = None,
) -> dict:
    normalized_time_filter = _normalize_time_filter(time_filter)
    attempts = build_fallback_query_attempts(result or {})
    if query:
        attempts[0]["query"] = query

    selected_attempt = attempts[0] if attempts else {
        "key": "original",
        "query": query,
        "relaxed_roles": [],
        "relaxed_labels": [],
    }
    filtered_query = ""
    articles = []

    for attempt in attempts or [selected_attempt]:
        candidate_query = pubmed_backend.apply_pubmed_date_filter(
            attempt.get("query", ""),
            start_year=normalized_time_filter.get("start_year", ""),
            end_year=normalized_time_filter.get("end_year", ""),
        )
        if not candidate_query:
            continue
        candidate_articles = pubmed_backend.fetch_articles(candidate_query, max_results=max_results)
        if candidate_articles:
            filtered_query = candidate_query
            articles = candidate_articles
            selected_attempt = attempt
            break
        if not filtered_query:
            filtered_query = candidate_query
            selected_attempt = attempt

    reranked = rerank_articles_hybrid(
        articles or [],
        question,
        custom_goal,
    )
    prioritized = prioritize_articles(reranked.get("articles", []), result or {}, focus_key, custom_goal)
    prioritized["time_filter"] = normalized_time_filter
    prioritized["reranking"] = reranked
    prioritized["discovery_query"] = filtered_query
    prioritized["fallback"] = {
        "used": bool(selected_attempt.get("relaxed_roles")),
        "relaxed_roles": selected_attempt.get("relaxed_roles", []),
        "relaxed_labels": selected_attempt.get("relaxed_labels", []),
        "original_query": pubmed_backend.apply_pubmed_date_filter(
            query or get_preferred_discovery_query(build_query_package(result or {})),
            start_year=normalized_time_filter.get("start_year", ""),
            end_year=normalized_time_filter.get("end_year", ""),
        ),
        "active_query": filtered_query,
    }
    return {
        "query": filtered_query,
        "articles": articles,
        "prioritized": prioritized,
    }


def run_topic_discovery(
    question: str,
    *,
    focus_key: str = "other",
    custom_goal: str = "",
    max_results: int = 50,
    time_filter: dict | None = None,
) -> dict:
    librarian_analysis = get_librarian_strategy_analysis(question)

    if librarian_analysis:
        result = librarian_analysis.get("result") or {}
        query_package = librarian_analysis.get("query_package") or build_query_package(result)
    else:
        result = analyze_research_question(question)
        query_package = build_query_package(result)

    base_query = get_preferred_discovery_query(query_package)
    discovery = discover_articles(
        question=question,
        result=result,
        query=base_query,
        focus_key=focus_key,
        custom_goal=custom_goal,
        max_results=max_results,
        time_filter=time_filter,
    )
    return {
        "result": result,
        "query_package": query_package,
        "discovery": discovery,
        "strategy_source": "librarian_strategy" if librarian_analysis else "legacy",
    }
