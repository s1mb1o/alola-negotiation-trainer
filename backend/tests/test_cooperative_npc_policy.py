"""Cooperative counterproposals retain authored economics and session compatibility."""

from copy import deepcopy
import json

from fastapi.testclient import TestClient
import pytest
import yaml

from backend.app.main import create_app
from backend.app.negotiation_policy import COOPERATIVE_POLICY_VERSION, select_counterproposal
from backend.app.scenarios import (
    authored_opening, constraint_violations, evaluate_utility, validate_terms,
)
from backend.app.supply_language import _completion, _eligible, decide_supply_action
from .conftest import PROJECT_ROOT, bearer, create_payload


def scenario(filename):
    return yaml.safe_load((PROJECT_ROOT / "examples" / filename).read_text())["scenario"]


def state(client, session):
    with client.app.state.database.read_connection() as connection:
        return json.loads(connection.execute(
            "SELECT state_json FROM sessions WHERE id = ?", (session["session_id"],),
        ).fetchone()[0])


def send(client, session, message):
    response = client.post(f"/api/v1/sessions/{session['session_id']}/messages",
                          headers=bearer(session["participant_token"]), json={
                              "message": message, "expected_revision": session["revision"],
                              "idempotency_key": "cooperative-turn",
                          })
    assert response.status_code == 200, response.text
    return response.json()


def distance(source, terms, received):
    return sum(abs(value - received[term]) / (
        source["terms"]["definitions"][term]["value_schema"]["maximum"]
        - source["terms"]["definitions"][term]["value_schema"]["minimum"]
    ) for term, value in terms.items())


@pytest.mark.parametrize("filename", [
    "scenario_supplier_001_v6.yaml",
    "scenario_office_lease_ru_v4.yaml", "scenario_office_lease_en_v4.yaml",
    "scenario_saas_subscription_ru_v3.yaml", "scenario_saas_subscription_en_v3.yaml",
    "scenario_freight_contract_ru_v4.yaml", "scenario_freight_contract_en_v3.yaml",
])
@pytest.mark.parametrize("role", ["buyer", "seller"])
def test_cooperative_packages_are_closer_safe_and_private_model_independent(filename, role):
    source = scenario(filename)
    opening = authored_opening(source)[2]
    received = {term: definition["value_schema"]["minimum" if role == "seller" else "maximum"]
                for term, definition in source["terms"]["definitions"].items()}
    before = deepcopy(received)
    previous = select_counterproposal(source, role, received, opening)
    result = select_counterproposal(source, role, received, opening, cooperative=True)
    assert result is not None
    assert not validate_terms(source, result.terms, complete=True)
    assert all(not constraint_violations(source, actor, result.terms) for actor in source["roles"])
    assert evaluate_utility(source, role, result.terms) >= source["utility_model"]["role_models"][role]["reservation_utility"]
    if previous:
        assert distance(source, result.terms, received) <= distance(source, previous.terms, received)
    other = "seller" if role == "buyer" else "buyer"
    source["utility_model"]["role_models"][other] = {"must_not_read": object()}
    source["roles"][other]["brief"] = {"must_not_read": object()}
    source["roles"][other]["batna"] = {"must_not_read": object()}
    assert select_counterproposal(source, role, received, opening, cooperative=True) == result
    assert received == before


@pytest.mark.parametrize("role", ["buyer", "seller"])
def test_cooperative_price_concessions_do_not_reverse(role):
    source = scenario("scenario_supplier_001_v6.yaml")
    opening = authored_opening(source)[2]
    previous = {"price": 115000 if role == "seller" else 105000,
                "prepayment_fraction": 0.5, "delivery_weeks": 4}
    for price in (103000, 105000, 108000, 112000, 115000):
        received = {"price": price, "prepayment_fraction": 0 if role == "seller" else 1,
                    "delivery_weeks": 2 if role == "seller" else 8}
        result = select_counterproposal(source, role, received, opening, previous, cooperative=True)
        if result:
            assert (result.terms["price"] <= previous["price"]) if role == "seller" else (result.terms["price"] >= previous["price"])
            baseline = {**received, "price": result.terms["price"]}
            for term in result.trade_term_ids:
                assert evaluate_utility(source, role, {**baseline, term: result.terms[term]}) > evaluate_utility(source, role, baseline)
            previous = result.terms


def test_cooperation_cannot_complete_missing_terms_or_cross_economic_limits():
    source = scenario("scenario_supplier_001_v6.yaml")
    opening = authored_opening(source)[2]
    assert select_counterproposal(source, "seller", {"price": 103000}, opening, cooperative=True) is None
    received = {"price": 103000, "prepayment_fraction": 0, "delivery_weeks": 2}
    source["utility_model"]["role_models"]["seller"]["reservation_utility"] = 101
    assert select_counterproposal(source, "seller", received, opening, cooperative=True) is None
    source = scenario("scenario_supplier_001_v6.yaml")
    source["hard_constraints"][0]["expression"]["right"]["const"] = 102000
    assert select_counterproposal(source, "seller", received, opening, cooperative=True) is None


