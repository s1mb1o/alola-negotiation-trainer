"""DR-51 contract tests. Fixture output is not evidence of live model quality."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from backend.app.coaching import generate_coaching
from backend.app.dialogue import (
    LlmNpcDialogueRenderer, NpcDialogueRequest, NpcUtterancePlan, PublicDialogueTurn,
    stable_render_id, utterance_plan_from_payload, utterance_plan_payload,
)
from backend.app.methodology import VERSION, assess_economics
from backend.app.training import classify_social
from .conftest import bearer
from .behavior_fixtures import behavior_fixture
from .test_grounded_goal_dialogue import OpeningProvider, opening_request
from .test_supply_dialogue import SupplyProvider, supply_request
from .test_training_loop import Provider, create, send


@pytest.mark.parametrize("utility, surplus, margin, acceptable", [
    (75, 35, 15, True), (60, 20, 0, True), (50, 10, -10, False),
    (40, 0, -20, False), (30, -10, -30, False),
])
def test_batna_and_reservation_are_distinct(utility, surplus, margin, acceptable):
    result = assess_economics({"agreement": True, "participant_utility": utility},
                             {"batna_utility": 40, "reservation_utility": 60})
    assert result == {"version": VERSION, "zopa": "not_inferred", "economics": {
        "outcome": "agreement", "surplus_over_batna": surplus,
        "margin_over_reservation": margin, "meets_reservation": acceptable,
    }}


def test_no_agreement_has_no_deal_surplus():
    result = assess_economics({"agreement": False, "participant_utility": 40},
                             {"batna_utility": 40, "reservation_utility": 60})
    assert result["economics"] == {"outcome": "no_agreement", "surplus_over_batna": None,
                                   "margin_over_reservation": None, "meets_reservation": None}


def scalar_request():
    fallback = "Что мешает согласовать условия?"
    return NpcDialogueRequest(
        language="ru", currency="EUR", speech_act="general_answer", approved_terms=(),
        public_interest_labels=(), participant_facing_terms=(("price", "цена"),),
        dialogue_context=(PublicDialogueTurn("player", "Нам важно успеть к запуску проекта."),),
        approved_reply_options=(fallback,), fallback_text=fallback,
        conversation_goal="Identify the constraint behind the position.",
        methodology_version=VERSION,
    )


@pytest.mark.parametrize("dialogue_request, action", [(scalar_request(), "inform"),
    (replace(supply_request(), methodology_version=VERSION), "propose")])
def test_render_plan_keeps_methodology_and_reads_historical_plans(dialogue_request, action):
    request = dialogue_request
    plan = NpcUtterancePlan(stable_render_id("methods", 1), "methods", 1, "npc", action, request)
    payload = json.loads(json.dumps(utterance_plan_payload(plan)))
    assert utterance_plan_from_payload(payload) == plan
    del payload["request"]["methodology_version"]
    historical = utterance_plan_from_payload(payload)
    assert historical.request.methodology_version == ""
    assert historical.request.approved_terms == request.approved_terms
    with pytest.raises(ValueError, match="methodology"):
        replace(request, methodology_version="unknown")


def test_grounded_opening_uses_methodology_without_changing_authored_values():
    request = replace(opening_request(), methodology_version=VERSION)
    provider = OpeningProvider(request.fallback_template)
    result = LlmNpcDialogueRenderer(provider).render_opening(request)
    assert result.mode == "llm" and not result.fallback_used
    assert request.public_position in result.text
    assert "Harvard" in provider.calls[0]["instructions"]
    assert "Reject invented objective criteria" in provider.calls[1]["instructions"]


@pytest.mark.parametrize("safe", [True, False])
def test_scalar_methodology_passes_grounding_or_uses_safe_fallback(safe):
    request = scalar_request()
    reply = "Похоже, для вас важен запуск проекта. Что сейчас мешает подготовке?"
    provider = SupplyProvider([{"speech_act": request.speech_act, "reply": reply}, {"safe": safe}])
    result = LlmNpcDialogueRenderer(provider).render(request)
    assert len(provider.calls) == 2
    assert "Harvard" in provider.calls[0]["instructions"]
    assert "Reject an evasive reply" in provider.calls[1]["instructions"]
    assert result.text == (reply if safe else request.fallback_text)
    assert result.fallback_used is not safe


def test_supply_methods_preserve_package_and_canonical_acceptance():
    request = replace(supply_request(), methodology_version=VERSION)
    reply = "Какие условия оплаты вам доступны?"
    provider = SupplyProvider([{"reply": reply}, {"safe": True}])
    result = LlmNpcDialogueRenderer(provider).render(request)
    assert result.mode == "llm" and result.text.endswith(request.package_block)
    assert "Harvard" in provider.calls[0]["instructions"]
    assert "selected engine action" in provider.calls[1]["instructions"]
    canonical = replace(supply_request("accept"), methodology_version=VERSION)
    bypass = SupplyProvider([])
    result = LlmNpcDialogueRenderer(bypass).render(canonical)
    assert result.text == canonical.fallback_text and not bypass.calls


def coaching_fixture():
    source = {"ref": "message:1", "text": "Прекращаю переговоры.", "source_revision": 1,
              "role": "buyer", "is_player": True}
    package = {"revision": 2, "language": "ru", "evidence": [source],
               "outcome": {"agreement": False, "participant_utility": 40},
               "economic_baseline": {"batna_utility": 40, "reservation_utility": 60}}
    package["methodology"] = assess_economics(package["outcome"], package["economic_baseline"])
    cards = [{"dimension": dimension, "assessment": "insufficient_evidence",
              "evidence_refs": [source["ref"]], "observation": "Причина выхода не указана.",
              "recommendation": "Объясните причину выхода.",
              "alternative_phrase": "Давайте сравним варианты перед решением.",
              "next_practice": "Сопоставьте предложенный пакет со своей альтернативой."}
             for dimension in ("economics", "process", "communication")]
    return package, {"summary": "Соглашения нет.", "goal_assessment": "Условия не согласованы.",
                     "cards": cards, "behavior": behavior_fixture()}


@pytest.mark.parametrize("damage", ["missing", "duplicate", "no_assessment", "invented_ref", "injection", "grounding"])
def test_incomplete_or_ungrounded_methodology_review_is_not_published(damage):
    package, candidate = coaching_fixture()
    if damage == "missing":
        candidate["cards"].pop()
    elif damage == "duplicate":
        candidate["cards"][1]["dimension"] = "economics"
    elif damage == "no_assessment":
        del candidate["cards"][1]["assessment"]
    elif damage == "invented_ref":
        candidate["cards"][1]["evidence_refs"] = ["message:404"]
    elif damage == "injection":
        candidate["cards"][1]["observation"] = "<script>alert(1)</script>"
    else:
        candidate["cards"][0]["observation"] = "Ваша выгода относительно BATNA равна 100."
    provider = Provider([candidate, {"safe": False}])
    result = generate_coaching(provider, package, lambda value: value)
    assert result["status"] == "unavailable" and "cards" not in result
    assert len(provider.calls) == (2 if damage == "grounding" else 1)


def test_review_has_three_dimensions_exact_evidence_and_no_skill_penalty():
    package, candidate = coaching_fixture()
    provider = Provider([candidate, {"safe": True}])
    before = deepcopy(package)
    result = generate_coaching(provider, package, lambda value: value)
    assert result["status"] == "complete"
    assert {card["dimension"] for card in result["cards"]} == {"economics", "process", "communication"}
    assert all(card["assessment"] == "insufficient_evidence" for card in result["cards"])
    assert all(card["evidence"] == package["evidence"] for card in result["cards"])
    assert package == before
    assert "Insufficient evidence is not a failed skill" in provider.calls[0][0]
    assert "Do not treat null margins as zero" in provider.calls[1][0]


def test_exit_only_record_cannot_establish_economic_decision_quality():
    package, candidate = coaching_fixture()
    package["offer_history"] = []
    candidate["cards"][0].update(
        assessment="observed",
        observation="Завершение переговоров экономически оправдано, поскольку ни одно предложение не достигло минимально приемлемого порога.",
    )
    # Reproduce the live failure even if the model grounder would approve it.
    provider = Provider([candidate, {"safe": True}])
    assert generate_coaching(provider, package, lambda text: text)["status"] == "unavailable"
    assert len(provider.calls) == 1


def test_owner_review_and_new_render_plans_use_methodology_without_active_leak(client):
    session = create(client)
    url = f"/api/v1/sessions/{session['session_id']}"
    token = bearer(session["participant_token"])
    assert "methodology" not in json.dumps(session)
    assert client.get(url + "/review", headers=token).status_code == 409
    session = send(client, session, "Нам важно успеть к запуску. Какие ограничения у вас?", "interest")
    service = client.app.state.service
    with service.database.read_connection() as connection:
        jobs = connection.execute("SELECT plan_json FROM npc_render_jobs WHERE session_id = ?", (session["session_id"],)).fetchall()
    assert jobs and all(json.loads(row[0])["request"]["methodology_version"] == VERSION for row in jobs)
    session = send(client, session, "Прекращаю переговоры.", "exit-methods")
    assert client.get(url + "/review").status_code in {401, 403}
    report = client.get(url + "/review", headers=token).json()
    expected = assess_economics(report["outcome"], report["training"]["economic_baseline"])
    assert report["training"]["methodology"] == expected
    assert set(report["outcome"].get("participant_utilities", {})) <= {"buyer"}
    assert "npc_reservation" not in json.dumps(report)


def test_method_name_is_not_a_social_event():
    message = "Я применяю Voss, Harvard и тактическую эмпатию."
    provider = Provider([{"events": [{"kind": "tactical_empathy", "quote": message}]}])
    assert classify_social(provider, message, [], {}) == []
