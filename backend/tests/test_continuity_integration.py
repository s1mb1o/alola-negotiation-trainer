from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.conversation import build_conversation_memory
from backend.app.dialogue import (
    NpcDialogueRequest,
    NpcDialogueResult,
    NpcUtterancePlan,
    TemplateNpcDialogueRenderer,
    build_safe_render_input,
    stable_render_id,
    utterance_plan_from_payload,
    utterance_plan_payload,
    validate_rendered_reply,
)
from backend.app.main import create_app

from .conftest import PROJECT_ROOT, bearer, create_payload


class CapturingTemplateRenderer:
    def __init__(self) -> None:
        self.requests: list[NpcDialogueRequest] = []

    def render(self, request: NpcDialogueRequest) -> NpcDialogueResult:
        self.requests.append(request)
        return TemplateNpcDialogueRenderer().render(request)


@pytest.fixture
def continuity_settings(settings: Settings, tmp_path: Path) -> Settings:
    # Keep production versions immutable. This English fixture exercises the same
    # partial-opening contract as the Russian supplier scenario.
    document = yaml.safe_load(
        (PROJECT_ROOT / "examples/scenario_saas_subscription_en_v2.yaml").read_text()
    )
    document["scenario"]["version"] = 90
    seller = document["scenario"]["roles"]["seller"]
    opening = seller.pop("opening_offer")
    seller["opening_position"] = {"price": opening["price"]}
    scenario_dir = tmp_path / "continuity_scenarios"
    scenario_dir.mkdir()
    (scenario_dir / "english_partial_opening.yaml").write_text(yaml.safe_dump(document))
    return replace(settings, scenario_directories=(*settings.scenario_directories, scenario_dir))


