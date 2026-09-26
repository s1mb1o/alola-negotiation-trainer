from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from backend.app.coaching import generate_coaching
from backend.app.dialogue import template_dialogue_result, build_safe_render_input
from backend.app.training import (
    TrainingSetup,
    apply_social,
    classify_social,
    initialize_training,
    training_observation,
)
from .conftest import bearer, create_payload


class Provider:
    provider = "fixture"
    model = "fixture-v1"

    def __init__(self, values, database=None):
        self.values = iter(values)
        self.calls = []
        self.database = database

    def generate(self, messages, *, instructions):
        if self.database:
            # A separate writer can start: the model call holds no write transaction.
            with self.database.write_transaction() as connection:
                connection.execute("SELECT 1")
        self.calls.append((instructions, messages))
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(text=json.dumps(value, ensure_ascii=False))


def create(client, key="training", **setup):
    payload = create_payload(key)
    payload["training"] = {"relationship": "successful_history", "personal_detail": True,
        "shared_background": "Мы успешно работали вместе.",
        "preparation": {"target": "PRIVATE-GOAL", "targets": [{"term_id": "price", "operator": "lte", "value": 1200000}]},
        **setup}
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def send(client, session, text, key):
    response = client.post(f"/api/v1/sessions/{session['session_id']}/messages", headers=bearer(session["participant_token"]),
        json={"message": text, "expected_revision": session["revision"], "idempotency_key": key})
    assert response.status_code == 200, response.text
    return {**session, **response.json()}


def test_private_preparation_social_once_and_renderer_context(client):
    session = create(client)
    service = client.app.state.service
    requests = []
    class Renderer:
        def render(self, request):
            requests.append(request)
            return template_dialogue_result(request)
    service.dialogue_renderer = Renderer()
    service.social_provider = Provider([{"events": [{"kind": "personal_interest", "quote": "Как зовут собаку?"}]}], service.database)
    after = send(client, session, "Как зовут собаку?", "dog")
    repeated = send(client, session, "Как зовут собаку?", "dog")
    assert after["revision"] == repeated["revision"]
    assert len(service.social_provider.calls) == 1
    assert requests and "Гуффи" in requests[0].training_context["personal_fact"]
    assert "PRIVATE-GOAL" not in build_safe_render_input(requests[0])
    assert "PRIVATE-GOAL" not in str(service.social_provider.calls)
    admin = client.get(f"/api/v1/admin/sessions/{session['session_id']}", headers=bearer("test-admin")).json()
    assert "PRIVATE-GOAL" not in json.dumps(admin)
    with service.database.read_connection() as connection:
        state = json.loads(connection.execute("SELECT state_json FROM sessions WHERE id = ?", (session["session_id"],)).fetchone()[0])
    assert state["training"]["social"]["rapport"] == 58
    social_state = after["observation"]["training"]["social_state"]
    assert social_state == {
        "values": {"rapport": 58, "credibility": 70, "tension": 10, "patience": 80},
        "delta": {"rapport": 3, "credibility": 0, "tension": 0, "patience": 0},
        "source_revision": 1,
    }
    assert repeated["observation"]["training"]["social_state"] == social_state


def test_target_validation_and_benchmark_gate(client):
    payload = create_payload("bad-target")
    payload["training"] = {"preparation": {"targets": [{"term_id": "hidden_budget", "value": 10}]}}
    assert client.post("/api/v1/sessions", json=payload).status_code == 422
    payload.update(run_mode="benchmark", difficulty="normal", hints_enabled=False,
                   benchmark_run_id="b", trial_id="t", benchmark_expected_trials=1)
    assert client.post("/api/v1/sessions", json=payload).status_code == 422
    payload = create_payload("external", both_external=True)
    payload["training"] = {}
    assert client.post("/api/v1/sessions", json=payload).status_code == 422


def test_coaching_gates_cache_failure_and_restart(client, settings):
    session = create(client)
    url = f"/api/v1/sessions/{session['session_id']}"
    service = client.app.state.service
    service.review_provider = Provider([RuntimeError("secret provider error")], service.database)
    assert client.post(url + "/coaching", headers=bearer(session["participant_token"])).status_code == 409
    assert not service.review_provider.calls
    session = send(client, session, "Прекращаю переговоры.", "exit")
    response = client.post(url + "/coaching", headers=bearer(session["participant_token"]))
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert "secret" not in response.text
    client.post(url + "/coaching", headers=bearer(session["participant_token"]))
    assert len(service.review_provider.calls) == 1
    report = client.get(url + "/review", headers=bearer(session["participant_token"])).json()
    assert report["outcome"]["agreement"] is False
    assert "detail" not in report["key_moments"][0]
    assert report["training"]["goal_comparison"][0]["status"] == "unknown"
    from backend.app.main import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(settings)) as restarted:
        assert restarted.post(url + "/coaching", headers=bearer(session["participant_token"])).json()["status"] == "unavailable"


