"""
Paywall event tracking through an Apps Script webhook.
"""

import os
from datetime import datetime
from uuid import uuid4

import requests
import streamlit as st

from question_display import get_question_presentation


DEFAULT_PRICES = ["5 €", "10 €", "Je ne paierais pas"]
PAYWALL_EVENT_COLUMNS = [
    "timestamp",
    "session_id",
    "event_name",
    "question_initiale",
    "question_reformulee",
    "type_question",
    "framework",
    "wide_count",
    "narrow_count",
    "is_identical",
    "price_shown",
    "price_selected",
    "email",
    "comment",
    "refusal_reason",
    "source",
]


def get_session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid4())
    return st.session_state["session_id"]


def get_paywall_webhook_url() -> str:
    try:
        return st.secrets["PAYWALL_WEBHOOK_URL"].strip()
    except Exception:
        return os.getenv("PAYWALL_WEBHOOK_URL", "").strip()


def build_paywall_payload(
    entry: dict,
    event_name: str,
    *,
    price_selected: str = "",
    email: str = "",
    comment: str = "",
    refusal_reason: str = "",
    source: str = "streamlit_app",
) -> dict:
    result = entry.get("result") or {}
    bramer = (entry.get("platform_outputs") or {}).get("PubMed", {})
    presentation = get_question_presentation(result, entry.get("user_question", ""))

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": get_session_id(),
        "event_name": event_name,
        "question_initiale": entry.get("user_question", ""),
        "question_reformulee": entry.get("reformulated_question", ""),
        "type_question": presentation.get("question_type", ""),
        "framework": result.get("framework"),
        "wide_count": (bramer.get("large") or {}).get("count"),
        "narrow_count": (bramer.get("strict") or {}).get("count"),
        "is_identical": bramer.get("is_identical"),
        "price_shown": DEFAULT_PRICES,
        "price_selected": price_selected,
        "email": email,
        "comment": comment,
        "refusal_reason": refusal_reason,
        "source": source,
    }


def send_paywall_event(payload: dict) -> bool:
    webhook_url = get_paywall_webhook_url()
    if not webhook_url:
        return False

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code < 400
    except Exception:
        return False
