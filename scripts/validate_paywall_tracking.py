"""
Local validation for paywall tracking without a real Google Sheets webhook.
"""

import os
import sys
import types
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

streamlit_stub = types.ModuleType("streamlit")
streamlit_stub.session_state = {}
streamlit_stub.secrets = {}
sys.modules["streamlit"] = streamlit_stub

from paywall_tracking import build_paywall_payload
from paywall_tracking import PAYWALL_EVENT_COLUMNS
from paywall_tracking import send_paywall_event


class _DummyResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def _build_entry():
    return {
        "user_question": "Quelle est la prevalence du diabete au Mali ?",
        "reformulated_question": "Quelle est la prévalence du diabète au Mali ?",
        "result": {
            "framework": "PICO",
            "components": {
                "intervention": "diabete",
                "outcome": "prevalence",
            },
        },
        "platform_outputs": {
            "PubMed": {
                "large": {"count": 120},
                "strict": {"count": 34},
                "is_identical": False,
            }
        },
    }


def _assert_payload_shape(payload):
    missing = [column for column in PAYWALL_EVENT_COLUMNS if column not in payload]
    if missing:
        raise AssertionError(f"Missing columns in payload: {missing}")


def main():
    streamlit_stub.session_state.clear()
    os.environ["PAYWALL_WEBHOOK_URL"] = "https://example.test/webhook"
    entry = _build_entry()
    captured = []

    def fake_post(url, json=None, timeout=0):
        captured.append({"url": url, "payload": json, "timeout": timeout})
        return _DummyResponse(200)

    critical_events = [
        ("paywall_view", {}),
        ("paywall_price_selected", {"price_selected": "10 €"}),
        ("paywall_email_submitted", {"price_selected": "10 €", "email": "test@example.com"}),
        ("paywall_dismissed", {"price_selected": "Je ne paierais pas"}),
        (
            "paywall_refusal_reason_submitted",
            {
                "price_selected": "Je ne paierais pas",
                "refusal_reason": "Le prix me semble trop élevé",
            },
        ),
    ]

    with patch("paywall_tracking.requests.post", side_effect=fake_post):
        for event_name, kwargs in critical_events:
            payload = build_paywall_payload(entry, event_name, **kwargs)
            ok = send_paywall_event(payload)
            if not ok:
                raise AssertionError(f"Event was not accepted by webhook: {event_name}")

    if len(captured) != len(critical_events):
        raise AssertionError(f"Expected {len(critical_events)} payloads, got {len(captured)}")

    for item in captured:
        _assert_payload_shape(item["payload"])

    with patch("paywall_tracking.requests.post", side_effect=RuntimeError("boom")):
        failing_ok = send_paywall_event(build_paywall_payload(entry, "paywall_view"))
        if failing_ok:
            raise AssertionError("Webhook failure should remain non-blocking and return False.")

    print("Validation locale du tracking paywall: OK")
    print("Evenements recus :")
    for item in captured:
        payload = item["payload"]
        print(
            f"- {payload['event_name']} | {payload['price_selected']} | "
            f"{payload['email']} | {payload['refusal_reason']}"
        )


if __name__ == "__main__":
    main()
