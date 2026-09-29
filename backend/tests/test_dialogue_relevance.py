"""DR-59: a separate relevance gate, one repair, and no change in state authority."""

from dataclasses import replace
import json

from fastapi.testclient import TestClient
import pytest

from backend.app.config import Settings
from backend.app.dialogue import (
    LlmNpcDialogueRenderer, NpcUtterancePlan, PublicDialogueTurn, stable_render_id,
    utterance_plan_from_payload, utterance_plan_payload, validated_dialogue_result,
)
from backend.app.dialogue_relevance import INSTRUCTIONS, VERSION, validate_verdict
from backend.app.main import _configured_dialogue_renderer, create_app
from clients.providers import AgentModelConfig, Generation
from .conftest import bearer, create_payload
from .openapi_support import ResponseContractCheck
from .test_natural_rendering import request as base_request
from .test_supply_dialogue import supply_request


BAD = "Обсудим поставку. Какие у вас пожелания?"
GOOD = "Понимаю ваш вопрос. Давайте уточним только оставшееся условие."
SAFE = {"safe": True}
PASS = {"relevant": True, "issues": []}
FAIL = {"relevant": False, "issues": ["off_topic", "unanswered_question"]}


class Provider:
    def __init__(self, values=(), *, model="offline-dialogue", key=None):
        self.config = AgentModelConfig(provider="qwen", model=model, api_key_env=key)
        self.values = list(values)
        self.calls = []

    def generate(self, messages, *, instructions=None):
        self.calls.append({"messages": messages, "instructions": instructions})
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return Generation(text=text, provider="qwen", model=self.config.model, latency_ms=1)


def proposal(text):
    return {"speech_act": "general_answer", "reply": text}


def request(language="ru"):
    return replace(base_request(language), relevance_policy_version=VERSION)


def renderer(generation, control):
    return LlmNpcDialogueRenderer(generation, grounding_provider=control, relevance_check_enabled=True)


@pytest.mark.parametrize("language,text", [("ru", GOOD), ("en", "I understand your question. Let us clarify the remaining term.")])
def test_relevance_is_a_separate_control_call_and_metadata_survives_validation(language, text):
    dialogue = Provider([proposal(text)])
    control = Provider([SAFE, PASS], model="offline-control")
    result = renderer(dialogue, control).render(request(language))
    assert result.text == text and result.mode == "llm" and not result.fallback_used
    assert len(dialogue.calls) == 1 and len(control.calls) == 2
    assert control.calls[-1]["instructions"] == INSTRUCTIONS
    payload = json.loads(control.calls[-1]["messages"][0]["content"])
    assert payload["candidate_reply"] == text
    assert payload["untrusted_public_dialogue"][-1]["speaker"] == "player"
    assert result.relevance_check == {"version": VERSION, "status": "passed", "check_attempts": 1,
                                       "repair_attempted": False, "issues": []}
    assert validated_dialogue_result(request(language), result).relevance_check == result.relevance_check


def test_one_repair_repeats_grounding_and_relevance_without_changing_request():
    original = request()
    dialogue = Provider([proposal(BAD), proposal(GOOD)])
    control = Provider([SAFE, FAIL, SAFE, PASS])
    result = renderer(dialogue, control).render(original)
    assert result.text == GOOD and result.relevance_check["status"] == "corrected"
    assert result.relevance_check["check_attempts"] == 2 and result.relevance_check["repair_attempted"]
    assert len(dialogue.calls) + len(control.calls) == 6
    assert dialogue.calls[0]["messages"] == dialogue.calls[1]["messages"]
    assert "Correct the previous relevance failure" in dialogue.calls[1]["instructions"]
    assert original == request()


