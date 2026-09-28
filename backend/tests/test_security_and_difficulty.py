from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.service import NegotiationService

from .conftest import bearer, create_payload


HIDDEN_MARKERS = (
    "utility_model",
    "reservation_utility",
    "hard_constraints",
    "seller.quarter_deadline",
    "truth_note",
    "private_payload",
)


@pytest.mark.parametrize(
    ("language", "scenario_id", "expected"),
    [
        (
            "ru",
            "saas_subscription_ru",
            {
                "buyer": {
                    "summary": "Вы представляете компанию ООО Меридиан Ритейл.",
                    "objectives": ["Купить годовую подписку и быстро запустить аналитику."],
                    "context": "Бюджет ограничен. Аванс и срок запуска можно обсуждать.",
                    "batna": "Продлить текущую систему на один квартал.",
                    "constraints": {"maximum_price": 1_250_000},
                    "priorities": ["price", "prepayment_fraction", "delivery_weeks"],
                },
                "seller": {
                    "summary": "Вы представляете компанию АО Спектр Аналитика.",
                    "objectives": ["Продать годовую подписку с приемлемой маржой."],
                    "context": (
                        "Закрытие сделки в этом квартале важно. Больший аванс улучшает условия."
                    ),
                    "batna": "Перенести команду внедрения на другого клиента.",
                    "constraints": {"minimum_price": 1_000_000},
                    "priorities": ["price", "prepayment_fraction", "delivery_weeks"],
                },
            },
        ),
        (
            "en",
            "saas_subscription_en",
            {
                "buyer": {
                    "summary": "You represent Meridian Retail LLC.",
                    "objectives": ["Buy an annual subscription and launch analytics quickly."],
                    "context": (
                        "The budget is limited. Prepayment and launch time are negotiable."
                    ),
                    "batna": "Extend the current system for one quarter.",
                    "constraints": {"maximum_price": 1_250_000},
                    "priorities": ["price", "prepayment_fraction", "delivery_weeks"],
                },
                "seller": {
                    "summary": "You represent Spectrum Analytics JSC.",
                    "objectives": ["Sell an annual subscription with an acceptable margin."],
                    "context": (
                        "Closing this quarter matters. A larger prepayment improves the offer."
                    ),
                    "batna": "Assign the implementation team to another customer.",
                    "constraints": {"minimum_price": 1_000_000},
                    "priorities": ["price", "prepayment_fraction", "delivery_weeks"],
                },
            },
        ),
    ],
)
def test_role_brief_is_structured_localized_and_actor_safe(
    client: TestClient,
    language: str,
    scenario_id: str,
    expected: dict[str, dict[str, object]],
) -> None:
    payload = create_payload(
        f"structured-role-brief-{language}",
        both_external=True,
        language=language,
    )
    payload["scenario_id"] = scenario_id
    created_response = client.post("/api/v1/sessions", json=payload)
    assert created_response.status_code == 201
    created = created_response.json()
    tokens = {item["role"]: item["token"] for item in created["participant_credentials"]}

    for role, token in tokens.items():
        response = client.get(
            f"/api/v1/sessions/{created['session_id']}/observation",
            headers=bearer(token),
        )
        assert response.status_code == 200
        role_brief = response.json()["role_brief"]
        assert role_brief == expected[role]
        assert set(role_brief) == {
            "summary",
            "objectives",
            "context",
            "batna",
            "constraints",
            "priorities",
        }

        serialized = json.dumps(role_brief, ensure_ascii=False)
        assert '"reservation_utility"' not in serialized
        assert '"utility"' not in serialized
        assert '"weight"' not in serialized
        other_role = "seller" if role == "buyer" else "buyer"
        assert expected[other_role]["summary"] not in serialized
        assert expected[other_role]["batna"] not in serialized


