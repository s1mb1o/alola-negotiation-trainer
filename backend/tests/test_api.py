from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import SCENARIO_ID, bearer, create_payload, credentials


def test_health_and_scenario_catalog(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["journal_mode"] == "wal"

    response = client.get("/api/v1/scenarios", params={"language": "ru"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(body["items"])
    scenario = next(item for item in body["items"] if item["id"] == SCENARIO_ID)
    assert scenario["opening_offer_role"] == "seller"
    assert [role["role"] for role in scenario["roles"]] == ["buyer", "seller"]
    assert "utility_model" not in scenario
    assert all(item["language"] == "ru" for item in body["items"])


def test_create_session_is_idempotent_and_actor_authenticated(client: TestClient) -> None:
    payload = create_payload("create-idempotent")
    first = client.post("/api/v1/sessions", json=payload)
    second = client.post("/api/v1/sessions", json=payload)
    assert first.status_code == second.status_code == 201
    body = first.json()
    repeated = second.json()
    assert repeated["session_id"] == body["session_id"]
    assert repeated["revision"] == body["revision"]
    assert repeated["credential_delivery"] == "initial_response_only"
    assert "participant_token" not in repeated
    assert "participant_credentials" not in repeated
    token = body["participant_token"]

    assert client.get(f"/api/v1/sessions/{body['session_id']}").status_code == 401
    session = client.get(f"/api/v1/sessions/{body['session_id']}", headers=bearer(token))
    assert session.status_code == 200
    assert session.json()["next_actor"] == body["next_actor"]

    database = client.app.state.database
    with database.read_connection() as connection:
        stored = connection.execute(
            "SELECT response_json FROM idempotency_results "
            "WHERE scope = 'create_session' AND idempotency_key = 'create-idempotent'"
        ).fetchone()[0]
    assert body["participant_token"] not in stored
    assert "participant_credentials" not in stored


def test_session_language_must_match_scenario_version(client: TestClient) -> None:
    payload = create_payload("language-mismatch", language="en")
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 422
    assert response.json()["error"] == "scenario_language_mismatch"


def test_offer_acceptance_confirmation_for_external_participants(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions", json=create_payload("create-two-external", both_external=True)
    ).json()
    tokens = credentials(created)
    session_id = created["session_id"]

    counter = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "Предлагаю цену 1 200 000 рублей.",
            "idempotency_key": "buyer-offer",
            "expected_revision": 0,
        },
    )
    assert counter.status_code == 200
    assert counter.json()["result"] == "turn_committed"
    assert counter.json()["revision"] == 1

    ambiguous = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Согласен",
            "idempotency_key": "ambiguous",
            "expected_revision": 1,
        },
    )
    assert ambiguous.json()["result"] == "clarification_required"
    assert ambiguous.json()["revision"] == 2

    intent = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Принимаю все условия предложения.",
            "idempotency_key": "accept-intent",
            "expected_revision": 2,
        },
    )
    assert intent.json()["result"] == "confirmation_required"
    assert intent.json()["pending_confirmation"]["terms"]["price"] == 1_200_000

    confirmed = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Подтверждаю принятие.",
            "idempotency_key": "accept-confirm",
            "expected_revision": intent.json()["revision"],
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "agreement_reached"
    review = client.get(f"/api/v1/sessions/{session_id}/review", headers=bearer(tokens["seller"]))
    assert review.status_code == 200
    assert review.json()["outcome"]["agreement"] is True
    assert "reservation_utility" not in review.text


