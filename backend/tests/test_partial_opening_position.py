from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from backend.app.scenarios import ScenarioError, compile_scenario

from .conftest import PROJECT_ROOT, bearer, create_payload, credentials


SUPPLIER_V2_PATH = PROJECT_ROOT / "examples" / "scenario_supplier_001_v2.yaml"


def _supplier_document() -> dict:
    return yaml.safe_load(SUPPLIER_V2_PATH.read_text(encoding="utf-8"))


def _supplier_v3_payload(key: str, *, difficulty: str = "easy") -> dict:
    payload = create_payload(key, difficulty=difficulty)
    payload.update({"scenario_id": "supplier_001", "scenario_version": 3})
    return payload


def test_compiler_preserves_explicit_partial_opening_position() -> None:
    document = _supplier_document()
    scenario = document["scenario"]
    scenario["version"] = 3
    seller = scenario["roles"]["seller"]
    seller.pop("opening_offer")
    seller["opening_position"] = {"price": 120_000}

    compiled = compile_scenario(document, Path("supplier-position.yaml"))

    assert compiled.source["roles"]["seller"]["opening_position"] == {"price": 120_000}
    assert "prepayment_fraction" not in compiled.source["roles"]["seller"]["opening_position"]
    assert "delivery_weeks" not in compiled.source["roles"]["seller"]["opening_position"]
    assert compiled.public_metadata()["opening_offer_role"] == "seller"
    assert compiled.public_metadata()["opening_kind"] == "opening_position"


def test_compiler_keeps_opening_offer_complete_and_rejects_two_openings() -> None:
    incomplete_offer = _supplier_document()
    incomplete_offer["scenario"]["roles"]["seller"]["opening_offer"] = {"price": 120_000}
    with pytest.raises(ScenarioError, match="Opening offer is missing required terms"):
        compile_scenario(incomplete_offer, Path("incomplete-offer.yaml"))

    two_openings = deepcopy(_supplier_document())
    two_openings["scenario"]["roles"]["seller"]["opening_position"] = {"price": 120_000}
    with pytest.raises(ScenarioError, match="must not define both"):
        compile_scenario(two_openings, Path("two-openings.yaml"))

    empty_position = _supplier_document()
    seller = empty_position["scenario"]["roles"]["seller"]
    seller.pop("opening_offer")
    seller["opening_position"] = {}
    with pytest.raises(ScenarioError, match="at least one authored term"):
        compile_scenario(empty_position, Path("empty-position.yaml"))


def test_easy_opening_position_contains_only_authored_terms(client: TestClient) -> None:
    response = client.post(
        "/api/v1/sessions",
        json=_supplier_v3_payload("partial-opening-position"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["revision"] == 0
    assert body["round"] == 1
    assert body["substantive_turn_count"] == 0
    assert body["observation"]["active_offers"] == [
        {
            "offer_id": body["observation"]["active_offers"][0]["offer_id"],
            "offer_revision": 1,
            "proposer_role": "seller",
            "terms": {"price": 120_000},
            "unresolved_required_terms": ["prepayment_fraction", "delivery_weeks"],
        }
    ]
    message = body["observation"]["conversation"][0]["message"]
    assert message == (
        "Добрый день. Предлагаю обсудить условия поставки промышленных компьютеров. "
        "Моя начальная позиция: цена 120\u00a0000 €. "
        "Остальные условия предлагаю обсудить."
    )
    assert "0%" not in message
    assert "8 недель" not in message
    assert "предоплат" not in message.casefold()

    history = client.get(
        f"/api/v1/sessions/{body['session_id']}/history",
        headers=bearer(body["participant_token"]),
    ).json()
    offer_event = next(event for event in history["events"] if event["type"] == "offer.created")
    assert offer_event["payload"]["terms"] == {"price": 120_000}
    assert offer_event["payload"]["unresolved_required_terms"] == [
        "prepayment_fraction",
        "delivery_weeks",
    ]
    opener_event = next(
        event for event in history["events"] if event["type"] == "npc.opening_utterance.delivered"
    )
    assert opener_event["payload"]["speech_act"] == "opening_position"
    assert opener_event["payload"]["opening_kind"] == "opening_position"


def test_partial_opening_position_cannot_bind(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=_supplier_v3_payload("partial-opening-not-bindable", difficulty="normal"),
    ).json()

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(created["participant_token"]),
        json={
            "message": "Принимаю все условия предложения.",
            "idempotency_key": "accept-partial-opening",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "offer_not_bindable"
    assert body["status"] == "active"
    assert body["observation"]["active_offers"][0]["terms"] == {"price": 120_000}
    assert body["observation"]["active_offers"][0]["unresolved_required_terms"] == [
        "prepayment_fraction",
        "delivery_weeks",
    ]


def test_builtin_npc_discusses_incomplete_counteroffer_without_filling_missing_terms(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=_supplier_v3_payload("npc-requests-completion", difficulty="normal"),
    ).json()

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(created["participant_token"]),
        json={
            "message": "Предлагаю цену 110 000 евро.",
            "idempotency_key": "partial-counteroffer",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [action["action"] for action in body["committed_actions"]] == [
        "counter_offer",
        "inform",
    ]
    npc_action = body["committed_actions"][-1]
    assert npc_action["speech_act"] == "acknowledge_partial_offer"
    assert "полный" not in npc_action["message"].casefold()
    assert body["observation"]["active_offers"][0]["terms"] == {"price": 110_000}
    assert body["observation"]["active_offers"][0]["unresolved_required_terms"] == [
        "prepayment_fraction",
        "delivery_weeks",
    ]


def test_player_can_complete_opening_position_without_repeating_authored_price(
    client: TestClient,
) -> None:
    payload = _supplier_v3_payload("complete-opening-position", difficulty="normal")
    payload["participants"] = [
        {"role": "buyer", "controller": "external_agent"},
        {"role": "seller", "controller": "external_agent"},
    ]
    created = client.post(
        "/api/v1/sessions",
        json=payload,
    ).json()
    tokens = credentials(created)

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "Предлагаю предоплату 50% и поставку через 3 недели.",
            "idempotency_key": "complete-missing-opening-terms",
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["observation"]["active_offers"][0]["terms"] == {
        "price": 120_000,
        "prepayment_fraction": 0.5,
        "delivery_weeks": 3,
    }
    assert body["observation"]["active_offers"][0]["unresolved_required_terms"] == []
