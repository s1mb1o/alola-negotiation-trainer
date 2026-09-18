from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.dialogue import NpcDialogueRequest, NpcDialogueResult
from backend.app.main import create_app

from .conftest import bearer, create_payload


class SpyRenderer:
    provider = "spy-provider"
    model = "spy-model"

    def __init__(self) -> None:
        self.calls = 0

    def render(self, request: NpcDialogueRequest) -> NpcDialogueResult:
        self.calls += 1
        return NpcDialogueResult(
            text=request.fallback_text,
            mode="llm",
            provider=self.provider,
            model=self.model,
            fallback_used=False,
        )


def _supplier_payload(key: str, *, difficulty: str = "easy") -> dict[str, Any]:
    payload = create_payload(key, difficulty=difficulty)
    payload.update({"scenario_id": "supplier_001", "scenario_version": 2})
    return payload


def test_easy_builtin_opening_role_presents_offer_without_consuming_turn(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/sessions",
        json=_supplier_payload("easy-opening-offer"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["revision"] == 0
    assert body["round"] == 1
    assert body["substantive_turn_count"] == 0
    assert body["next_actor"].endswith("_buyer")
    assert body["committed_actions"] == []
    assert body["observation"]["active_offers"] == [
        {
            "offer_id": body["observation"]["active_offers"][0]["offer_id"],
            "offer_revision": 1,
            "proposer_role": "seller",
            "terms": {
                "price": 120_000,
                "prepayment_fraction": 0,
                "delivery_weeks": 8,
            },
            "unresolved_required_terms": [],
        }
    ]
    conversation = body["observation"]["conversation"]
    assert len(conversation) == 1
    assert conversation[0]["revision"] == 0
    assert conversation[0]["role"] == "seller"
    assert "условия поставки промышленных компьютеров" in conversation[0]["message"]
    assert "120\xa0000 €" in conversation[0]["message"]
    assert "0%" in conversation[0]["message"]
    assert "8 недель" in conversation[0]["message"]
    assert body["observation"]["assistance"]["detected_signals"] == []
    assert body["observation"]["assistance"]["probable_interests"] == []

    token = body["participant_token"]
    history = client.get(
        f"/api/v1/sessions/{body['session_id']}/history",
        headers=bearer(token),
    ).json()
    event = next(
        item for item in history["events"] if item["type"] == "npc.opening_utterance.delivered"
    )
    assert event["session_revision"] == 0
    assert event["payload"]["speech_act"] == "opening_offer"
    assert event["payload"]["substantive"] is False
    assert event["payload"]["dialogue_renderer"]["mode"] == "template"

    with client.app.state.database.read_connection() as connection:
        state = json.loads(
            connection.execute(
                "SELECT state_json FROM sessions WHERE id = ?", (body["session_id"],)
            ).fetchone()[0]
        )
        assert state["round_actor_ids"] == []
        assert state["completed_rounds"] == 0
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM offers WHERE session_id = ?", (body["session_id"],)
            ).fetchone()[0]
            == 1
        )


def test_easy_opening_is_idempotent_and_first_player_turn_starts_the_round(
    client: TestClient,
) -> None:
    payload = _supplier_payload("easy-opening-idempotent")
    first = client.post("/api/v1/sessions", json=payload).json()
    repeated = client.post("/api/v1/sessions", json=payload).json()

    assert repeated["session_id"] == first["session_id"]
    assert repeated["observation"]["conversation"] == first["observation"]["conversation"]
    assert repeated["credential_delivery"] == "initial_response_only"
    with client.app.state.database.read_connection() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?", (first["session_id"],)
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM events WHERE session_id = ? "
                "AND type = 'npc.opening_utterance.delivered'",
                (first["session_id"],),
            ).fetchone()[0]
            == 1
        )

    turn = client.post(
        f"/api/v1/sessions/{first['session_id']}/messages",
        headers=bearer(first["participant_token"]),
        json={
            "message": "Здравствуйте. Какие условия для вас важны?",
            "idempotency_key": "easy-first-player-turn",
            "expected_revision": 0,
        },
    )
    assert turn.status_code == 200
    body = turn.json()
    assert body["revision"] == 2
    assert body["substantive_turn_count"] == 2
    assert body["round"] == 2


@pytest.mark.parametrize("difficulty", ["guided", "normal", "expert"])
def test_automatic_opening_is_easy_only(client: TestClient, difficulty: str) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=_supplier_payload(f"no-opening-{difficulty}", difficulty=difficulty),
    ).json()

    assert created["revision"] == 0
    assert created["observation"]["conversation"] == []


def test_easy_does_not_speak_for_external_or_human_opening_role(client: TestClient) -> None:
    both_external = _supplier_payload("easy-both-external")
    both_external["participants"] = [
        {"role": "buyer", "controller": "external_agent"},
        {"role": "seller", "controller": "external_agent"},
    ]
    external = client.post("/api/v1/sessions", json=both_external).json()
    assert external["observation"]["conversation"] == []

    human_seller = _supplier_payload("easy-human-seller")
    human_seller["participants"] = [
        {"role": "buyer", "controller": "built_in_npc"},
        {"role": "seller", "controller": "human"},
    ]
    created = client.post("/api/v1/sessions", json=human_seller).json()
    assert not any(message["revision"] == 0 for message in created["observation"]["conversation"])
    assert created["revision"] == 1
    assert len(created["committed_actions"]) == 1


def test_easy_opening_bypasses_injected_llm_renderer(settings: Any) -> None:
    renderer = SpyRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        created = client.post(
            "/api/v1/sessions",
            json=_supplier_payload("easy-opening-template-only"),
        ).json()

    assert renderer.calls == 0
    message = created["observation"]["conversation"][0]["message"]
    assert "120\xa0000 €" in message


def test_easy_opening_offer_is_localized_in_english(client: TestClient) -> None:
    payload = create_payload(
        "easy-opening-english",
        difficulty="easy",
        language="en",
    )
    payload.update({"scenario_id": "freight_contract_en", "scenario_version": 1})

    created = client.post("/api/v1/sessions", json=payload).json()

    assert created["revision"] == 0
    message = created["observation"]["conversation"][0]["message"]
    assert "freight terms" in message
    assert "My opening offer" in message
    assert "RUB 480,000" in message
    assert "prepayment of 40%" in message
    assert "delivery timeline of 6 weeks" in message