def test_review_grounding_exact_evidence_and_no_write_lock(client):
    session = create(client)
    session = send(client, session, "Прекращаю переговоры.", "exit")
    url = f"/api/v1/sessions/{session['session_id']}"
    report = client.get(url + "/review", headers=bearer(session["participant_token"])).json()
    source = report["training"]["evidence"][-1]
    candidate = {"summary": "Сделка не заключена.", "goal_assessment": "Цель не достигнута.",
                 "cards": [{"evidence_refs": [source["ref"]], "observation": "Вы завершили переговоры.",
                            "recommendation": "Перед выходом проверьте альтернативу.",
                            "alternative_phrase": "Какое условие для вас важнее всего?",
                            "next_practice": "Задайте вопрос об интересах до выхода."}]}
    service = client.app.state.service
    service.review_provider = Provider([candidate, {"safe": True}], service.database)
    response = client.post(url + "/coaching", headers=bearer(session["participant_token"])).json()
    assert response["status"] == "complete"
    assert response["cards"][0]["evidence"] == [source]
    assert len(service.review_provider.calls) == 2
    assert "PRIVATE-GOAL" in service.review_provider.calls[0][1][0]["content"]
    candidate["cards"][0]["evidence_refs"] = ["invented"]
    assert generate_coaching(Provider([candidate]), {"revision": 1, "evidence": [source]}, lambda x: x)["status"] == "unavailable"


def test_fork_exact_checkpoint_fresh_auth_history_and_comparison(client):
    session = create(client)
    first_id, old_token = session["session_id"], session["participant_token"]
    session = send(client, session, "Здравствуйте!", "hello")
    checkpoint_revision = session["revision"]
    before = client.get(f"/api/v1/sessions/{first_id}", headers=bearer(old_token)).json()
    session = send(client, session, "Прекращаю переговоры.", "exit")
    terminal_rewind = client.post(
        f"/api/v1/sessions/{first_id}/rewind",
        headers=bearer(old_token),
        json={"source_revision": checkpoint_revision, "idempotency_key": "terminal-rewind"},
    )
    assert terminal_rewind.status_code == 409
    assert terminal_rewind.json()["error"] == "rewind_not_available"
    fork_body = {"source_revision": checkpoint_revision, "idempotency_key": "fork-once"}
    response = client.post(f"/api/v1/sessions/{first_id}/fork", headers=bearer(old_token), json=fork_body)
    assert response.status_code == 201, response.text
    child = response.json()
    assert child["participant_token"] != old_token
    assert child["revision"] == checkpoint_revision
    child_url = f"/api/v1/sessions/{child['session_id']}"
    assert client.get(child_url, headers=bearer(old_token)).status_code == 401
    assert client.get(f"/api/v1/sessions/{first_id}", headers=bearer(child["participant_token"])).status_code == 401
    assert [m["message"] for m in child["observation"]["conversation"]] == [m["message"] for m in before["observation"]["conversation"]]
    assert child["observation"]["training"] == before["observation"]["training"]
    again = client.post(f"/api/v1/sessions/{first_id}/fork", headers=bearer(old_token), json=fork_body).json()
    assert again["session_id"] == child["session_id"] and "participant_token" not in again
    assert client.get(child_url + "/comparison", headers=bearer(child["participant_token"])).status_code == 409
    child = send(client, child, "Прекращаю переговоры.", "exit-child")
    compared = client.get(child_url + "/comparison", headers=bearer(child["participant_token"])).json()
    assert compared["informed_practice"] and compared["same_initial_conditions_at_checkpoint"]
    assert compared["utility_delta"] == 0 and compared["causal_improvement_claim"] is False
    assert "participant_utilities" not in compared["before"]