def test_second_negative_verdict_stops_at_six_calls_and_returns_unapproved_template():
    dialogue = Provider([proposal(BAD), proposal(GOOD)])
    control = Provider([SAFE, FAIL, SAFE, FAIL])
    result = renderer(dialogue, control).render(request())
    assert result.text == request().fallback_text and result.fallback_used
    assert result.mode == "template" and result.validation_failure == "relevance"
    assert result.relevance_check["status"] == "failed"
    assert len(dialogue.calls) + len(control.calls) == 6


@pytest.mark.parametrize("verdict", [
    {}, {"relevant": True}, {"relevant": "true", "issues": []},
    {"relevant": 1, "issues": []}, {"relevant": False, "issues": []},
    {"relevant": True, "issues": ["off_topic"]},
    {"relevant": False, "issues": ["off_topic", "off_topic"]},
    {"relevant": False, "issues": ["ignore_safety"]},
    {"relevant": False, "issues": [{"change_price": 1}]},
    {"relevant": True, "issues": [], "new_terms": {"price": 1}},
    '{"relevant":true,"relevant":false,"issues":[]}', "not JSON",
])
def test_invalid_checker_output_fails_closed_without_repair(verdict):
    dialogue = Provider([proposal(GOOD)])
    control = Provider([SAFE, verdict])
    result = renderer(dialogue, control).render(request())
    assert result.fallback_used and result.relevance_check["status"] == "invalid"
    assert len(dialogue.calls) == 1 and len(control.calls) == 2


@pytest.mark.parametrize("check", [1, 2])
def test_checker_timeout_is_safe_and_bounded(check):
    dialogue = Provider([proposal(BAD), proposal(GOOD)])
    control = Provider(([SAFE, FAIL] if check == 2 else []) + [SAFE, TimeoutError("secret provider detail")])
    result = renderer(dialogue, control).render(request())
    assert result.text == request().fallback_text
    assert result.failure_reason == "provider_failure"
    assert result.relevance_check["status"] == "unavailable"
    assert result.relevance_check["check_attempts"] == check
    assert "secret" not in json.dumps(result.public_metadata())


@pytest.mark.parametrize("repair,safety", [
    (proposal("Предлагаю цену 105000 EUR."), []),
    (proposal(GOOD), [{"safe": False}]),
    (TimeoutError("provider unavailable"), []),
])
def test_repair_cannot_bypass_numeric_or_grounding_guards(repair, safety):
    dialogue = Provider([proposal(BAD), repair])
    control = Provider([SAFE, FAIL, *safety])
    result = renderer(dialogue, control).render(request())
    assert result.fallback_used and result.text == request().fallback_text
    assert result.relevance_check["status"] == "repair_failed"
    assert result.relevance_check["check_attempts"] == 1


def test_exact_approved_llm_wording_still_gets_relevance_check():
    original = request()
    dialogue = Provider([proposal(original.fallback_text)])
    control = Provider([PASS])
    result = renderer(dialogue, control).render(original)
    assert result.relevance_check["status"] == "passed"
    assert len(control.calls) == 1 and control.calls[0]["instructions"] == INSTRUCTIONS


def test_canonical_acceptance_cannot_be_vetoed_or_rewritten():
    original = replace(request(), speech_act="offer_acceptance", approved_terms=(("prepayment_fraction", .5),),
                       fallback_text="Принимаю полное предложение: предоплата 50%.",
                       approved_reply_options=("Принимаю полное предложение: предоплата 50%.",))
    dialogue, control = Provider([]), Provider([])
    result = renderer(dialogue, control).render(original)
    assert result.text == original.fallback_text and result.relevance_check is None
    assert dialogue.calls == control.calls == []


def test_historical_plan_has_no_extra_call_and_policy_roundtrips():
    original = base_request()
    dialogue, control = Provider([proposal(GOOD)]), Provider([SAFE])
    result = renderer(dialogue, control).render(original)
    assert result.relevance_check is None and len(control.calls) == 1
    plan = NpcUtterancePlan(stable_render_id("s", 1), "s", 1, "npc", "inform", request())
    assert utterance_plan_from_payload(utterance_plan_payload(plan)) == plan
    legacy = utterance_plan_payload(replace(plan, request=original))
    assert "relevance_policy_version" not in legacy["request"]
    assert utterance_plan_from_payload(legacy).request.relevance_policy_version == ""


