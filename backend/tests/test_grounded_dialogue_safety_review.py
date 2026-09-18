"""Independent offline regressions for numeric presentation and public telemetry."""

from copy import deepcopy
from dataclasses import replace
import json
import re

import pytest
from fastapi.testclient import TestClient

from backend.app.conversation import build_conversation_memory
from backend.app.dialogue import (
    NpcDialogueRequest, NpcDialogueResult, NpcUtterancePlan, TemplateNpcDialogueRenderer,
    stable_render_id, utterance_plan_from_payload, utterance_plan_payload,
    validate_rendered_reply, validated_dialogue_result,
)
from backend.app.dialogue_contracts import PublicNumericReference, reference_texts
from backend.app.main import create_app

from .conftest import bearer, create_payload, credentials


def _request(term: str = "price", value: int | float = 105000, language: str = "en") -> NpcDialogueRequest:
    labels = {term: {"price": "price", "prepayment_fraction": "prepayment"}[term]}
    memory = build_conversation_memory([], [{
        "event_id": "evt_visible", "session_revision": 3, "participant_id": "player",
        "type": "offer.created", "payload": {
            "offer_id": "offer_visible", "offer_revision": 1, "terms": {term: value},
        },
    }], npc_participant_id="npc", term_labels=labels, required_term_ids=[term])
    fallback = "What supports your position?" if language == "en" else "На чём основана ваша позиция?"
    return NpcDialogueRequest(
        language, "EUR", "general_answer", (), (), tuple(labels.items()), (), (fallback,), fallback,
        npc_role="seller", conversation_memory=memory,
        numeric_references=(PublicNumericReference("quote_a", "offer_visible", 1, "buyer", term, value, "EUR"),),
    )


@pytest.mark.parametrize("language", ["ru", "en"])
def test_numeric_reference_preserves_fractional_monetary_amount(language: str) -> None:
    text = reference_texts(_request(value=105000.49, language=language))["[[quote_a]]"]
    assert re.search(r"105(?:[,\s])?000[.,]49", text), text


def test_numeric_reference_preserves_full_authored_percentage_precision() -> None:
    text = reference_texts(_request(term="prepayment_fraction", value=0.123456789))["[[quote_a]]"]
    assert "12.3456789%" in text, text


@pytest.mark.parametrize("field", ["provider", "model"])
@pytest.mark.parametrize("invalid_reply", [False, True])
@pytest.mark.parametrize("secret", ["sk-synthetic-review-credential", "nt_syntheticreviewcredential"])
def test_credential_shaped_metadata_never_reaches_public_events(field: str, invalid_reply: bool, secret: str) -> None:
    request = _request()
    result = NpcDialogueResult("Unauthorized amount 123" if invalid_reply else request.fallback_text,
                               "llm", "test", "offline", False)
    result = replace(result, **{field: secret})
    sanitized = validated_dialogue_result(request, result)
    assert secret not in json.dumps(sanitized.public_metadata())


@pytest.mark.parametrize("field", ["mode", "failure_reason", "validation_failure"])
@pytest.mark.parametrize("malformed", [[], {}, ["secret-value"]])
def test_unstructured_renderer_metadata_is_sanitized_without_raising(field: str, malformed: object) -> None:
    request = _request()
    result = replace(NpcDialogueResult(request.fallback_text, "llm", "test", "offline", False), **{field: malformed})
    sanitized = validated_dialogue_result(request, result)
    assert sanitized.text == request.fallback_text
    assert sanitized.public_metadata()[field] == ("template" if field == "mode" else None)


@pytest.mark.parametrize("latency", [float("nan"), float("inf"), -1, "100", True, {}])
def test_invalid_latency_remains_unavailable(latency: object) -> None:
    request = _request()
    result = replace(NpcDialogueResult(request.fallback_text, "llm", "test", "offline", False), latency_ms=latency)
    assert validated_dialogue_result(request, result).latency_ms is None


