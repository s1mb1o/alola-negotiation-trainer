from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from .conftest import bearer, create_payload, credentials


@pytest.mark.parametrize(
    ("language", "scenario_id", "message", "expected_terms"),
    [
        (
            "ru",
            "freight_contract_ru",
            "Цена 480\u202f000 руб. превышает наш бюджет. Готовы заключить договор при "
            "цене 440\u202f000 руб., предоплате 40% и доставке 6 недель.",
            {"price": 440_000, "prepayment_fraction": 0.4, "delivery_weeks": 6},
        ),
        (
            "ru",
            "freight_contract_ru",
            "440\u202f000 руб. нам не подходит. Готов сделать встречный шаг: "
            "455\u202f000 руб. при предоплате 50% и сроке 6 недель.",
            {"price": 455_000, "prepayment_fraction": 0.5, "delivery_weeks": 6},
        ),
        (
            "en",
            "freight_contract_en",
            "RUB 480,000 exceeds our firm budget. We can proceed at RUB 440,000 "
            "with 6-week delivery and 40% prepayment.",
            {"price": 440_000, "prepayment_fraction": 0.4, "delivery_weeks": 6},
        ),
        (
            "en",
            "freight_contract_en",
            "I can’t meet RUB 440,000. I can offer RUB 460,000 with 50% prepayment "
            "and 6-week delivery.",
            {"price": 460_000, "prepayment_fraction": 0.5, "delivery_weeks": 6},
        ),
        (
            "ru",
            "freight_contract_ru",
            "Понимаю вашу экономику, но 465\u202f000 руб. мы согласовать не сможем: "
            "наш предельный бюджет — 440\u202f000 руб. При этой цене готовы подтвердить "
            "договор сразу, со сроком доставки 6 недель и предоплатой 40%.",
            {"price": 440_000, "prepayment_fraction": 0.4, "delivery_weeks": 6},
        ),
        (
            "en",
            "freight_contract_en",
            "I can't meet RUB 480,000, but I can offer RUB 440,000 with 40% "
            "prepayment and 6-week delivery.",
            {"price": 440_000, "prepayment_fraction": 0.4, "delivery_weeks": 6},
        ),
        (
            "en",
            "freight_contract_en",
            "I understand the RUB 440,000 budget. I can meet that price with 50% "
            "prepayment and a 7-week delivery schedule.",
            {"price": 440_000, "prepayment_fraction": 0.5, "delivery_weeks": 7},
        ),
    ],
)
def test_parser_selects_explicit_proposal_clause(
    client: TestClient,
    language: str,
    scenario_id: str,
    message: str,
    expected_terms: dict[str, float | int],
) -> None:
    payload = create_payload(
        f"proposal-clause-{language}-{expected_terms['price']}",
        both_external=True,
        language=language,
    )
    payload["scenario_id"] = scenario_id
    created = client.post("/api/v1/sessions", json=payload).json()
    tokens = credentials(created)

    counter = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": message,
            "idempotency_key": f"proposal-{language}-{expected_terms['price']}",
            "expected_revision": created["revision"],
        },
    )

    assert counter.status_code == 200
    assert counter.json()["result"] == "turn_committed"
    assert counter.json()["observation"]["active_offers"][0]["terms"] == expected_terms


def test_parser_rejects_multiple_offer_candidates(client: TestClient) -> None:
    payload = create_payload("multiple-offer-candidates", both_external=True, language="en")
    payload["scenario_id"] = "freight_contract_en"
    created = client.post("/api/v1/sessions", json=payload).json()
    tokens = credentials(created)
    initial_offer = created["observation"]["active_offers"][0]

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "I can meet RUB 440,000 with 50% and 7 weeks; if 6 weeks, "
            "I need RUB 460,000 with 40%",
            "idempotency_key": "multiple-offers",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    assert response.json()["result"] == "clarification_required"
    assert response.json()["clarification"]["reason_code"] == "multiple_offer_candidates"
    assert response.json()["observation"]["active_offers"] == [initial_offer]
    assert response.json()["substantive_turn_count"] == 0


def test_parser_rejects_referential_multiple_offer_candidates(client: TestClient) -> None:
    payload = create_payload("referential-multiple-offers", both_external=True, language="en")
    payload["scenario_id"] = "freight_contract_en"
    created = client.post("/api/v1/sessions", json=payload).json()
    tokens = credentials(created)

    buyer_offer = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "I offer RUB 440,000 with 40% prepayment and 6-week delivery.",
            "idempotency_key": "referential-buyer-offer",
            "expected_revision": created["revision"],
        },
    ).json()
    active_offer = buyer_offer["observation"]["active_offers"][0]

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "I understand the RUB 440,000 budget. I can meet that price with "
            "50% prepayment and a 7-week delivery schedule; the additional week helps "
            "us plan the capacity at that rate. If delivery must remain within 6 weeks, "
            "I would need RUB 460,000 with 40% prepayment.",
            "idempotency_key": "referential-multiple-offers",
            "expected_revision": buyer_offer["revision"],
        },
    )

    assert response.status_code == 200
    assert response.json()["result"] == "clarification_required"
    assert response.json()["clarification"]["reason_code"] == "multiple_offer_candidates"
    assert response.json()["observation"]["active_offers"] == [active_offer]
    assert response.json()["substantive_turn_count"] == 1
    assert response.json()["next_actor"] == buyer_offer["next_actor"]
