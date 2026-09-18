from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.scenarios import (
    ScenarioCatalog,
    constraint_violations,
    evaluate_utility,
)

from .conftest import bearer, create_payload, credentials


SCENARIO_ID = "supplier_001"
SCENARIO_VERSION = 2
LATEST_SCENARIO_VERSION = 5


def _supplier_payload(key: str, *, both_external: bool = True, difficulty: str = "normal") -> dict:
    payload = create_payload(
        key,
        both_external=both_external,
        difficulty=difficulty,
        language="ru",
    )
    payload.update({"scenario_id": SCENARIO_ID, "scenario_version": SCENARIO_VERSION})
    return payload


def test_catalog_publishes_latest_supplier_and_keeps_v2_for_replay(
    client: TestClient,
) -> None:
    catalog = client.get("/api/v1/scenarios", params={"language": "ru"})

    assert catalog.status_code == 200
    supplier = [item for item in catalog.json()["items"] if item["id"] == SCENARIO_ID]
    assert len(supplier) == 1
    assert supplier[0]["version"] == LATEST_SCENARIO_VERSION
    assert supplier[0]["title"] == "Поставка 100 промышленных компьютеров"
    assert supplier[0]["currency"] == "EUR"
    assert supplier[0]["negotiable_terms"] == [
        "price",
        "prepayment_fraction",
        "delivery_weeks",
    ]

    latest = client.get(f"/api/v1/scenarios/{SCENARIO_ID}")
    replay_version = client.get(f"/api/v1/scenarios/{SCENARIO_ID}/versions/2")
    draft = client.get(f"/api/v1/scenarios/{SCENARIO_ID}/versions/1")
    assert latest.status_code == 200
    assert latest.json()["version"] == LATEST_SCENARIO_VERSION
    assert latest.json()["opening_kind"] == "opening_position"
    assert replay_version.status_code == 200
    assert replay_version.json()["opening_kind"] == "opening_offer"
    assert draft.status_code == 404


def test_supplier_role_briefs_and_expert_context_are_actor_scoped(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=_supplier_payload("supplier-actor-scope", difficulty="expert"),
    ).json()
    tokens = credentials(created)

    observations = {
        role: client.get(
            f"/api/v1/sessions/{created['session_id']}/observation",
            headers=bearer(token),
        ).json()
        for role, token in tokens.items()
    }

    buyer = observations["buyer"]
    seller = observations["seller"]
    assert buyer["role_brief"]["constraints"] == {"maximum_price": 115_000}
    assert seller["role_brief"]["constraints"] == {"minimum_price": 103_000}
    assert "105 000 евро" in buyer["role_brief"]["context"]
    assert "112 000 евро" in seller["role_brief"]["context"]
    assert "112 000 евро" not in buyer["role_brief"]["context"]
    assert "105 000 евро" not in seller["role_brief"]["context"]
    assert [item["id"] for item in buyer["context"]] == ["buyer_seller_desperate_rumor"]
    assert [item["id"] for item in seller["context"]] == ["seller_buyer_no_alternative_rumor"]
    serialized = json.dumps(observations, ensure_ascii=False)
    for hidden_marker in (
        "reservation_utility",
        "utility_model",
        "hard_constraints",
        "truth_note",
        "seller.cashflow_pressure",
    ):
        assert hidden_marker not in serialized


def test_supplier_parser_commits_one_complete_scalar_package(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions", json=_supplier_payload("supplier-complete-package")
    ).json()
    tokens = credentials(created)

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": (
                "Предлагаю цену 111 000 евро, предоплату 50% "
                "и поставку всего заказа через 3 недели."
            ),
            "idempotency_key": "supplier-scalar-offer",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "turn_committed"
    assert body["observation"]["active_offers"][0]["terms"] == {
        "price": 111_000,
        "prepayment_fraction": 0.5,
        "delivery_weeks": 3,
    }


def test_supplier_wrong_currency_requires_clarification(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions", json=_supplier_payload("supplier-wrong-currency")
    ).json()
    tokens = credentials(created)
    opening = created["observation"]["active_offers"]

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "Предлагаю цену 111 000 долларов, предоплату 50% и срок 3 недели.",
            "idempotency_key": "supplier-usd-offer",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "clarification_required"
    assert body["clarification"]["reason_code"] == "currency_mismatch"
    assert body["clarification"]["expected_currency"] == "EUR"
    assert body["clarification"]["provided_currencies"] == ["USD"]
    assert body["observation"]["active_offers"] == opening


def test_supplier_composite_proposal_is_unscored_and_cannot_change_offer(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/sessions", json=_supplier_payload("supplier-composite-guard")
    ).json()
    tokens = credentials(created)
    opening = created["observation"]["active_offers"]

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": (
                "Предлагаю 111 000 евро и предоплату 50%: первая партия 10 устройств "
                "до 7 ноября, остальные 90 устройств до 20 ноября."
            ),
            "idempotency_key": "supplier-split-delivery",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "clarification_required"
    assert body["clarification"]["reason_code"] == "unscored_proposal"
    assert "вне текущей грамматики" in body["clarification"]["question"]
    assert body["observation"]["active_offers"] == opening


def test_supplier_builtin_npc_uses_domain_wording_and_complete_counteroffer(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=_supplier_payload("supplier-npc-counter", both_external=False),
    ).json()

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(created["participant_token"]),
        json={
            "message": "Предлагаю 100 000 евро, предоплату 50% и поставку через 3 недели.",
            "idempotency_key": "supplier-low-price",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    npc_action = body["committed_actions"][-1]
    assert npc_action["action"] == "counter_offer"
    assert body["observation"]["active_offers"][0]["terms"] == {
        "price": 110_000,
        "prepayment_fraction": 0.5,
        "delivery_weeks": 3,
    }
    assert "110\u00a0000 €" in npc_action["message"]
    assert "50%" in npc_action["message"]
    assert "3 недели" in npc_action["message"]


def test_supplier_representative_package_is_inside_declared_zopa(settings: Settings) -> None:
    scenarios = ScenarioCatalog(
        settings.scenario_directories,
        settings.scenario_schema_path,
    ).discover()
    scenario = next(
        item.source
        for item in scenarios
        if item.id == SCENARIO_ID and item.version == SCENARIO_VERSION
    )
    package = {"price": 111_000, "prepayment_fraction": 0.5, "delivery_weeks": 3}

    assert constraint_violations(scenario, "buyer", package) == []
    assert constraint_violations(scenario, "seller", package) == []
    assert evaluate_utility(scenario, "buyer", package) == 60.5
    assert evaluate_utility(scenario, "seller", package) == 43.3143
    assert evaluate_utility(scenario, "buyer", package) >= 40
    assert evaluate_utility(scenario, "seller", package) >= 40
