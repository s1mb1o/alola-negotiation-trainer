from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from .conftest import bearer, create_payload, credentials


@pytest.mark.parametrize(
    ("language", "scenario_id"),
    [
        ("ru", "office_lease_ru"),
        ("en", "office_lease_en"),
    ],
)
def test_catalog_lists_latest_office_lease_and_keeps_v1_retrievable(
    client: TestClient,
    language: str,
    scenario_id: str,
) -> None:
    catalog = client.get("/api/v1/scenarios", params={"language": language})

    assert catalog.status_code == 200
    matches = [item for item in catalog.json()["items"] if item["id"] == scenario_id]
    assert len(matches) == 1
    assert matches[0]["version"] == 4
    assert matches[0]["negotiable_terms"] == [
        "annual_rent",
        "prepayment_fraction",
        "office_readiness_weeks",
    ]

    latest = client.get(f"/api/v1/scenarios/{scenario_id}")
    version_one = client.get(f"/api/v1/scenarios/{scenario_id}/versions/1")

    assert latest.status_code == version_one.status_code == 200
    assert latest.json()["version"] == 4
    assert version_one.json()["version"] == 1
    assert version_one.json()["negotiable_terms"] == [
        "price",
        "prepayment_fraction",
        "delivery_weeks",
    ]


def test_russian_landlord_brief_uses_natural_lease_language(client: TestClient) -> None:
    payload = create_payload(
        "office-v2-landlord-brief-ru",
        both_external=True,
        language="ru",
    )
    payload.update({"scenario_id": "office_lease_ru", "scenario_version": 2})
    created = client.post("/api/v1/sessions", json=payload).json()
    tokens = credentials(created)
    seller = next(
        participant for participant in created["participants"] if participant["role"] == "seller"
    )

    observation = client.get(
        f"/api/v1/sessions/{created['session_id']}/observation",
        headers=bearer(tokens["seller"]),
    )

    assert observation.status_code == 200
    brief = observation.json()["role_brief"]
    assert brief["objectives"] == ["Сдать свободный офис в аренду на год по приемлемой ставке."]
    assert brief["context"] == (
        "Пока офис пустует, компания теряет арендный доход. "
        "Предоплата снижает риск задержки платежей. "
        "Срочная подготовка офиса увеличивает расходы."
    )
    assert brief["constraints"] == {"minimum_annual_rent": 2_100_000}
    assert brief["priorities"] == [
        "annual_rent",
        "prepayment_fraction",
        "office_readiness_weeks",
    ]
    assert seller["participant_id"] == observation.json()["participant_id"]
    serialized = str(brief).casefold()
    assert "простой помещения дорог" not in serialized
    assert "delivery" not in serialized


@pytest.mark.parametrize(
    ("language", "scenario_id", "message", "expected_terms"),
    [
        (
            "ru",
            "office_lease_ru",
            "Предлагаю годовую арендную плату 2 400 000 рублей, "
            "предоплату 30% и готовность офиса к въезду через 4 недели.",
            {
                "annual_rent": 2_400_000,
                "prepayment_fraction": 0.3,
                "office_readiness_weeks": 4,
            },
        ),
        (
            "en",
            "office_lease_en",
            "I offer annual rent of RUB 2,400,000, 30% prepayment, and the office "
            "ready for move-in in 4 weeks.",
            {
                "annual_rent": 2_400_000,
                "prepayment_fraction": 0.3,
                "office_readiness_weeks": 4,
            },
        ),
    ],
)
def test_office_lease_v2_parser_extracts_complete_package(
    client: TestClient,
    language: str,
    scenario_id: str,
    message: str,
    expected_terms: dict[str, float | int],
) -> None:
    payload = create_payload(
        f"office-v2-parser-{language}",
        both_external=True,
        language=language,
    )
    payload.update({"scenario_id": scenario_id, "scenario_version": 2})
    created = client.post("/api/v1/sessions", json=payload).json()
    tokens = credentials(created)

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": message,
            "idempotency_key": f"office-v2-offer-{language}",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    assert response.json()["result"] == "turn_committed"
    assert response.json()["observation"]["active_offers"][0]["terms"] == expected_terms