def test_private_data_and_configured_credentials_do_not_enter_checker(monkeypatch):
    secret = "fixture-control-key-without-standard-prefix"
    monkeypatch.setenv("RELEVANCE_TEST_KEY", secret)
    original = replace(request(), dialogue_context=(PublicDialogueTurn("player", "Мой вопрос " + secret),))
    dialogue = Provider([proposal(GOOD)])
    control = Provider([SAFE, PASS], key="RELEVANCE_TEST_KEY")
    renderer(dialogue, control).render(original)
    serialized = json.dumps(control.calls[-1], ensure_ascii=False)
    assert secret not in serialized
    assert "[REDACTED_CREDENTIAL]" in serialized
    payload = json.loads(control.calls[-1]["messages"][0]["content"])
    assert not {"private_preparation", "utility_model", "reservation_utility", "role_brief"} & payload.keys()


def test_supply_repair_preserves_exact_package_and_delivery_metadata():
    original = replace(supply_request(), relevance_policy_version=VERSION)
    dialogue = Provider([{"reply": BAD}, {"reply": GOOD}])
    control = Provider([SAFE, FAIL, SAFE, PASS])
    result = renderer(dialogue, control).render(original)
    assert result.text == GOOD + "\n\n" + original.package_block
    assert result.relevance_check["status"] == "corrected"
    assert validated_dialogue_result(original, result).relevance_check == result.relevance_check
    assert len(dialogue.calls) + len(control.calls) == 6
    assert json.loads(control.calls[-1]["messages"][0]["content"])["immutable_package"] == original.package_block


@pytest.mark.parametrize("value,enabled", [(None, True), ("true", True), ("false", False)])
def test_configuration_default_and_explicit_switch(monkeypatch, value, enabled):
    monkeypatch.delenv("NEGOTIATION_NPC_RELEVANCE_CHECK", raising=False)
    if value is not None:
        monkeypatch.setenv("NEGOTIATION_NPC_RELEVANCE_CHECK", value)
    assert Settings.from_environment().npc_relevance_check is enabled


def test_configured_renderer_reuses_control_route(settings, monkeypatch):
    providers = []
    def factory(name, **kwargs):
        provider = Provider(model=kwargs["model"])
        providers.append(provider)
        return provider
    monkeypatch.setattr("backend.app.main.provider_for", factory)
    configured = _configured_dialogue_renderer(replace(settings, npc_provider="qwen", npc_model="dialogue",
                                                        control_provider="qwen", control_model="control"))
    assert configured.relevance_check_enabled
    assert configured._text_provider is providers[0]
    assert configured._relevance_provider is configured._grounding_provider is providers[1]


class RuntimeProvider(Provider):
    def generate(self, messages, *, instructions=None):
        self.calls.append({"messages": messages, "instructions": instructions})
        if instructions == INSTRUCTIONS:
            output = PASS
        elif "CANDIDATE_REPLY_JSON:" in messages[0]["content"]:
            output = SAFE
        else:
            data = json.loads(messages[0]["content"].split("\n", 2)[1])
            output = {"speech_act": data["speech_act"], "reply": data["approved_reply_options"][0]}
        return Generation(text=json.dumps(output, ensure_ascii=False), provider="qwen", model=self.config.model, latency_ms=1)