def test_conditional_confirmation_does_not_bind_previous_offer(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions", json=create_payload("conditional-confirm", both_external=True)
    ).json()
    tokens = credentials(created)
    session_id = created["session_id"]
    buyer_offer = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "Предлагаю цену 1 200 000 рублей, предоплату 50% и доставку 4 недели.",
            "idempotency_key": "conditional-offer",
            "expected_revision": 0,
        },
    ).json()
    intent = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Принимаю все условия предложения.",
            "idempotency_key": "conditional-intent",
            "expected_revision": buyer_offer["revision"],
        },
    ).json()
    conditional = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "Подтверждаю принятие, если цена 1 250 000 рублей.",
            "idempotency_key": "conditional-final",
            "expected_revision": intent["revision"],
        },
    )
    assert conditional.status_code == 200
    assert conditional.json()["status"] == "active"
    assert conditional.json()["result"] == "turn_committed"
    assert conditional.json()["observation"]["active_offers"][0]["terms"]["price"] == 1_250_000


def test_counteroffer_accepts_unicode_digit_grouping(client: TestClient) -> None:
    payload = create_payload("unicode-digit-grouping", both_external=True)
    payload["scenario_id"] = "freight_contract_ru"
    created = client.post("/api/v1/sessions", json=payload).json()
    tokens = credentials(created)

    counter = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "Предлагаю цену 440\u202f000 ₽, предоплату 50% и доставку 4 недели.",
            "idempotency_key": "unicode-price",
            "expected_revision": created["revision"],
        },
    )

    assert counter.status_code == 200
    assert counter.json()["result"] == "turn_committed"
    assert counter.json()["observation"]["active_offers"][0]["terms"] == {
        "price": 440_000,
        "prepayment_fraction": 0.5,
        "delivery_weeks": 4,
    }


def test_walk_away_review_and_aggregate_stats(client: TestClient) -> None:
    payload = create_payload("create-walk-away")
    payload["participants"][0].update(
        {"provider": "openai", "model": "test-model", "prompt_version": "v1"}
    )
    payload.update({"benchmark_run_id": "training-run", "trial_id": "trial-1", "seed": 7})
    created = client.post("/api/v1/sessions", json=payload).json()
    token = created["participant_token"]
    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(token),
        json={
            "message": "Прекращаю переговоры.",
            "idempotency_key": "walk-away",
            "expected_revision": created["revision"],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "walked_away"

    stats = client.get("/api/v1/stats").json()
    assert stats["totals"]["completed_sessions"] == 1
    assert stats["totals"]["agreements"] == 0
    assert stats["totals"]["avg_outcome_score"] is None
    assert "avg_utility" not in stats["totals"]
    assert any(row["model"] == "openai/test-model" for row in stats["by_model"])
    assert stats["benchmark_runs"][0]["benchmark_run_id"] == "training-run"


def test_builtin_npc_accepts_legal_offer_deterministically(client: TestClient) -> None:
    created = client.post("/api/v1/sessions", json=create_payload("create-built-in")).json()
    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(created["participant_token"]),
        json={
            "message": "Предлагаю цену 1 200 000 рублей.",
            "idempotency_key": "legal-offer",
            "expected_revision": created["revision"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "agreement_reached"
    assert [action["action"] for action in body["committed_actions"]] == [
        "counter_offer",
        "accept",
    ]


def test_human_can_play_opening_offer_role(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=create_payload("seller-role", human_role="seller"),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["revision"] == 0
    assert body["next_actor"].endswith("_seller")
    assert body["observation"]["role"] == "seller"
    assert body["committed_actions"] == []
    assert body["observation"]["conversation"][0]["role"] == "buyer"


def test_administrative_close_requires_admin_token(client: TestClient) -> None:
    created = client.post("/api/v1/sessions", json=create_payload("admin-close")).json()
    path = f"/api/v1/sessions/{created['session_id']}/close"
    body = {
        "idempotency_key": "close-1",
        "expected_revision": created["revision"],
        "reason": "test cleanup",
    }
    unauthorized = client.post(path, json=body, headers=bearer(created["participant_token"]))
    assert unauthorized.status_code == 401
    closed = client.post(path, json=body, headers=bearer("test-admin"))
    assert closed.status_code == 200
    assert closed.json()["status"] == "aborted"