@pytest.mark.parametrize("language", ["ru", "en"])
def test_supply_discount_is_earlier_but_safe_and_never_fills_delivered_terms(language):
    source = scenario(f"scenario_supplier_integration_{language}.yaml")
    opening = authored_opening(source)[2]
    message = "Можно снизить цену?" if language == "ru" else "Can you reduce the price?"
    previous = decide_supply_action(source, "seller", opening, message, language)
    result = decide_supply_action(source, "seller", opening, message, language, cooperative=True)
    assert previous.terms["base_price"]["minor_units"] == 11500000
    assert result.terms["base_price"]["minor_units"] == 11100000
    assert result.action == "propose"
    assert set(result.terms) == set(opening)
    assert _eligible(source, "seller", _completion(source, result.terms))
    again = decide_supply_action(source, "seller", result.terms, message, language, cooperative=True)
    assert again.action == "inform" and again.terms is None
    source["utility_model"]["role_models"]["seller"]["reservation_utility"] = 10000
    impossible = decide_supply_action(source, "seller", opening, message, language, cooperative=True)
    assert impossible.action == "inform" and impossible.terms is None


@pytest.mark.parametrize("language", ["ru", "en"])
def test_player_api_gives_price_only_compromise_without_unnecessary_secondary_demands(client, language):
    payload = create_payload("cooperative-office-" + language, language=language)
    payload.update(scenario_id=f"office_lease_{language}", scenario_version=4)
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 201
    session = response.json()
    assert state(client, session)["npc_policy_version"] == COOPERATIVE_POLICY_VERSION
    reply = send(client, session,
                 "Предлагаю годовую аренду 1800000 рублей, предоплату 0% и готовность офиса через 1 неделю."
                 if language == "ru" else
                 "I offer annual rent of 1800000 RUB, prepayment 0%, and office readiness in 1 week.")
    terms = reply["observation"]["active_offers"][0]["terms"]
    assert terms == {"annual_rent": 2100000, "prepayment_fraction": 0, "office_readiness_weeks": 1}
    assert reply["status"] == "active"
    text = json.dumps(reply)
    assert "npc_policy_version" not in text and "reservation_utility" not in text


@pytest.mark.parametrize("mode", ["benchmark", "external_agent"])
def test_nonhuman_and_benchmark_sessions_keep_legacy_policy(client, mode):
    payload = create_payload("policy-" + mode)
    if mode == "benchmark":
        payload.update(run_mode="benchmark", hints_enabled=False, benchmark_run_id="policy-run",
                       trial_id="policy-trial", benchmark_expected_trials=1)
    else:
        payload["participants"][0]["controller"] = "external_agent"
    response = client.post("/api/v1/sessions", json=payload,
                           headers=bearer("test-admin") if mode == "benchmark" else {})
    assert response.status_code == 201, response.text
    assert "npc_policy_version" not in state(client, response.json())


@pytest.mark.parametrize("historical", [False, True])
def test_restart_and_fork_preserve_policy_from_checkpoint(client, settings, historical):
    payload = create_payload("policy-persistence")
    payload.update(scenario_id="office_lease_ru", scenario_version=4, training={})
    session = client.post("/api/v1/sessions", json=payload).json()
    if historical:
        # Model a pre-DR-57 session before its next checkpoint is written.
        old_state = state(client, session)
        old_state.pop("npc_policy_version")
        with client.app.state.database.write_transaction() as connection:
            connection.execute("UPDATE sessions SET state_json = ? WHERE id = ?",
                               (json.dumps(old_state), session["session_id"]))
    updated = send(client, session, "Какие ваши приоритеты?")
    checkpoint_revision = updated["revision"]
    session["revision"] = checkpoint_revision
    # Use a different key from the first turn.
    response = client.post(f"/api/v1/sessions/{session['session_id']}/messages",
                           headers=bearer(session["participant_token"]), json={
                               "message": "Прекращаю переговоры.", "expected_revision": checkpoint_revision,
                               "idempotency_key": "cooperative-stop",
                           })
    assert response.status_code == 200
    with TestClient(create_app(settings)) as restarted:
        child = restarted.post(f"/api/v1/sessions/{session['session_id']}/fork",
                               headers=bearer(session["participant_token"]),
                               json={"source_revision": checkpoint_revision, "idempotency_key": "policy-fork"})
        assert child.status_code == 201, child.text
        expected = None if historical else COOPERATIVE_POLICY_VERSION
        assert state(restarted, child.json()).get("npc_policy_version") == expected
        reply = send(restarted, child.json(), "Предлагаю годовую аренду 1800000 рублей, предоплату 0% и готовность офиса через 1 неделю.")
        terms = reply["observation"]["active_offers"][0]["terms"]
        source = scenario("scenario_office_lease_ru_v4.yaml")
        expected_terms = select_counterproposal(source, "seller",
            {"annual_rent": 1800000, "prepayment_fraction": 0, "office_readiness_weeks": 1},
            authored_opening(source)[2], cooperative=not historical).terms
        assert terms == expected_terms