def test_legacy_role_brief_text_overrides_summary_without_exposing_utility() -> None:
    scenario = {
        "roles": {
            "buyer": {
                "company": "Legacy Company",
                "brief": {"text": {"ru": "Сохраненный текст роли.", "en": "Legacy role."}},
                "batna": {"utility": 99},
                "constraints": {"reservation_utility": 91, "maximum_price": 10},
                "interests": {
                    "delivery": {"weight": 0.25},
                    "price": {"weight": 0.75},
                },
            }
        }
    }

    role_brief = NegotiationService._role_brief(scenario, "buyer", "ru")

    assert role_brief == {
        "summary": "Сохраненный текст роли.",
        "objectives": [],
        "context": "",
        "batna": "",
        "constraints": {"maximum_price": 10},
        "priorities": ["price", "delivery"],
    }
    serialized = json.dumps(role_brief, ensure_ascii=False)
    assert "reservation_utility" not in serialized
    assert '"utility"' not in serialized
    assert '"weight"' not in serialized


def test_each_difficulty_is_actor_safe(client: TestClient) -> None:
    assistance = {}
    context = {}
    for difficulty in ("guided", "easy", "normal", "expert"):
        created = client.post(
            "/api/v1/sessions",
            json=create_payload(f"create-{difficulty}", difficulty=difficulty),
        ).json()
        observation = client.get(
            f"/api/v1/sessions/{created['session_id']}/observation",
            headers=bearer(created["participant_token"]),
        )
        assert observation.status_code == 200
        serialized = observation.text
        assert all(marker not in serialized for marker in HIDDEN_MARKERS)
        assistance[difficulty] = observation.json()["assistance"]
        context[difficulty] = observation.json()["context"]

    assert assistance["guided"]["coaching"]
    assert "probable_interests" in assistance["easy"]
    assert assistance["normal"] is None
    assert assistance["expert"] is None
    assert context["normal"] == []
    assert len(context["expert"]) == 1
    assert "truth_note" not in context["expert"][0]


def test_token_is_scoped_to_one_session(client: TestClient) -> None:
    first = client.post("/api/v1/sessions", json=create_payload("isolation-a")).json()
    second = client.post("/api/v1/sessions", json=create_payload("isolation-b")).json()
    cross_read = client.get(
        f"/api/v1/sessions/{second['session_id']}/observation",
        headers=bearer(first["participant_token"]),
    )
    assert cross_read.status_code == 401


def test_hint_is_safe_persisted_and_idempotent(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions", json=create_payload("hint-session", difficulty="guided")
    ).json()
    token = created["participant_token"]
    request = {"idempotency_key": "hint-1", "expected_revision": created["revision"]}
    first = client.post(
        f"/api/v1/sessions/{created['session_id']}/hints",
        headers=bearer(token),
        json=request,
    )
    repeated = client.post(
        f"/api/v1/sessions/{created['session_id']}/hints",
        headers=bearer(token),
        json=request,
    )
    assert first.status_code == repeated.status_code == 200
    assert first.json() == repeated.json()
    assert first.json()["revision"] == created["revision"] + 1
    assert all(marker not in first.text for marker in HIDDEN_MARKERS)
    assert first.json()["observation"]["hints"][0]["text"] == first.json()["hint"]["text"]

    observation = client.get(
        f"/api/v1/sessions/{created['session_id']}/observation", headers=bearer(token)
    )
    assert observation.status_code == 200
    assert observation.json()["hints"][0]["event_id"] == first.json()["hint"]["event_id"]

    history = client.get(f"/api/v1/sessions/{created['session_id']}/history", headers=bearer(token))
    assert history.status_code == 200
    assert any(event["type"] == "hint.delivered" for event in history.json()["events"])
    assert "private_payload" not in history.text