def _create(client: TestClient, key: str, language: str = "ru", *, version: int | None = None) -> dict:
    payload = create_payload(key, language=language)
    payload.update(
        scenario_id="supplier_001" if language == "ru" else "saas_subscription_en",
        scenario_version=version if version is not None else (4 if language == "ru" else 90),
    )
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _submit(client: TestClient, session: dict, message: str) -> dict:
    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/messages",
        headers=bearer(session["participant_token"]),
        json={
            "message": message,
            "idempotency_key": f"message-{session['revision']}",
            "expected_revision": session["revision"],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    session["revision"] = body["revision"]
    return body


def _history(client: TestClient, session: dict) -> list[dict[str, Any]]:
    response = client.get(
        f"/api/v1/sessions/{session['session_id']}/history",
        headers=bearer(session["participant_token"]),
    )
    assert response.status_code == 200
    return response.json()["events"]


@pytest.mark.parametrize(
    ("language", "focus", "proposal", "amount", "followup"),
    [
        (
            "ru", "Хочу обсудить цену.", "Предлагаю цену 105 000 евро.", 105_000,
            "Почему это для вас важно?",
        ),
        (
            "en", "We would like to discuss the price.",
            "I offer a price of RUB 1,150,000.", 1_150_000, "Why does that matter to you?",
        ),
    ],
)
def test_focused_partial_offer_continues_topic_without_filling_or_binding_terms(
    continuity_settings: Settings,
    language: str,
    focus: str,
    proposal: str,
    amount: int,
    followup: str,
) -> None:
    renderer = CapturingTemplateRenderer()
    with TestClient(create_app(continuity_settings, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, f"focused-partial-{language}", language)
        focused = _submit(client, session, focus)
        assert focused["committed_actions"][-1]["speech_act"] == "focused_discussion"
        assert renderer.requests[-1].focused_term_ids == ("price",)
        assert not renderer.requests[-1].approved_reasons

        partial = _submit(client, session, proposal)
        assert partial["committed_actions"][-1]["speech_act"] == "acknowledge_partial_offer"
        assert partial["committed_actions"][-1]["action"] == "inform"
        assert renderer.requests[-1].focused_term_ids == ("price",)
        followup_body = _submit(client, session, followup)
        request = renderer.requests[-1]
        assert request.focused_term_ids == ("price",)
        assert request.approved_reasons
        assert request.conversation_memory["current_topic"]["term_id"] == "price"
        assert request.conversation_memory["agreement"] is None
        assert request.approved_terms == ()
        for body in (partial, followup_body):
            assert body["status"] == "active"
            offer = body["observation"]["active_offers"][0]
            assert offer["terms"] == {"price": amount}
            assert offer["unresolved_required_terms"] == ["prepayment_fraction", "delivery_weeks"]
        offers = request.conversation_memory["offers"]
        assert offers[-1]["terms"] == {"price": amount}
        assert offers[-1]["speaker"] == "player"
        history = _history(client, session)
        assert offers[-1]["source_event_id"] in {event["event_id"] for event in history}
        assert not any(event["type"] == "agreement.reached" for event in history)


@pytest.mark.parametrize(
    ("language", "greeting", "question", "reason_id", "other_question", "other_ids"),
    [
        (
            "ru", "Здравствуйте", "Почему для вас важна предоплата?", "early_payment",
            "Почему важен срок поставки?", ("acceleration_cost",),
        ),
        (
            "en", "Hello", "Why does prepayment matter to you?", "advance_payment",
            "Why does the launch timeline matter?", (),
        ),
    ],
)
def test_reasons_are_topic_gated_and_only_delivered_reasons_enter_next_request(
    continuity_settings: Settings,
    language: str,
    greeting: str,
    question: str,
    reason_id: str,
    other_question: str,
    other_ids: tuple[str, ...],
) -> None:
    renderer = CapturingTemplateRenderer()
    with TestClient(create_app(continuity_settings, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, f"reason-gates-{language}", language)
        _submit(client, session, greeting)
        assert renderer.requests[-1].approved_reasons == ()
        assert renderer.requests[-1].disclosed_reasons == ()

        body = _submit(client, session, question)
        selected_request = renderer.requests[-1]
        assert tuple(item[0] for item in selected_request.approved_reasons) == (reason_id,)
        assert selected_request.disclosed_reasons == ()
        reason_text = selected_request.approved_reasons[0][1]
        assert reason_text in body["committed_actions"][-1]["message"]
        disclosure_event = next(
            event for event in _history(client, session)
            if event["type"] == "npc.utterance.delivered"
            and event["payload"].get("disclosed_reason_ids") == [reason_id]
        )

        _submit(client, session, other_question)
        next_request = renderer.requests[-1]
        assert tuple(item[0] for item in next_request.approved_reasons) == other_ids
        assert next_request.disclosed_reasons == (
            (reason_id, reason_text, disclosure_event["event_id"]),
        )
        filename = (
            "scenario_supplier_001_v4.yaml" if language == "ru"
            else "scenario_saas_subscription_en_v2.yaml"
        )
        scenario = yaml.safe_load((PROJECT_ROOT / "examples" / filename).read_text())["scenario"]
        safe_input = build_safe_render_input(selected_request)
        for role in scenario["roles"].values():
            assert role["brief"]["context"] not in safe_input
            assert role["brief"]["objective"] not in safe_input
            for reason in role["dialogue_reasons"]:
                if reason["id"] != reason_id:
                    assert reason["text"] not in safe_input
        assert "source_ref" not in safe_input
        assert "reservation_utility" not in safe_input


@pytest.mark.parametrize(
    ("language", "focus", "why", "waiver_question", "short_why", "reason_id"),
    [
        (
            "ru", "Хочу обсудить предоплату.", "Почему для вас важна предоплата?",
            "Значит, аванс уже отменён?", "Почему?", "early_payment",
        ),
        (
            "en", "Let us discuss prepayment.", "Why does prepayment matter to you?",
            "Does that mean the advance payment has already been waived?", "Why?",
            "advance_payment",
        ),
    ],
)
def test_delivered_reason_remains_context_without_forcing_repetition_on_later_questions(
    continuity_settings: Settings,
    language: str,
    focus: str,
    why: str,
    waiver_question: str,
    short_why: str,
    reason_id: str,
) -> None:
    renderer = CapturingTemplateRenderer()
    with TestClient(create_app(continuity_settings, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, f"disclosed-reason-followup-{language}", language)
        original_offers = session["observation"]["active_offers"]
        _submit(client, session, focus)
        _submit(client, session, why)
        first_request = renderer.requests[-1]
        assert tuple(item[0] for item in first_request.approved_reasons) == (reason_id,)
        reason_text = first_request.approved_reasons[0][1]
        event = next(
            item for item in _history(client, session)
            if item["type"] == "npc.utterance.delivered"
            and item["payload"].get("disclosed_reason_ids") == [reason_id]
        )

        for question in (waiver_question, short_why):
            body = _submit(client, session, question)
            request = renderer.requests[-1]
            assert request.approved_reasons == ()
            assert request.disclosed_reasons == ((reason_id, reason_text, event["event_id"]),)
            assert request.conversation_memory["agreement"] is None
            assert body["status"] == "active"
            assert body["observation"]["active_offers"] == original_offers
        disclosure_events = [
            item for item in _history(client, session)
            if reason_id in item["payload"].get("disclosed_reason_ids", [])
        ]
        assert len(disclosure_events) == 1


def test_legacy_scenario_without_reasons_keeps_nonbinding_topic_continuity(
    settings: Settings,
) -> None:
    renderer = CapturingTemplateRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, "legacy-continuity", version=3)
        _submit(client, session, "Хочу обсудить цену.")
        body = _submit(client, session, "Предлагаю цену 105 000 евро.")
        assert body["committed_actions"][-1]["speech_act"] == "acknowledge_partial_offer"
        _submit(client, session, "Почему это для вас важно?")
        assert renderer.requests[-1].approved_reasons == ()
        assert renderer.requests[-1].disclosed_reasons == ()
        assert renderer.requests[-1].conversation_memory["current_topic"]["term_id"] == "price"
        assert renderer.requests[-1].conversation_memory["agreement"] is None


@pytest.mark.parametrize(
    ("language", "focus", "unrelated_question", "why", "reason_id"),
    [
        (
            "ru", "Хочу обсудить цену.", "Какую компанию вы представляете?",
            "Почему?", "acceptable_supply",
        ),
        (
            "en", "We would like to discuss the price.", "How are you?",
            "Why?", "subscription_margin",
        ),
    ],
)
def test_unrelated_question_does_not_inherit_reason_disclosure_but_short_why_does(
    continuity_settings: Settings,
    language: str,
    focus: str,
    unrelated_question: str,
    why: str,
    reason_id: str,
) -> None:
    renderer = CapturingTemplateRenderer()
    with TestClient(create_app(continuity_settings, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, f"unrelated-question-{language}", language)
        _submit(client, session, focus)
        _submit(client, session, unrelated_question)
        unrelated = renderer.requests[-1]
        assert unrelated.conversation_memory["current_topic"]["term_id"] == "price"
        assert unrelated.approved_reasons == ()
        assert unrelated.disclosed_reasons == ()

        focused_session = _create(client, f"short-why-{language}", language)
        _submit(client, focused_session, focus)
        _submit(client, focused_session, why)
        assert tuple(item[0] for item in renderer.requests[-1].approved_reasons) == (reason_id,)


@pytest.mark.parametrize(
    ("language", "message", "expected_speech_act"),
    [
        ("ru", "Здравствуйте, давайте обсудим только цену.", "focused_discussion"),
        ("en", "Hello, let us discuss only price.", "focused_discussion"),
        ("ru", "Ты дурак, давайте обсудим только цену.", "abusive_language_boundary"),
        ("en", "You are an idiot, let us discuss only price.", "abusive_language_boundary"),
    ],
)
def test_explicit_focus_overrides_greeting_but_preserves_abuse_boundary(
    continuity_settings: Settings, language: str, message: str, expected_speech_act: str,
) -> None:
    renderer = CapturingTemplateRenderer()
    with TestClient(create_app(continuity_settings, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, f"greeting-focus-{language}-{expected_speech_act}", language)
        body = _submit(client, session, message)
        assert body["committed_actions"][-1]["speech_act"] == expected_speech_act
        assert renderer.requests[-1].focused_term_ids == ("price",)
        assert renderer.requests[-1].approved_reasons == ()
        assert renderer.requests[-1].conversation_memory["agreement"] is None


def _reason_request() -> NpcDialogueRequest:
    reason = "Ранняя оплата имеет для нас высокую ценность."
    return NpcDialogueRequest(
        language="ru",
        currency="EUR",
        speech_act="general_answer",
        approved_terms=(),
        public_interest_labels=(),
        participant_facing_terms=(("prepayment_fraction", "предоплата"),),
        dialogue_context=(),
        approved_reply_options=(reason,),
        fallback_text=reason,
        approved_reasons=(("early_payment", reason),),
    )


@pytest.mark.parametrize(
    ("field", "malformed"),
    [
        ("approved_reasons", (("early_payment",),)),
        ("approved_reasons", (("early_payment", "Текст причины.", "extra"),)),
        ("approved_reasons", ("ab",)),
        ("disclosed_reasons", (("early_payment", "Текст причины."),)),
        ("disclosed_reasons", (("early_payment", "Текст причины.", "evt_source", "extra"),)),
        ("disclosed_reasons", (("early_payment", "Текст причины.", "private_source"),)),
    ],
)
def test_reason_request_rejects_malformed_reason_fields(field: str, malformed: tuple) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(_reason_request(), **{field: malformed})


@pytest.mark.parametrize("malformed", [["ab"], {"ab": "not a reason tuple"}])
def test_durable_reason_plan_rejects_strings_and_objects_instead_of_reason_arrays(
    malformed: object,
) -> None:
    plan = NpcUtterancePlan(
        render_id=stable_render_id("reason-plan-session", 1),
        session_id="reason-plan-session",
        intent_revision=1,
        npc_participant_id="reason-plan-npc",
        action="inform",
        request=_reason_request(),
    )
    payload = utterance_plan_payload(plan)
    payload["request"]["approved_reasons"] = malformed
    with pytest.raises((TypeError, ValueError)):
        utterance_plan_from_payload(payload)


@pytest.mark.parametrize(
    "reply",
    [
        "Почему для вас важны условия оплаты?",
        "Мы ценим раннюю оплату.",
        "Ранняя оплата имеет для нас умеренную ценность.",
    ],
)
def test_selected_reason_cannot_be_omitted_or_paraphrased(reply: str) -> None:
    with pytest.raises(ValueError, match="omitted or changed a selected authored reason"):
        validate_rendered_reply(
            json.dumps({"speech_act": "general_answer", "reply": reply}), _reason_request(),
        )


def test_selected_reason_allows_extra_nonnumeric_wording_around_exact_authored_text() -> None:
    request = _reason_request()
    reply = request.approved_reasons[0][1] + " Какой порядок оплаты вы предлагаете?"
    assert validate_rendered_reply(
        json.dumps({"speech_act": "general_answer", "reply": reply}), request,
    ) == reply


@pytest.mark.parametrize("source", ["topic", "offer"])
def test_renderer_memory_rejects_terms_outside_participant_facing_fields(source: str) -> None:
    message = {
        "id": 1,
        "session_revision": 1,
        "participant_id": "player",
        "content": "Хочу обсудить цену.",
    }
    event = {
        "event_id": "evt_price",
        "session_revision": 1,
        "participant_id": "player",
        "type": "offer.countered",
        "payload": {"offer_id": "offer_price", "offer_revision": 1, "terms": {"price": 105_000}},
    }
    memory = build_conversation_memory(
        [message] if source == "topic" else [],
        [event] if source == "offer" else [],
        npc_participant_id="npc",
        term_labels={"price": "цена", "prepayment_fraction": "предоплата"},
        required_term_ids=["price", "prepayment_fraction"],
    )
    # This request authorizes prepayment only. A structurally valid price memory
    # must not expand the participant-facing term contract.
    with pytest.raises(ValueError, match="memory terms must be participant-facing"):
        replace(_reason_request(), conversation_memory=memory)


def test_configured_credentials_are_redacted_before_persisted_memory_and_truncation(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_secret = "opaque-memory-provider-secret"
    admin_secret = "opaque-memory-administrator-secret"
    monkeypatch.setenv("TEST_MEMORY_PROVIDER_SECRET", provider_secret)
    configured = replace(
        settings, npc_api_key_env="TEST_MEMORY_PROVIDER_SECRET", admin_token=admin_secret,
    )
    renderer = CapturingTemplateRenderer()
    with TestClient(create_app(configured, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, "memory-custom-credentials")
        _submit(client, session, f"Нам важно сохранить секреты: {provider_secret}; {admin_secret}.")
        request = renderer.requests[-1]
        serialized = build_safe_render_input(request)
        assert request.conversation_memory["player_statements"]
        for secret in (provider_secret, admin_secret):
            assert secret not in serialized
        with client.app.state.database.read_connection() as connection:
            stored = connection.execute(
                "SELECT id, content FROM messages WHERE session_id = ? AND session_revision = 1",
                (session["session_id"],),
            ).fetchone()
        assert provider_secret not in stored["content"]
        assert admin_secret not in stored["content"]

        # Simulate an older transcript that predates credential redaction. The
        # configured key crosses the memory text boundary before sanitization.
        historical = "Нам важно " + "а" * 380 + " " + provider_secret + "; " + admin_secret
        with client.app.state.database.write_transaction() as connection:
            connection.execute("UPDATE messages SET content = ? WHERE id = ?", (historical, stored["id"]))
        _submit(client, session, "Почему для вас важна предоплата?")
        recovered = renderer.requests[-1]
        assert len(recovered.conversation_memory["player_statements"][0]["text"]) == 400
        serialized = build_safe_render_input(recovered)
        assert provider_secret[:10] not in serialized
        assert admin_secret not in serialized


def test_restart_retains_early_focus_postponement_and_disclosure_without_session_leakage(
    settings: Settings,
) -> None:
    renderer = CapturingTemplateRenderer()
    early_focus = "Давайте обсудим только цену. Оплату обсудим позже."
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, "restart-continuity")
        _submit(client, session, early_focus)
        first_topic = renderer.requests[-1].conversation_memory["current_topic"]
        _submit(client, session, "Почему для вас важна предоплата?")
        disclosure = next(
            event for event in _history(client, session)
            if event["type"] == "npc.utterance.delivered"
            and event["payload"].get("disclosed_reason_ids") == ["early_payment"]
        )
        _submit(client, session, "Нам критично сохранить устойчивость интеграции.")
        for _ in range(5):
            _submit(client, session, "Давайте продолжим разговор.")
        assert all(turn.text != early_focus for turn in renderer.requests[-1].dialogue_context)
        assert len(renderer.requests[-1].dialogue_context) == 12

    restarted_renderer = CapturingTemplateRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=restarted_renderer)) as client:
        other = _create(client, "isolated-continuity")
        _submit(client, other, "Здравствуйте")
        isolated = restarted_renderer.requests[-1]
        assert isolated.disclosed_reasons == ()
        assert isolated.conversation_memory["current_topic"] is None
        assert isolated.conversation_memory["deferred_topics"] == []
        assert early_focus not in build_safe_render_input(isolated)

        _submit(client, session, "Почему это для вас важно?")
        recovered = restarted_renderer.requests[-1]
        memory = recovered.conversation_memory
        assert memory["current_topic"] == first_topic
        assert memory["deferred_topics"] == [
            {**first_topic, "term_id": "prepayment_fraction"},
        ]
        assert memory["agreement"] is None
        assert any("устойчивость интеграции" in item["text"] for item in memory["player_statements"])
        assert recovered.disclosed_reasons[0][0] == "early_payment"
        assert recovered.disclosed_reasons[0][2] == disclosure["event_id"]
        with client.app.state.database.read_connection() as connection:
            message_ids = {
                row["id"] for row in connection.execute(
                    "SELECT id FROM messages WHERE session_id = ?", (session["session_id"],)
                )
            }
        for item in [memory["current_topic"], *memory["deferred_topics"], *memory["questions"]]:
            assert item["source_message_id"] in message_ids
        assert other["session_id"] not in json.dumps(memory)

        _submit(client, session, "Теперь вернёмся к оплате.")
        resumed = restarted_renderer.requests[-1]
        assert resumed.focused_term_ids == ("prepayment_fraction",)
        assert resumed.conversation_memory["current_topic"]["term_id"] == "prepayment_fraction"
        assert resumed.conversation_memory["deferred_topics"] == []
        assert resumed.conversation_memory["agreement"] is None