def test_public_reference_cannot_bind_a_different_value_via_boolean_numeric_equality() -> None:
    request = _request(value=1)
    memory = deepcopy(request.conversation_memory)
    memory["offers"][0]["terms"]["price"] = True
    with pytest.raises(ValueError):
        replace(request, conversation_memory=memory)


def test_exact_fractional_quote_and_formatter_version_are_frozen_in_durable_plan() -> None:
    request = _request(value=105000.49)
    plan = NpcUtterancePlan(stable_render_id("sess_public", 4), "sess_public", 4, "npc", "inform", request)
    payload = utterance_plan_payload(plan)
    slot_payload = payload["request"]["numeric_references"][0]
    assert slot_payload["display_text"] == reference_texts(request)["[[quote_a]]"]
    assert slot_payload["format_version"] == 1
    assert utterance_plan_from_payload(payload) == plan
    modified_text = deepcopy(payload)
    modified_text["request"]["numeric_references"][0]["display_text"] += " Agreement reached."
    with pytest.raises(ValueError):
        utterance_plan_from_payload(modified_text)
    unknown_formatter = deepcopy(payload)
    unknown_formatter["request"]["numeric_references"][0]["format_version"] = 2
    with pytest.raises(ValueError):
        utterance_plan_from_payload(unknown_formatter)


@pytest.mark.parametrize(("language", "reply"), [
    ("en", "Delivery in December. What supports your position?"),
    ("en", "Delivery is planned for November. What supports your position?"),
    ("en", "Delivery takes eleven weeks. What supports your position?"),
    ("en", "The prepayment is twelve percent. What supports your position?"),
    ("ru", "Поставка в декабре. На чём основана ваша позиция?"),
    ("ru", "Поставка запланирована на ноябрь. На чём основана ваша позиция?"),
    ("ru", "Поставка через одиннадцать недель. На чём основана ваша позиция?"),
    ("ru", "Предоплата двенадцать процентов. На чём основана ваша позиция?"),
])
def test_unapproved_dates_and_spelled_out_quantities_are_not_public_quote_slots(language: str, reply: str) -> None:
    request = _request(language=language)
    with pytest.raises(ValueError):
        validate_rendered_reply(json.dumps({"speech_act": request.speech_act, "reply": reply}), request)


@pytest.mark.parametrize(("language", "reply"), [
    ("en", "We can discuss the delivery timeline in weeks."),
    ("en", "May I ask what supports your position?"),
    ("en", "You may explain your priorities."),
    ("ru", "Срок можно обсудить в неделях."),
])
def test_standalone_units_and_english_modal_may_do_not_invent_a_numeric_value(language: str, reply: str) -> None:
    request = _request(language=language)
    assert validate_rendered_reply(json.dumps({"speech_act": request.speech_act, "reply": reply}), request) == reply


@pytest.mark.parametrize(("difficulty", "human_role"), [("easy", "buyer"), ("normal", "seller")])
def test_initial_dialogue_metadata_redacts_programmatically_configured_secret(settings, difficulty: str, human_role: str) -> None:
    secret = "private-application-token-without-known-prefix"
    configured = replace(settings, admin_token=secret)

    class SecretMetadataRenderer:
        provider = "offline"
        model = secret

        def render(self, request):
            return TemplateNpcDialogueRenderer().render(request)

    with TestClient(create_app(configured, npc_dialogue_renderer=SecretMetadataRenderer())) as client:
        payload = create_payload("initial-secret-" + human_role, difficulty=difficulty, human_role=human_role)
        payload.update(scenario_id="supplier_001", scenario_version=5)
        response = client.post("/api/v1/sessions", json=payload)
        assert response.status_code == 201
        created = response.json()
        history = client.get(
            f"/api/v1/sessions/{created['session_id']}/history",
            headers=bearer(credentials(created)[human_role]),
        )
        assert history.status_code == 200
        assert secret not in response.text
        assert secret not in history.text