@pytest.mark.parametrize(
    ("language", "scenario_id", "message", "provided_currency"),
    [
        (
            "ru",
            "office_lease_ru",
            "Предлагаю годовую арендную плату 2 400 000 евро.",
            "EUR",
        ),
        (
            "en",
            "office_lease_en",
            "I offer annual rent of USD 2,400,000.",
            "USD",
        ),
    ],
)
def test_office_lease_v2_rejects_wrong_annual_rent_currency(
    client: TestClient,
    language: str,
    scenario_id: str,
    message: str,
    provided_currency: str,
) -> None:
    payload = create_payload(
        f"office-v2-currency-{language}",
        both_external=True,
        language=language,
    )
    payload.update({"scenario_id": scenario_id, "scenario_version": 2})
    created = client.post("/api/v1/sessions", json=payload).json()
    tokens = credentials(created)
    initial_offer = created["observation"]["active_offers"]

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": message,
            "idempotency_key": f"office-v2-wrong-currency-{language}",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "clarification_required"
    assert body["clarification"]["reason_code"] == "currency_mismatch"
    assert body["clarification"]["expected_currency"] == "RUB"
    assert body["clarification"]["provided_currencies"] == [provided_currency]
    assert body["observation"]["active_offers"] == initial_offer


@pytest.mark.parametrize(
    ("language", "scenario_id", "question", "expected_fragment", "forbidden_fragment"),
    [
        (
            "ru",
            "office_lease_ru",
            "Какие условия для вас важны?",
            "срок готовности офиса к въезду",
            "поставк",
        ),
        (
            "en",
            "office_lease_en",
            "What terms matter to you?",
            "office is ready for move-in",
            "delivery",
        ),
    ],
)
def test_office_lease_npc_uses_lease_specific_prompt(
    client: TestClient,
    language: str,
    scenario_id: str,
    question: str,
    expected_fragment: str,
    forbidden_fragment: str,
) -> None:
    payload = create_payload(f"office-v2-prompt-{language}", language=language)
    payload.update({"scenario_id": scenario_id, "scenario_version": 2})
    created = client.post("/api/v1/sessions", json=payload).json()

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(created["participant_token"]),
        json={
            "message": question,
            "idempotency_key": f"office-v2-question-{language}",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    npc_action = response.json()["committed_actions"][-1]
    assert npc_action["action"] == "inform"
    assert expected_fragment in npc_action["message"]
    assert forbidden_fragment not in npc_action["message"].casefold()


@pytest.mark.parametrize(
    ("language", "scenario_id", "message", "expected_fragment", "forbidden_fragment"),
    [
        (
            "ru",
            "office_lease_ru",
            "Предлагаю годовую арендную плату 2 000 000 рублей, "
            "предоплату 20% и готовность офиса к въезду через 4 недели.",
            "годовая арендная плата 2\u00a0425\u00a0000 ₽",
            "поставк",
        ),
        (
            "en",
            "office_lease_en",
            "I offer annual rent of RUB 2,000,000, 20% prepayment, and the office "
            "ready for move-in in 4 weeks.",
            "annual rent of RUB 2,425,000",
            "delivery",
        ),
    ],
)
def test_office_lease_npc_counters_annual_rent_in_natural_language(
    client: TestClient,
    language: str,
    scenario_id: str,
    message: str,
    expected_fragment: str,
    forbidden_fragment: str,
) -> None:
    payload = create_payload(f"office-v2-counter-{language}", language=language)
    payload.update({"scenario_id": scenario_id, "scenario_version": 2})
    created = client.post("/api/v1/sessions", json=payload).json()

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(created["participant_token"]),
        json={
            "message": message,
            "idempotency_key": f"office-v2-low-offer-{language}",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    npc_action = body["committed_actions"][-1]
    assert npc_action["action"] == "counter_offer"
    assert body["observation"]["active_offers"][0]["terms"] == {
        "annual_rent": 2_425_000,
        "prepayment_fraction": 0.2,
        "office_readiness_weeks": 4,
    }
    assert expected_fragment in npc_action["message"]
    assert forbidden_fragment not in npc_action["message"].casefold()
