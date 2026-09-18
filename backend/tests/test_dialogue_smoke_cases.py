"""Offline contract tests for the versioned DR-28 smoke case inventory."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.app.dialogue import TemplateNpcDialogueRenderer
from backend.app.main import create_app
from backend.dialogue_smoke_cases import DIFFICULTIES, SmokeStep, evaluate_step, grounded_cases


@pytest.mark.parametrize("language", ["ru", "en"])
def test_case_inventory_is_bounded_pinned_and_independent(language):
    cases = grounded_cases(language)
    assert 1 <= len(cases) <= 3
    assert len({case.case_id for case in cases}) == len(cases)
    assert all(1 <= len(case.steps) <= 8 for case in cases)
    assert all(len({step.step_id for step in case.steps}) == len(case.steps) for case in cases)
    assert {(case.scenario_id, case.scenario_version) for case in cases} == {
        ("supplier_001", 5) if language == "ru" else ("office_lease_en", 4)
    }
    assert any(step.quote_requested for case in cases for step in case.steps)
    for case in cases:
        for step in case.steps:
            if step.expected_terms:
                step.expected_terms["test_mutation"] = 1
    assert all(
        "test_mutation" not in (step.expected_terms or {})
        for case in grounded_cases(language)
        for step in case.steps
    )


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
@pytest.mark.parametrize(
    "case",
    [case for language in ("ru", "en") for case in grounded_cases(language)],
    ids=lambda case: case.language + "-" + case.case_id,
)
def test_every_case_passes_public_api_with_template_renderer(settings, difficulty, case):
    with TestClient(
        create_app(settings, npc_dialogue_renderer=TemplateNpcDialogueRenderer())
    ) as client:
        created = client.post(
            "/api/v1/sessions",
            json={
                "idempotency_key": f"case-{case.language}-{case.case_id}-{difficulty}",
                "scenario_id": case.scenario_id,
                "scenario_version": case.scenario_version,
                "language": case.language,
                "difficulty": difficulty,
                "run_mode": "training",
                "hints_enabled": False,
                "participants": [
                    {"role": "buyer", "controller": "human"},
                    {"role": "seller", "controller": "built_in_npc"},
                ],
            },
        )
        assert created.status_code == 201, created.text
        state = created.json()
        session_id = state["session_id"]
        participant_id = state["observation"]["participant_id"]
        headers = {"Authorization": f"Bearer {state['participant_token']}"}
        url = f"/api/v1/sessions/{session_id}"
        previous_ids = {
            event["event_id"]
            for event in client.get(url + "/events", headers=headers).json()["events"]
        }
        for step in case.steps:
            before = deepcopy(state)
            response = client.post(
                url + "/messages",
                headers=headers,
                json={
                    "message": step.message,
                    "expected_revision": state["revision"],
                    "idempotency_key": step.step_id,
                },
            )
            assert response.status_code == 200, (step.step_id, response.text)
            state = response.json()
            public = client.get(url + "/events", headers=headers)
            assert public.status_code == 200
            events = public.json()["events"]
            added = [event for event in events if event["event_id"] not in previous_ids]
            previous_ids.update(event["event_id"] for event in added)
            checks = evaluate_step(step, before, state, added, participant_id)
            assert all(checks.values()), (step.step_id, checks, state, added)
            assert state["observation"]["hints"] == []


def test_player_offer_check_does_not_confuse_later_npc_counteroffer():
    step = SmokeStep("relative", "Reduce the price by 5%.", "relative_offer", {"price": 104500})
    before = {
        "status": "active",
        "active_offers": [{"offer_id": "first", "offer_revision": 2, "terms": {"price": 110000}}],
    }
    after = {
        "status": "active",
        "active_offers": [{"offer_id": "first", "offer_revision": 4, "terms": {"price": 108000}}],
    }
    events = [
        {
            "type": "offer.countered",
            "participant_id": "player",
            "payload": {
                "offer_id": "first",
                "offer_revision": 3,
                "terms": {"price": 104500},
                "unresolved_required_terms": ["delivery_weeks"],
            },
        },
        {
            "type": "offer.countered",
            "participant_id": "npc",
            "payload": {
                "offer_id": "first",
                "offer_revision": 4,
                "terms": {"price": 108000},
                "unresolved_required_terms": ["delivery_weeks"],
            },
        },
    ]
    assert all(evaluate_step(step, before, after, events, "player").values())
    assert not evaluate_step(step, before, after, events, "other")["one_player_offer_committed"]
    events[0]["payload"]["offer_id"] = "another_session_offer"
    assert not evaluate_step(step, before, after, events, "player")[
        "active_baseline_revision_advanced"
    ]


def test_numeric_question_cannot_pass_if_npc_changes_offer_or_reaches_agreement():
    step = SmokeStep("question", "Why is the price EUR 120,000?", "numeric_question")
    before = {"status": "active", "active_offers": [{"terms": {"price": 120000}}]}
    after = {"status": "agreement_reached", "active_offers": [{"terms": {"price": 115000}}]}
    events = [{"type": "agreement.reached", "participant_id": "npc", "payload": {}}]
    checks = evaluate_step(step, before, after, events, "player")
    assert not checks["session_active"]
    assert not checks["no_binding_agreement"]
    assert not checks["active_offers_unchanged"]


def test_evaluator_does_not_invent_quote_coverage():
    step = SmokeStep("question", "Why?", "numeric_question", quote_requested=True)
    checks = evaluate_step(step, {}, {}, [], "player")
    assert not any("quote" in name for name in checks)


@pytest.mark.parametrize(
    "after,events",
    [
        ({"status": "active", "result": "confirmation_required"}, []),
        ({"status": "active", "pending_confirmation": {"offer_id": "offer"}}, []),
        ({"status": "active"}, [{"type": "acceptance.confirmation_required"}]),
    ],
)
def test_false_agreement_check_rejects_each_public_confirmation_signal(after, events):
    step = SmokeStep("claim", "Does that mean we have agreed?", "false_agreement")
    assert not evaluate_step(step, {}, after, events, "player")["no_acceptance_confirmation"]


def test_unknown_language_or_check_kind_fails_explicitly():
    with pytest.raises(ValueError):
        grounded_cases("fr")
    with pytest.raises(ValueError):
        evaluate_step(SmokeStep("x", "x", "typo"), {}, {}, [], "player")
