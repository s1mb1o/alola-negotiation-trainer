from dataclasses import replace
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.conversation import build_conversation_memory
from backend.app.dialogue import (
    LlmNpcDialogueRenderer, NpcDialogueRequest, NpcDialogueResult, NpcUtterancePlan,
    build_safe_render_input, stable_render_id, utterance_plan_from_payload, utterance_plan_payload,
    validate_rendered_reply, validated_dialogue_result,
)
from backend.app.dialogue_contracts import PublicNumericReference, reference_texts
from backend.app.main import create_app
from backend.app.engine import _format_money, _format_percentage
from clients.providers import AgentModelConfig, Generation
from .conftest import bearer, create_payload
from .test_continuity_integration import CapturingTemplateRenderer, _create, _submit, _history


def reference_request(language="ru", speaker="player"):
    labels = {"price": "цена" if language == "ru" else "price"}
    memory = build_conversation_memory([], [{
        "event_id": "evt_public", "session_revision": 3, "participant_id": speaker,
        "type": "offer.created", "payload": {"offer_id": "offer_public", "offer_revision": 1,
                                              "terms": {"price": 105000}},
    }], npc_participant_id="npc", term_labels=labels, required_term_ids=["price"])
    fallback = "На чём основана ваша позиция?" if language == "ru" else "What supports your position?"
    slot = PublicNumericReference("quote_a", "offer_public", 1, "seller" if speaker == "npc" else "buyer", "price", 105000, "EUR")
    return NpcDialogueRequest(language, "EUR", "general_answer", (), (), tuple(labels.items()), (),
                              (fallback,), fallback, npc_role="seller", conversation_memory=memory,
                              numeric_references=(slot,))


def output(request, reply):
    return json.dumps({"speech_act": request.speech_act, "reply": reply}, ensure_ascii=False)


@pytest.mark.parametrize("language", ["ru", "en"])
@pytest.mark.parametrize("speaker", ["npc", "player"])
def test_public_quote_is_exact_attributed_and_survives_delivery_validation(language, speaker):
    request = reference_request(language, speaker)
    result = validate_rendered_reply(output(request, "[[quote_a]] " + request.fallback_text), request)
    quoted = reference_texts(request)["[[quote_a]]"]
    assert result == quoted + " " + request.fallback_text
    expected = ("В нашем" if speaker == "npc" else "В вашем") if language == "ru" else ("Our" if speaker == "npc" else "Your")
    assert result.startswith(expected)
    delivered = validated_dialogue_result(request, NpcDialogueResult(result, "llm", "test", "offline", False))
    assert not delivered.fallback_used
    assert delivered.text == result


@pytest.mark.parametrize("reply", ["[[quote_b]]", "[[quote_a]] [[quote_a]]", "[[quote_a]] Цена 99999 евро.",
                                   "Цена 105000 EUR.", "Договорились. [[quote_a]]", "[[quote_a", "quote_a]]"])
def test_unknown_modified_repeated_or_binding_numeric_references_fail_closed(reply):
    request = reference_request()
    with pytest.raises(ValueError):
        validate_rendered_reply(output(request, reply), request)


@pytest.mark.parametrize("mutation", [dict(value=99000), dict(offer_revision=2), dict(offer_id="offer_other"),
                                       dict(proposer_role="seller"), dict(currency="USD"), dict(term_id="salary")])
def test_reference_must_match_public_active_revision(mutation):
    request = reference_request()
    with pytest.raises(ValueError):
        replace(request, numeric_references=(replace(request.numeric_references[0], **mutation),))


def test_reference_cannot_revive_superseded_offer_and_plan_roundtrip_is_exact():
    request = reference_request()
    plan = NpcUtterancePlan(stable_render_id("sess_public", 4), "sess_public", 4, "npc", "inform", request)
    assert utterance_plan_from_payload(utterance_plan_payload(plan)) == plan
    memory = json.loads(json.dumps(request.conversation_memory))
    memory["offers"][0]["status"] = "superseded"
    with pytest.raises(ValueError):
        replace(request, conversation_memory=memory)
    payload = utterance_plan_payload(plan)
    for field in ("numeric_references", "difficulty", "conversation_style", "requested_term_id"):
        payload["request"].pop(field)
    assert utterance_plan_from_payload(payload).request.numeric_references == ()


