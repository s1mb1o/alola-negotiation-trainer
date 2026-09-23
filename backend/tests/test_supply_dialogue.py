from dataclasses import replace
import json

import pytest

from backend.app.dialogue import (
    LlmNpcDialogueRenderer,
    NpcDialogueRequest,
    NpcDialogueResult,
    NpcUtterancePlan,
    PublicDialogueTurn,
    stable_render_id,
    utterance_plan_payload,
    utterance_plan_from_payload,
    validated_dialogue_result,
)
from clients.providers import AgentModelConfig, Generation


def test_service_renders_supply_preliminary_proposals_with_llm(settings):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    from backend.tests.test_supply_protocol import create_supply, submit
    from backend.tests.conftest import credentials

    prose = "Готов обсудить стоимость. Какие условия оплаты вам доступны?"
    provider = SupplyProvider([{"reply": prose}, {"safe": True}])
    with TestClient(
        create_app(settings, npc_dialogue_renderer=LlmNpcDialogueRenderer(provider))
    ) as client:
        session = create_supply(client)
        response = submit(
            client, session, credentials(session)["buyer"], "Можно снизить цену? Бюджет ограничен."
        )
        assert len(provider.calls) == 2
        npc = response["committed_actions"][-1]
        assert npc["action"] == "propose"
        assert npc["dialogue_renderer"]["mode"] == "llm"
        assert npc["message"].startswith(prose + "\n\n")
        prompt = json.loads(provider.calls[0]["messages"][0]["content"])
        assert len(prompt["retrieved_reply_examples"]) == 3
        assert all(
            item["library_version"] == "reply_examples_v1"
            for item in prompt["retrieved_reply_examples"]
        )


def test_supply_pending_render_recovers_without_new_llm_calls(settings, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    from backend.tests.test_supply_protocol import create_supply
    from backend.tests.conftest import credentials, bearer

    provider = SupplyProvider([])
    with TestClient(create_app(settings)) as client:
        session = create_supply(client)
        token = credentials(session)["buyer"]
        body = {
            "message": "Можно снизить цену? Бюджет ограничен.",
            "expected_revision": 0,
            "idempotency_key": "crash-render",
        }

        def crash(plan):
            raise RuntimeError("simulated process loss after intent")

        monkeypatch.setattr(client.app.state.service, "_render_npc_plan", crash)
        with pytest.raises(RuntimeError, match="simulated process loss"):
            client.post(
                f"/api/v1/sessions/{session['session_id']}/messages",
                headers=bearer(token),
                json=body,
            )
    with TestClient(
        create_app(settings, npc_dialogue_renderer=LlmNpcDialogueRenderer(provider))
    ) as restarted:
        response = restarted.post(
            f"/api/v1/sessions/{session['session_id']}/messages", headers=bearer(token), json=body
        )
        assert response.status_code == 200
        assert provider.calls == []
        assert (
            response.json()["committed_actions"][-1]["dialogue_renderer"]["failure_reason"]
            == "restart_recovery"
        )
        assert (
            response.json()["observation"]["preliminary_proposals"][0]["terms"]["base_price"][
                "minor_units"
            ]
            == 11500000
        )


class SupplyProvider:
    def __init__(self, responses):
        self.config = AgentModelConfig(provider="openai", model="offline-supply-fixture")
        self.responses = list(responses)
        self.calls = []

    def generate(self, messages, *, instructions=None):
        self.calls.append({"messages": messages, "instructions": instructions})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return Generation(
            text=json.dumps(response, ensure_ascii=False),
            provider="fixture",
            model="fixture",
            latency_ms=0,
        )


def supply_request(action="propose"):
    block = "Основная партия: 109 500 EUR.\nРезерв: не указан."
    return NpcDialogueRequest(
        language="ru",
        currency="EUR",
        speech_act="acknowledge_information",
        approved_terms=(("base_price", {"currency": "EUR", "minor_units": 10950000}),),
        public_interest_labels=(),
        participant_facing_terms=(),
        dialogue_context=(PublicDialogueTurn("player", "Для нас важен запуск проекта."),),
        approved_reply_options=("Давайте обсудим график.\n\n" + block,),
        fallback_text="Давайте обсудим график.\n\n" + block,
        render_contract="supply-dialogue-v1",
        package_block=block,
        supply_action=action,
    )


def test_supply_llm_paragraphs_preserve_engine_block_and_do_not_receive_private_state():
    prose = "Запуск проекта для вас важен.\n\nКакая часть поставки нужна для интеграции?"
    provider = SupplyProvider([{"reply": prose}, {"safe": True}])
    request = supply_request()
    result = LlmNpcDialogueRenderer(provider).render(request)
    assert result.mode == "llm"
    assert result.text == prose + "\n\n" + request.package_block
    assert validated_dialogue_result(request, result).text == result.text
    assert len(provider.calls) == 2
    payload = json.loads(provider.calls[0]["messages"][0]["content"])
    assert set(payload) == {
        "contract",
        "language",
        "scenario_title",
        "npc_role",
        "difficulty",
        "proposed_action",
        "fallback_prose",
        "immutable_package",
        "retrieved_reply_examples",
        "untrusted_conversation",
        "training_context",
    }


@pytest.mark.parametrize(
    "bad",
    [
        {"reply": "Снижаю цену до 100000 EUR."},
        {"reply": "Договорились, условия приняты."},
        {"reply": "Цена составляет сто тысяч евро."},
        {"refusal": "No."},
        {"reply": "Какая часть поставки нужна?", "terms": {"price": 1}},
    ],
)
def test_supply_invalid_generation_falls_back_without_changing_package(bad):
    provider = SupplyProvider([bad])
    request = supply_request()
    result = LlmNpcDialogueRenderer(provider).render(request)
    assert result.fallback_used
    assert result.text == request.fallback_text


def test_supply_grounding_failure_and_changed_block_fail_closed():
    request = supply_request()
    provider = SupplyProvider(
        [{"reply": "Какая часть поставки нужна для интеграции?"}, {"safe": False}]
    )
    assert LlmNpcDialogueRenderer(provider).render(request).text == request.fallback_text
    changed = NpcDialogueResult(
        request.fallback_text.replace("109 500", "99 500"), "llm", "test", "test", False
    )
    assert validated_dialogue_result(request, changed).text == request.fallback_text


@pytest.mark.parametrize("action", ["opening", "publish", "accept", "reject"])
def test_supply_binding_wording_never_calls_provider(action):
    provider = SupplyProvider([])
    request = supply_request(action)
    assert LlmNpcDialogueRenderer(provider).render(request).text == request.fallback_text
    assert provider.calls == []


def test_supply_plan_roundtrip_preserves_version_and_exact_package():
    request = supply_request()
    plan = NpcUtterancePlan(
        stable_render_id("supply-test", 5), "supply-test", 5, "supplier", "propose", request
    )
    restored = utterance_plan_from_payload(json.loads(json.dumps(utterance_plan_payload(plan))))
    assert restored == plan
    assert restored.request.render_contract == "supply-dialogue-v1"
    with pytest.raises(ValueError):
        replace(request, render_contract="unknown-contract")
