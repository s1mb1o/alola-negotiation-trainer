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


def test_builtin_npc_greets_without_taking_the_first_negotiation_turn(
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
    assert conversation[0]["message"] == (
        "Здравствуйте. Давайте обсудим «Поставка 100 промышленных компьютеров». "
        "Слушаю вас."
    )
    assert "120\xa0000 €" not in conversation[0]["message"]
    assert "0%" not in conversation[0]["message"]
    assert "8 недель" not in conversation[0]["message"]
    assert body["observation"]["assistance"]["detected_signals"] == []
    assert body["observation"]["assistance"]["probable_interests"] == []

    token = body["participant_token"]
    history = client.get(
        f"/api/v1/sessions/{body['session_id']}/history",
        headers=bearer(token),
    ).json()
    event = next(
        item for item in history["events"] if item["type"] == "npc.greeting.delivered"
    )
    assert event["session_revision"] == 0
    assert event["payload"]["speech_act"] == "greeting"
    assert event["payload"]["substantive"] is False
    assert not any(
        item["type"] == "npc.opening_utterance.delivered" for item in history["events"]
    )

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


def test_greeting_is_idempotent_and_first_player_turn_starts_the_round(
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
                "AND type = 'npc.greeting.delivered'",
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
def test_greeting_is_available_at_every_difficulty(client: TestClient, difficulty: str) -> None:
    created = client.post(
        "/api/v1/sessions",
        json=_supplier_payload(f"no-opening-{difficulty}", difficulty=difficulty),
    ).json()

    assert created["revision"] == 0
    assert created["observation"]["conversation"][0]["message"].startswith("Здравствуйте.")
    assert created["substantive_turn_count"] == 0
    assert created["next_actor"].endswith("_buyer")


def test_greeting_requires_human_and_builtin_npc(client: TestClient) -> None:
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
    assert created["revision"] == 0
    assert created["next_actor"].endswith("_seller")
    assert created["committed_actions"] == []
    assert created["observation"]["conversation"][0]["role"] == "buyer"
    assert created["observation"]["conversation"][0]["message"].startswith("Здравствуйте.")

    first_turn = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(created["participant_token"]),
        json={
            "message": "Здравствуйте. Какие условия вы хотите обсудить?",
            "idempotency_key": "human-seller-first-turn",
            "expected_revision": 0,
        },
    )
    assert first_turn.status_code == 200
    assert first_turn.json()["committed_actions"][0]["participant_id"].endswith("_seller")


def test_easy_external_agent_retains_canonical_opening(client: TestClient) -> None:
    payload = _supplier_payload("easy-external-opening")
    payload["participants"][0]["controller"] = "external_agent"

    created = client.post("/api/v1/sessions", json=payload).json()

    assert created["revision"] == 0
    assert created["next_actor"].endswith("_buyer")
    message = created["observation"]["conversation"][0]["message"]
    assert "120\xa0000 €" in message
    assert "0%" in message


def test_greeting_bypasses_injected_llm_renderer(settings: Any) -> None:
    renderer = SpyRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        created = client.post(
            "/api/v1/sessions",
            json=_supplier_payload("easy-opening-template-only"),
        ).json()

    assert renderer.calls == 0
    message = created["observation"]["conversation"][0]["message"]
    assert "120\xa0000 €" not in message
    assert "Поставка 100 промышленных компьютеров" in message


def test_greeting_is_localized_in_english(client: TestClient) -> None:
    payload = create_payload(
        "easy-opening-english",
        difficulty="easy",
        language="en",
    )
    payload.update({"scenario_id": "freight_contract_en", "scenario_version": 1})

    created = client.post("/api/v1/sessions", json=payload).json()

    assert created["revision"] == 0
    message = created["observation"]["conversation"][0]["message"]
    assert message == (
        'Hello. I am ready to discuss "Urgent freight contract". Please go ahead.'
    )
    assert "RUB 480,000" not in message
