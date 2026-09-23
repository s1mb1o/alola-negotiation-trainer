"""Offline checks for bounded prepared-reply retrieval and prompt provenance."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.dialogue import (
    NpcDialogueRequest,
    NpcDialogueResult,
    NpcUtterancePlan,
    RetrievedReplyExample,
    build_safe_render_input,
    stable_render_id,
    utterance_plan_from_payload,
    utterance_plan_payload,
)
from backend.app.main import create_app
from backend.app import reply_retrieval
from backend.app.reply_retrieval import LIBRARY_VERSION, retrieve_reply_examples

from .conftest import bearer, create_payload


PRICE_REASON = ("transport_cost", "Тариф должен покрывать топливо и работу перевозчика.")


def _freight_price_examples(**overrides):
    query = {
        "scenario_id": "freight_contract_ru",
        "npc_role": "seller",
        "language": "ru",
        "speech_act": "general_answer",
        "player_message": "Почему такая цена за перевозку?",
        "focused_term_ids": ("price",),
        "approved_reasons": (PRICE_REASON,),
    }
    query.update(overrides)
    return retrieve_reply_examples(**query)


def test_price_question_retrieves_multiple_versioned_variants():
    exact = _freight_price_examples()
    paraphrase = _freight_price_examples(player_message="Почему стоимость перевозки такая высокая?")

    assert len(exact) == 3
    assert len(paraphrase) == 3
    assert exact == _freight_price_examples()
    assert all(item.library_version == LIBRARY_VERSION for item in exact)
    assert len({item.reply for item in exact}) == 3
    assert all(PRICE_REASON[1] in item.reply for item in exact)


@pytest.mark.parametrize(
    "override",
    [
        {"scenario_id": "saas_subscription_ru"},
        {"npc_role": "buyer"},
        {"language": "en"},
        {"speech_act": "focused_discussion"},
        {"focused_term_ids": ("delivery_weeks",)},
        {"approved_reasons": ()},
        {"approved_reasons": (("transport_cost", "Different reason."),)},
        {"player_message": "Поговорим о погоде."},
    ],
)
def test_retrieval_does_not_cross_action_or_approval_boundary(override):
    assert _freight_price_examples(**override) == ()


def test_prepared_reply_rejects_numeric_or_binding_assertions():
    with pytest.raises(ValueError):
        RetrievedReplyExample(LIBRARY_VERSION, "unsafe_1", "Цена?", "Цена 100 EUR.")
    with pytest.raises(ValueError):
        RetrievedReplyExample(LIBRARY_VERSION, "unsafe_2", "Цена?", "Договорились.")


def test_broken_optional_library_leaves_retrieval_empty(tmp_path, monkeypatch):
    broken = tmp_path / "reply_examples_v1.json"
    broken.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(reply_retrieval, "LIBRARY_PATH", broken)
    reply_retrieval._library.cache_clear()
    try:
        assert _freight_price_examples() == ()
    finally:
        reply_retrieval._library.cache_clear()


class CapturingRenderer:
    provider = "offline-fixture"
    model = "offline-fixture"

    def __init__(self):
        self.requests = []

    def render(self, request):
        self.requests.append(request)
        return NpcDialogueResult(
            text=request.fallback_text,
            mode="template",
            provider=self.provider,
            model=self.model,
            fallback_used=False,
        )


def test_service_attaches_retrieved_examples_after_approving_reason(settings):
    renderer = CapturingRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        payload = create_payload("retrieved-price", difficulty="easy")
        payload.update(scenario_id="freight_contract_ru", scenario_version=3)
        created = client.post("/api/v1/sessions", json=payload)
        assert created.status_code == 201, created.text
        session = created.json()
        response = client.post(
            f"/api/v1/sessions/{session['session_id']}/messages",
            headers=bearer(session["participant_token"]),
            json={
                "message": "Почему такая цена за перевозку?",
                "expected_revision": session["revision"],
                "idempotency_key": "price-question",
            },
        )
        assert response.status_code == 200, response.text
        assert "freight_ru_price_reason" not in response.text

    request = renderer.requests[-1]
    assert request.speech_act == "general_answer"
    assert request.approved_reasons == (PRICE_REASON,)
    assert len(request.retrieved_reply_examples) == 3
    assert all(PRICE_REASON[1] in item.reply for item in request.retrieved_reply_examples)

    plan = NpcUtterancePlan(
        stable_render_id("retrieval-test", 2), "retrieval-test", 2, "npc-test", "inform", request
    )
    restored = utterance_plan_from_payload(json.loads(json.dumps(utterance_plan_payload(plan))))
    assert restored.request.retrieved_reply_examples == request.retrieved_reply_examples

    prompt = build_safe_render_input(request)
    assert '"retrieved_reply_examples"' in prompt
    assert PRICE_REASON[1] in prompt
    assert "reservation_utility" not in prompt


def test_old_render_plan_without_examples_still_restores(settings):
    request = NpcDialogueRequest(
        language="ru",
        currency="EUR",
        speech_act="greeting",
        approved_terms=(),
        public_interest_labels=(),
        participant_facing_terms=(),
        dialogue_context=(),
        approved_reply_options=("Здравствуйте.",),
        fallback_text="Здравствуйте.",
    )
    plan = NpcUtterancePlan(
        stable_render_id("old-plan", 1), "old-plan", 1, "npc-test", "inform", request
    )
    payload = utterance_plan_payload(plan)
    del payload["request"]["retrieved_reply_examples"]
    assert utterance_plan_from_payload(payload).request.retrieved_reply_examples == ()