def test_active_rewind_restores_exact_checkpoint_and_enforces_lineage_limit(client):
    session = create(client, "rewind-active")
    root_id = session["session_id"]
    root_token = session["participant_token"]
    session = send(client, session, "Здравствуйте!", "rewind-hello")
    source_revision = session["revision"]
    checkpoint = client.get(
        f"/api/v1/sessions/{root_id}", headers=bearer(root_token)
    ).json()
    session = send(client, session, "Какие условия для вас важны?", "rewind-question")

    body = {"source_revision": source_revision, "idempotency_key": "rewind-one"}
    response = client.post(
        f"/api/v1/sessions/{root_id}/rewind",
        headers=bearer(root_token),
        json=body,
    )
    assert response.status_code == 201, response.text
    child = response.json()
    assert child["revision"] == source_revision
    assert child["participant_token"] != root_token
    assert [
        {key: value for key, value in message.items() if key != "participant_id"}
        for message in child["observation"]["conversation"]
    ] == [
        {key: value for key, value in message.items() if key != "participant_id"}
        for message in checkpoint["observation"]["conversation"]
    ]
    assert [
        {
            key: value
            for key, value in offer.items()
            if key != "proposer_participant_id"
        }
        for offer in child["observation"]["active_offers"]
    ] == [
        {
            key: value
            for key, value in offer.items()
            if key != "proposer_participant_id"
        }
        for offer in checkpoint["observation"]["active_offers"]
    ]
    assert child["observation"]["training"]["social_state"] == checkpoint["observation"]["training"]["social_state"]
    assert child["observation"]["training"]["rewind"] == {
        "limit": 3,
        "used": 1,
        "remaining": 2,
        "available": True,
        "eligible_source_revisions": [0],
    }

    repeated = client.post(
        f"/api/v1/sessions/{root_id}/rewind",
        headers=bearer(root_token),
        json=body,
    ).json()
    assert repeated["session_id"] == child["session_id"]
    assert "participant_token" not in repeated
    root_status = client.get(
        f"/api/v1/sessions/{root_id}", headers=bearer(root_token)
    ).json()["observation"]["training"]["rewind"]
    assert root_status["used"] == 1

    second = client.post(
        f"/api/v1/sessions/{child['session_id']}/rewind",
        headers=bearer(child["participant_token"]),
        json={"source_revision": 0, "idempotency_key": "rewind-two"},
    ).json()
    assert second["observation"]["training"]["rewind"]["used"] == 2
    current = client.post(
        f"/api/v1/sessions/{root_id}/rewind",
        headers=bearer(root_token),
        json={"source_revision": source_revision, "idempotency_key": "rewind-three"},
    ).json()
    assert current["observation"]["training"]["rewind"]["used"] == 3
    exhausted = client.post(
        f"/api/v1/sessions/{current['session_id']}/rewind",
        headers=bearer(current["participant_token"]),
        json={"source_revision": 0, "idempotency_key": "rewind-four"},
    )
    assert exhausted.status_code == 409
    assert exhausted.json()["error"] == "rewind_limit_exhausted"


def test_player_assist_is_read_only_actor_safe_and_idempotent(client):
    session = create(client, "player-assist")
    service = client.app.state.service
    service.player_assist_provider = Provider(
        [{"message": "Какие условия для вас наиболее важны?"}],
        service.database,
    )
    url = f"/api/v1/sessions/{session['session_id']}"
    request = {
        "expected_revision": session["revision"],
        "idempotency_key": "assist-once",
    }

    response = client.post(
        url + "/player-assist",
        headers=bearer(session["participant_token"]),
        json=request,
    )
    assert response.status_code == 200, response.text
    assisted = response.json()
    assert assisted["message"] == "Какие условия для вас наиболее важны?"
    unchanged = client.get(url, headers=bearer(session["participant_token"])).json()
    assert unchanged["revision"] == session["revision"]
    assert unchanged["observation"]["conversation"] == session["observation"]["conversation"]
    assert len(service.player_assist_provider.calls) == 1
    instructions, messages = service.player_assist_provider.calls[0]
    assert "PRIVATE-GOAL" in messages[0]["content"]
    assert "untrusted task data" in instructions

    repeated = client.post(
        url + "/player-assist",
        headers=bearer(session["participant_token"]),
        json=request,
    ).json()
    assert repeated == assisted
    assert len(service.player_assist_provider.calls) == 1

    sent = send(client, session, assisted["message"], "assist-send")
    assert sent["revision"] > session["revision"]


def test_player_assist_rejects_binding_control_without_state_change(client):
    session = create(client, "player-assist-binding")
    service = client.app.state.service
    service.player_assist_provider = Provider([
        {"message": "Подтверждаю принятие полного предложения без дополнительных условий."}
    ])
    url = f"/api/v1/sessions/{session['session_id']}"
    response = client.post(
        url + "/player-assist",
        headers=bearer(session["participant_token"]),
        json={"expected_revision": session["revision"], "idempotency_key": "assist-binding"},
    )
    assert response.status_code == 503
    assert response.json()["error"] == "player_assist_unavailable"
    unchanged = client.get(url, headers=bearer(session["participant_token"])).json()
    assert unchanged["revision"] == session["revision"]


def test_social_schema_evidence_bounds_and_farming():
    setup = TrainingSetup(personal_detail=True)
    training = initialize_training(setup, "owner", {"terms": {"definitions": {}}}, lambda x: x)
    for revision in range(1, 60):
        apply_social(training, revision, [{"kind": "personal_interest", "quote": "dog"}])
    assert training["social"]["rapport"] == 51
    for revision in range(60, 160):
        apply_social(training, revision, [{"kind": "direct_insult", "quote": "insult"}])
    assert all(0 <= value <= 100 for value in training["social"].values())
    previous = dict(training["social"])
    assert apply_social(training, 159, [{"kind": "apology", "quote": "sorry"}]) == []
    assert training["social"] == previous
    provider = Provider([{"events": [{"kind": "direct_insult", "quote": "invented"}]}])
    assert classify_social(provider, "Мне не подходит цена", [], {}) == []
    provider = Provider([{"events": [{"kind": "admitted_deception", "quote": "Ты соврал"}]}])
    assert classify_social(provider, "Ты соврал", [], {}) == []