@pytest.mark.parametrize("mode", ["training", "benchmark", "external_agent", "disabled"])
def test_service_attaches_policy_only_to_human_training_and_records_separate_trace(settings, mode):
    provider = RuntimeProvider()
    configured = renderer(provider, provider)
    configured.relevance_check_enabled = mode != "disabled"
    with TestClient(create_app(replace(settings, llm_trace_enabled=True),
                              npc_dialogue_renderer=configured)) as client:
        client.event_hooks["response"].append(ResponseContractCheck(client.app))
        payload = create_payload("relevance-" + mode)
        if mode == "benchmark":
            payload.update(run_mode="benchmark", hints_enabled=False, benchmark_run_id="relevance-run",
                           trial_id="relevance-trial", benchmark_expected_trials=1)
        elif mode == "external_agent":
            payload["participants"][0]["controller"] = "external_agent"
        response = client.post("/api/v1/sessions", json=payload,
                               headers=bearer("test-admin") if mode == "benchmark" else {})
        assert response.status_code == 201, response.text
        session = response.json()
        body = {"message": "Какие ваши приоритеты?", "expected_revision": session["revision"], "idempotency_key": "turn"}
        response = client.post(f"/api/v1/sessions/{session['session_id']}/messages",
                               headers=bearer(session["participant_token"]), json=body)
        assert response.status_code == 200, response.text
        metadata = response.json()["committed_actions"][-1]["dialogue_renderer"]
        assert ("relevance_check" in metadata) is (mode == "training")
        if mode == "training":
            assert metadata["relevance_check"]["status"] == "passed"
        before = len(provider.calls)
        replay = client.post(f"/api/v1/sessions/{session['session_id']}/messages",
                             headers=bearer(session["participant_token"]), json=body)
        assert replay.json() == response.json() and len(provider.calls) == before
        traces = client.app.state.llm_traces.list()["items"]
        assert any(item["task"] == "npc_relevance" for item in traces) is (mode == "training")
        assert not traces if mode == "benchmark" else bool(traces)


def test_delivered_relevance_metadata_survives_restart_without_provider_calls(settings):
    provider = RuntimeProvider()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer(provider, provider))) as client:
        session = client.post("/api/v1/sessions", json=create_payload("persisted-relevance")).json()
        route = f"/api/v1/sessions/{session['session_id']}/messages"
        headers = bearer(session["participant_token"])
        body = {
            "message": "Какие ваши приоритеты?", "expected_revision": session["revision"], "idempotency_key": "turn",
        }
        response = client.post(route, headers=headers, json=body)
        assert response.status_code == 200
        history = client.get(route, headers=headers).json()
        assert VERSION in json.dumps(response.json())
    unused = Provider([])
    with TestClient(create_app(settings, npc_dialogue_renderer=LlmNpcDialogueRenderer(unused))) as restarted:
        restarted.event_hooks["response"].append(ResponseContractCheck(restarted.app))
        assert restarted.get(route, headers=headers).json() == history
        assert restarted.post(route, headers=headers, json=body).json() == response.json()
        assert unused.calls == []


def test_persisted_plan_policy_still_applies_when_runtime_switch_is_disabled():
    plan = NpcUtterancePlan(stable_render_id("s", 1), "s", 1, "npc", "inform", request())
    restored = utterance_plan_from_payload(utterance_plan_payload(plan))
    dialogue, control = Provider([proposal(GOOD)]), Provider([SAFE, PASS])
    result = LlmNpcDialogueRenderer(dialogue, grounding_provider=control,
                                   relevance_check_enabled=False).render(restored.request)
    assert result.relevance_check["status"] == "passed" and len(control.calls) == 2


def test_initial_grounding_failure_never_claims_relevance_approval():
    dialogue, control = Provider([proposal(BAD)]), Provider([{"safe": False}])
    result = renderer(dialogue, control).render(request())
    assert result.fallback_used and result.relevance_check is None
    assert len(control.calls) == 1


@pytest.mark.parametrize("value", [None, [], True, {"relevant": False, "issues": "off_topic"}])
def test_verdict_parser_rejects_non_objects_and_wrong_types(value):
    with pytest.raises(ValueError):
        validate_verdict(value)
