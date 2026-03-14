import streamlit as st


ARTICLE_FEEDBACK_LABELS = {
    "": "Votre retour sur cet article",
    "pertinent": "Pertinent",
    "mitige": "Mitigé",
    "hors_sujet": "Hors sujet",
}

LEGACY_ARTICLE_FEEDBACK_VALUES = {
    "relevant": "pertinent",
    "mixed": "mitige",
    "off-topic": "hors_sujet",
}


def get_article_feedback_id(article: dict) -> str:
    return (
        str(article.get("pmid") or "").strip()
        or str(article.get("doi") or "").strip()
        or str(article.get("url") or "").strip()
        or f"{str(article.get('title') or '').strip()}::{str(article.get('year') or '').strip()}"
    )


def render_article_feedback_controls(entry_id: str, article: dict, feedback_store: dict) -> None:
    article_id = get_article_feedback_id(article)
    widget_key = f"article_feedback_choice_{entry_id}_{article_id}"
    stored_feedback = (feedback_store or {}).get(article_id, {})
    stored_label = LEGACY_ARTICLE_FEEDBACK_VALUES.get(stored_feedback.get("label", ""), stored_feedback.get("label", ""))

    if widget_key not in st.session_state:
        st.session_state[widget_key] = stored_label

    choice = st.radio(
        "Votre retour sur cet article",
        options=["", "pertinent", "mitige", "hors_sujet"],
        format_func=lambda value: ARTICLE_FEEDBACK_LABELS[value],
        key=widget_key,
        horizontal=True,
        label_visibility="collapsed",
    )

    if choice:
        feedback_store[article_id] = {
            "label": choice,
            "title": article.get("title", ""),
            "pmid": article.get("pmid", ""),
            "doi": article.get("doi", ""),
            "year": article.get("year", ""),
        }
    else:
        feedback_store.pop(article_id, None)


def render_article_reasons(article: dict) -> None:
    reasons = article.get("reasons", []) or []
    if reasons:
        st.caption(" · ".join(reasons[:2]))


def render_article_details(article: dict) -> None:
    simple_reasons = article.get("reasons", []) or []
    technical_reasons = article.get("technical_reasons", []) or []

    if simple_reasons:
        st.caption(f"Pourquoi il est proposé : {', '.join(simple_reasons[:3])}")
    if technical_reasons:
        st.caption(f"Indices de matching : {', '.join(technical_reasons[:3])}")