def test_social_projection_is_owner_only_and_tracks_latest_committed_delta():
    training = initialize_training(
        TrainingSetup(),
        "owner",
        {"terms": {"definitions": {}}},
        lambda value: value,
    )
    initial = training_observation(training, "owner")["social_state"]
    assert initial["values"] == {"rapport": 45, "credibility": 60, "tension": 10, "patience": 80}
    assert initial["delta"] == {"rapport": 0, "credibility": 0, "tension": 0, "patience": 0}
    assert "social_state" not in training_observation(training, "other")

    apply_social(training, 3, [
        {"kind": "direct_insult", "quote": "insult"},
        {"kind": "repetition", "quote": "again"},
    ])
    changed = training_observation(training, "owner")["social_state"]
    assert changed["values"] == {"rapport": 39, "credibility": 60, "tension": 18, "patience": 73}
    assert changed["delta"] == {"rapport": -6, "credibility": 0, "tension": 8, "patience": -7}
    assert changed["source_revision"] == 3

    apply_social(training, 4, [])
    unchanged = training_observation(training, "owner")["social_state"]
    assert unchanged["values"] == changed["values"]
    assert unchanged["delta"] == {"rapport": 0, "credibility": 0, "tension": 0, "patience": 0}
    assert unchanged["source_revision"] == 4

    assert apply_social(training, 4, [{"kind": "personal_interest", "quote": "dog"}]) == []
    assert training_observation(training, "owner")["social_state"] == unchanged


def test_completed_targets_and_pending_confirmation_survive_fork(client, settings):
    session = create(client)
    session = send(client, session, "Предлагаю цену 1 000 000 рублей, предоплату 0% и доставку 2 недели.", "low-offer")
    session = send(client, session, "Принимаю все условия предложения.", "accept")
    pending_revision = session["revision"]
    expected_terms = session["pending_confirmation"]["terms"]
    session = send(client, session, "Подтверждаю принятие полного предложения.", "confirm")
    assert session["status"] == "agreement_reached"
    url = f"/api/v1/sessions/{session['session_id']}"
    review = client.get(url + "/review", headers=bearer(session["participant_token"])).json()
    goal = review["training"]["goal_comparison"][0]
    assert goal["actual"] == expected_terms["price"]
    assert goal["gap"] == max(0, expected_terms["price"] - 1200000)
    from backend.app.main import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(settings)) as restarted:
        child = restarted.post(url + "/fork", headers=bearer(session["participant_token"]),
            json={"source_revision": pending_revision, "idempotency_key": "fork-confirm"}).json()
        assert child["pending_confirmation"]["terms"] == expected_terms
        confirmed = send(restarted, child, "Подтверждаю принятие полного предложения.", "confirm-child")
        assert confirmed["status"] == "agreement_reached"


def test_supply_fork_remaps_source_events_and_keeps_package(client):
    payload = create_payload("supply-training")
    payload.update(scenario_id="supplier_integration_ru", training={})
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 201
    session = response.json()
    original = session["observation"]["preliminary_proposals"][0]
    session = send(client, session, "Прекращаю переговоры.", "stop")
    child = client.post(f"/api/v1/sessions/{session['session_id']}/fork", headers=bearer(session["participant_token"]),
                       json={"source_revision": 0, "idempotency_key": "fork-supply"}).json()
    proposal = child["observation"]["preliminary_proposals"][0]
    assert proposal["terms"] == original["terms"]
    assert proposal["source_event_ids"] != original["source_event_ids"]
    events = client.get(f"/api/v1/sessions/{child['session_id']}/events", headers=bearer(child["participant_token"])).json()["events"]
    assert set(proposal["source_event_ids"]) <= {event["event_id"] for event in events}


@pytest.mark.parametrize("verdict", [{"safe": False}, {"safe": 1}, {"safe": "true"}])
def test_coaching_requires_boolean_grounding_verdict(verdict):
    candidate = {"summary": "Итог", "goal_assessment": "Цель", "cards": [{
        "evidence_refs": ["message:1"], "observation": "Факт", "recommendation": "Совет",
        "alternative_phrase": "Вопрос", "next_practice": "Практика"}]}
    result = generate_coaching(Provider([candidate, verdict]), {"revision": 1, "evidence": [{"ref": "message:1"}]}, lambda x: x)
    assert result["status"] == "unavailable"