def test_benchmark_clarification_limit_terminates_session(client: TestClient) -> None:
    payload = create_payload("clarification-limit", both_external=True)
    payload.update(
        run_mode="benchmark",
        hints_enabled=False,
        benchmark_run_id="clarification-bound",
        trial_id="trial-1",
        benchmark_expected_trials=1,
    )
    created = client.post(
        "/api/v1/sessions", json=payload, headers=bearer("test-admin")
    ).json()
    token = next(
        item["token"]
        for item in created["participant_credentials"]
        if item["participant_id"] == created["next_actor"]
    )
    current = created
    for index in range(3):
        response = client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            headers=bearer(token),
            json={
                "message": "Согласен",
                "idempotency_key": f"clarification-{index}",
                "expected_revision": current["revision"],
            },
        )
        assert response.status_code == 200
        current = response.json()
    assert current["status"] == "expired"
    assert current["terminal_reason"] == "clarification_limit_reached"


def test_training_clarifications_recover_without_expiring(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=create_payload("training-clarification-recovery", both_external=True),
    ).json()
    token = next(
        item["token"]
        for item in created["participant_credentials"]
        if item["participant_id"] == created["next_actor"]
    )
    current = created
    for index in range(3):
        response = client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            headers=bearer(token),
            json={
                "message": "Согласен",
                "idempotency_key": f"training-clarification-{index}",
                "expected_revision": current["revision"],
            },
        )
        assert response.status_code == 200
        current = response.json()
    assert current["status"] == "active"
    assert current["result"] == "clarification_required"
    assert current["clarification"]["recovery"] == {
        "version": "training-clarification-v1",
        "example": (
            "Например: «Предлагаю цену 110 000 EUR, аванс 50% "
            "и поставку за 8 недель»."
        ),
        "end_session_message": "Прекращаю переговоры.",
    }

    restored = client.get(
        f"/api/v1/sessions/{created['session_id']}", headers=bearer(token)
    )
    assert restored.status_code == 200
    assert restored.json()["clarification"]["recovery"] == current["clarification"]["recovery"]

    ended = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(token),
        json={
            "message": current["clarification"]["recovery"]["end_session_message"],
            "idempotency_key": "training-clarification-end",
            "expected_revision": current["revision"],
        },
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "walked_away"


def test_training_clarification_recovery_survives_service_restart(settings) -> None:
    with TestClient(create_app(settings)) as first_client:
        created = first_client.post(
            "/api/v1/sessions",
            json=create_payload("training-recovery-restart", both_external=True),
        ).json()
        token = next(
            item["token"]
            for item in created["participant_credentials"]
            if item["participant_id"] == created["next_actor"]
        )
        current = created
        for index in range(3):
            current = first_client.post(
                f"/api/v1/sessions/{created['session_id']}/messages",
                headers=bearer(token),
                json={
                    "message": "Согласен",
                    "idempotency_key": f"restart-clarification-{index}",
                    "expected_revision": current["revision"],
                },
            ).json()
        expected_recovery = current["clarification"]["recovery"]

    with TestClient(create_app(settings)) as restarted_client:
        restored = restarted_client.get(
            f"/api/v1/sessions/{created['session_id']}",
            headers=bearer(token),
        )
        assert restored.status_code == 200
        assert restored.json()["clarification"]["recovery"] == expected_recovery


def test_hint_budget_is_bounded(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions", json=create_payload("hint-budget", difficulty="guided")
    ).json()
    token = created["participant_token"]
    current_revision = created["revision"]
    for index in range(3):
        response = client.post(
            f"/api/v1/sessions/{created['session_id']}/hints",
            headers=bearer(token),
            json={
                "idempotency_key": f"bounded-hint-{index}",
                "expected_revision": current_revision,
            },
        )
        assert response.status_code == 200
        current_revision = response.json()["revision"]
    exhausted = client.post(
        f"/api/v1/sessions/{created['session_id']}/hints",
        headers=bearer(token),
        json={"idempotency_key": "bounded-hint-4", "expected_revision": current_revision},
    )
    assert exhausted.status_code == 409
    assert exhausted.json()["error"] == "hints_exhausted"
