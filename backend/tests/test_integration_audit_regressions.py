from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from .conftest import bearer, create_payload, credentials


def test_participant_ids_include_full_session_entropy(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=create_payload("participant-id-entropy", both_external=True),
    ).json()

    session_entropy = created["session_id"].removeprefix("sess_")
    assert len(session_entropy) == 24
    for participant in created["participants"]:
        assert participant["participant_id"].startswith(f"participant_{session_entropy}_")


@pytest.mark.parametrize(
    ("language", "scenario_id", "wrong_message", "wrong_currency", "valid_message"),
    [
        (
            "ru",
            "saas_subscription_ru",
            "Предлагаю цену 1 200 000 евро.",
            "EUR",
            "Предлагаю цену 1 200 000 рублей.",
        ),
        (
            "en",
            "saas_subscription_en",
            "I offer a price of USD 1,200,000.",
            "USD",
            "I offer a price of RUB 1,200,000.",
        ),
    ],
)
def test_explicit_currency_mismatch_requires_actor_safe_clarification(
    client: TestClient,
    language: str,
    scenario_id: str,
    wrong_message: str,
    wrong_currency: str,
    valid_message: str,
) -> None:
    payload = create_payload(f"currency-mismatch-{language}", both_external=True, language=language)
    payload["scenario_id"] = scenario_id
    created = client.post("/api/v1/sessions", json=payload).json()
    tokens = credentials(created)
    initial_offer = created["observation"]["active_offers"][0]

    mismatch = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": wrong_message,
            "idempotency_key": f"wrong-currency-{language}",
            "expected_revision": created["revision"],
        },
    )
    assert mismatch.status_code == 200
    mismatch_body = mismatch.json()
    assert mismatch_body["result"] == "clarification_required"
    assert mismatch_body["next_actor"] == created["next_actor"]
    assert mismatch_body["clarification"]["reason_code"] == "currency_mismatch"
    assert mismatch_body["clarification"]["expected_currency"] == "RUB"
    assert mismatch_body["clarification"]["provided_currencies"] == [wrong_currency]
    assert "RUB" in mismatch_body["clarification"]["question"]
    assert mismatch_body["observation"]["active_offers"] == [initial_offer]
    assert "private_payload" not in mismatch.text

    valid = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": valid_message,
            "idempotency_key": f"valid-currency-{language}",
            "expected_revision": mismatch_body["revision"],
        },
    )
    assert valid.status_code == 200
    assert valid.json()["result"] == "turn_committed"
    assert valid.json()["observation"]["active_offers"][0]["terms"]["price"] == 1_200_000


def test_acceptance_cancel_cycle_expires_at_protocol_control_limit(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=create_payload("accept-cancel-limit", both_external=True),
    ).json()
    tokens = credentials(created)
    session_id = created["session_id"]

    offer = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "Предлагаю цену 1 200 000 рублей.",
            "idempotency_key": "cycle-offer",
            "expected_revision": created["revision"],
        },
    ).json()
    intent = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Принимаю все условия предложения.",
            "idempotency_key": "cycle-intent-1",
            "expected_revision": offer["revision"],
        },
    ).json()
    cancelled = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Отменяю принятие.",
            "idempotency_key": "cycle-cancel",
            "expected_revision": intent["revision"],
        },
    ).json()
    expired = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Принимаю все условия предложения.",
            "idempotency_key": "cycle-intent-2",
            "expected_revision": cancelled["revision"],
        },
    )

    assert expired.status_code == 200
    expired_body = expired.json()
    assert expired_body["result"] == "expired"
    assert expired_body["status"] == "expired"
    assert expired_body["next_actor"] is None
    assert expired_body["terminal_reason"] == "protocol_control_limit_reached"
    assert expired_body["substantive_turn_count"] == 1

    history = client.get(
        f"/api/v1/sessions/{session_id}/history",
        headers=bearer(tokens["seller"]),
    ).json()
    terminal_event = next(
        event for event in reversed(history["events"]) if event["type"] == "session.expired"
    )
    assert terminal_event["payload"]["reason"] == "protocol_control_limit_reached"


def test_package_design_scores_only_explicit_term_delta(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=create_payload("package-delta-score", both_external=True),
    ).json()
    tokens = credentials(created)
    session_id = created["session_id"]

    offer = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "Предлагаю цену 1 200 000 рублей.",
            "idempotency_key": "delta-price-only",
            "expected_revision": created["revision"],
        },
    ).json()
    assert len(offer["observation"]["active_offers"][0]["terms"]) == 3

    intent = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Принимаю все условия предложения.",
            "idempotency_key": "delta-accept",
            "expected_revision": offer["revision"],
        },
    ).json()
    confirmed = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Подтверждаю принятие.",
            "idempotency_key": "delta-confirm",
            "expected_revision": intent["revision"],
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "agreement_reached"

    review = client.get(
        f"/api/v1/sessions/{session_id}/review",
        headers=bearer(tokens["buyer"]),
    )
    assert review.status_code == 200
    assert review.json()["skills"]["package_design"] == pytest.approx(33.3333)