class OfflineQuoteProvider:
    config = AgentModelConfig(provider="openai", model="offline-test")

    def __init__(self, verdict=True, reply="[[quote_a]] На чём основана ваша позиция?"):
        self.verdict, self.reply, self.calls = verdict, reply, []

    def generate(self, messages, *, instructions=None):
        self.calls.append(messages)
        text = json.dumps({"safe": self.verdict}) if len(self.calls) == 2 else json.dumps({"speech_act": "general_answer", "reply": self.reply})
        return Generation(text=text, provider="openai", model="offline-test", latency_ms=1)


@pytest.mark.parametrize("verdict", [True, False])
def test_quote_requires_grounding_and_records_only_safe_telemetry(verdict):
    request = reference_request()
    provider = OfflineQuoteProvider(verdict)
    result = LlmNpcDialogueRenderer(provider).render(request)
    assert len(provider.calls) == 2
    assert result.fallback_used is not verdict
    assert result.validation_failure == (None if verdict else "grounding")
    assert result.attempted_generation and result.latency_ms >= 0
    assert validated_dialogue_result(request, result).public_metadata() == result.public_metadata()


def test_invalid_raw_number_has_categorized_failure_without_second_call():
    provider = OfflineQuoteProvider(reply="Цена 104000 евро.")
    result = LlmNpcDialogueRenderer(provider).render(reference_request())
    assert result.validation_failure == "unauthorized_claim"
    assert result.fallback_used and len(provider.calls) == 1


@pytest.mark.parametrize("difficulty", ["guided", "easy", "normal", "expert"])
def test_difficulty_profile_does_not_change_public_numbers(difficulty):
    request = reference_request()
    profiled = replace(request, difficulty=difficulty, conversation_style="analytical")
    payload = json.loads(build_safe_render_input(profiled).split("\n", 2)[1])
    assert payload["dialogue_profile"]
    assert payload["numeric_references"][0]["value"] == 105000
    assert "reservation_utility" not in payload and "utility" not in payload


def test_service_contextual_short_reply_and_relative_change_survive_restart(settings):
    renderer = CapturingTemplateRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, "grounded-short", version=5)
        _submit(client, session, "Сначала обсудим цену.")
        assert renderer.requests[-1].requested_term_id == "price"
        delivered = [event for event in _history(client, session) if event["type"] == "npc.utterance.delivered"]
        assert delivered[-1]["payload"]["requested_term_id"] == "price"
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        body = _submit(client, session, "110000")
        assert body["observation"]["active_offers"][0]["terms"] == {"price": 110000}
        body = _submit(client, session, "Предлагаю снизить цену на 5%.")
        assert body["observation"]["active_offers"][0]["terms"] == {"price": 104500}
        assert body["status"] == "active"
        assert renderer.requests[-1].numeric_references[0].value == 104500


@pytest.mark.parametrize("language,question", [("ru", "Почему цена 1200000 рублей?"), ("en", "Why is the price RUB 1200000?")])
def test_numeric_question_leaves_complete_offer_and_status_unchanged(settings, language, question):
    with TestClient(create_app(settings)) as client:
        payload = create_payload("numeric-question-" + language, language=language)
        payload.update(scenario_id="saas_subscription_" + language, scenario_version=3)
        response = client.post("/api/v1/sessions", json=payload)
        assert response.status_code == 201
        session = response.json()
        before = session["observation"]["active_offers"]
        body = _submit(client, session, question)
        assert body["observation"]["active_offers"] == before
        assert body["committed_actions"][-1]["action"] == "inform"
        assert body["status"] == "active"
        assert not any(event["type"] == "agreement.reached" for event in _history(client, session))


def test_admin_quality_is_additive_and_does_not_invent_human_ratings(client):
    session = _create(client, "quality-card", version=5)
    _submit(client, session, "Здравствуйте")
    response = client.get(f"/api/v1/admin/sessions/{session['session_id']}", headers=bearer("test-admin"))
    assert response.status_code == 200
    quality = response.json()["dialogue_quality"]
    assert quality["heuristic_only"] is True
    assert quality["human_review"]["status"] == "unrated"
    assert quality["rendering"]["latency_ms"]["average"] is None


@pytest.mark.parametrize("language,expected", [("ru", "105\u00a0000,49 €"), ("en", "EUR 105,000.49")])
def test_canonical_financial_text_also_preserves_exact_public_values(language, expected):
    assert _format_money(105000.49, "EUR", language) == expected
    assert _format_percentage(0.123456789) == "12.3456789%"
