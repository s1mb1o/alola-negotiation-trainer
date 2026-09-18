from __future__ import annotations

from copy import deepcopy
from itertools import product
import pytest
import yaml
from fastapi.testclient import TestClient

from backend.app.negotiation_policy import select_counterproposal
from backend.app.scenarios import (
    authored_opening, constraint_violations, evaluate_utility, validate_terms,
)

from .conftest import PROJECT_ROOT, bearer, create_payload, credentials


def _scenario(filename: str = "scenario_supplier_001_v5.yaml") -> dict:
    return yaml.safe_load((PROJECT_ROOT / "examples" / filename).read_text())["scenario"]


@pytest.mark.parametrize("npc_role", ["buyer", "seller"])
def test_exchange_concedes_money_for_conditions_with_demonstrable_npc_benefit(npc_role: str) -> None:
    scenario = _scenario()
    opening = authored_opening(scenario)[2]
    if npc_role == "seller":
        received = {"price": 103000, "prepayment_fraction": 0, "delivery_weeks": 2}
        previous = {"price": 115000, "prepayment_fraction": 0.5, "delivery_weeks": 6}
    else:
        received = {"price": 115000, "prepayment_fraction": 1, "delivery_weeks": 8}
        previous = {"price": 105000, "prepayment_fraction": 0, "delivery_weeks": 2}
    result = select_counterproposal(scenario, npc_role, received, opening, previous)
    assert result is not None
    assert result.reason_code == "conditional_exchange"
    assert result.monetary_term_id == "price"
    assert result.trade_term_ids
    assert not validate_terms(scenario, result.terms, complete=True)
    assert all(not constraint_violations(scenario, role, result.terms) for role in scenario["roles"])
    assert evaluate_utility(scenario, npc_role, result.terms) >= 40
    assert (result.terms["price"] < previous["price"]) if npc_role == "seller" else (result.terms["price"] > previous["price"])
    baseline = {**received, "price": result.terms["price"]}
    for term in result.trade_term_ids:
        condition = {**baseline, term: result.terms[term]}
        assert evaluate_utility(scenario, npc_role, condition) > evaluate_utility(scenario, npc_role, baseline)
    assert set(result.__dataclass_fields__) == {"terms", "reason_code", "monetary_term_id", "trade_term_ids"}


@pytest.mark.parametrize("role", ["buyer", "seller"])
def test_policy_does_not_read_counterpart_private_utility_or_batna(role: str) -> None:
    scenario = _scenario()
    opening = authored_opening(scenario)[2]
    received = {"price": 108000, "prepayment_fraction": 0.25, "delivery_weeks": 4}
    original = select_counterproposal(scenario, role, received, opening)
    counterpart = "buyer" if role == "seller" else "seller"
    scenario["utility_model"]["role_models"][counterpart] = {"this_private_model_must_not_be_read": True}
    scenario["roles"][counterpart]["batna"] = {"private_canary": object()}
    scenario["roles"][counterpart]["brief"] = {"private_canary": object()}
    assert select_counterproposal(scenario, role, received, opening) == original


@pytest.mark.parametrize("received", [{"price": 105000}, {"price": 105000, "delivery_weeks": 2}])
def test_policy_never_completes_an_incomplete_proposal(received: dict) -> None:
    scenario = _scenario()
    before = deepcopy(received)
    assert select_counterproposal(scenario, "seller", received, authored_opening(scenario)[2]) is None
    assert received == before


def test_crossed_hard_limits_and_unreachable_npc_reservation_have_no_counterproposal() -> None:
    scenario = _scenario()
    received = {"price": 105000, "prepayment_fraction": 0, "delivery_weeks": 2}
    scenario["hard_constraints"][0]["expression"]["right"]["const"] = 102000
    assert select_counterproposal(scenario, "seller", received, {"price": 120000}) is None
    scenario = _scenario()
    scenario["utility_model"]["role_models"]["seller"]["reservation_utility"] = 101
    assert select_counterproposal(scenario, "seller", received, {"price": 120000}) is None


@pytest.mark.parametrize("role", ["buyer", "seller"])
def test_each_counter_preserves_the_previous_public_monetary_concession(role: str) -> None:
    scenario = _scenario()
    opening = authored_opening(scenario)[2]
    previous = {"price": 115000 if role == "seller" else 105000, "prepayment_fraction": 0.5, "delivery_weeks": 4}
    for price in (103000, 105000, 108000, 112000, 115000):
        received = {"price": price, "prepayment_fraction": 0 if role == "seller" else 1, "delivery_weeks": 2 if role == "seller" else 8}
        result = select_counterproposal(scenario, role, received, opening, previous)
        if result is not None:
            assert (result.terms["price"] <= previous["price"]) if role == "seller" else (result.terms["price"] >= previous["price"])
            previous = result.terms


@pytest.mark.parametrize("filename", [
    "scenario_supplier_001_v5.yaml", "scenario_office_lease_ru_v4.yaml", "scenario_office_lease_en_v4.yaml",
    "scenario_freight_contract_ru_v3.yaml", "scenario_freight_contract_en_v3.yaml",
    "scenario_saas_subscription_ru_v3.yaml", "scenario_saas_subscription_en_v3.yaml",
])
def test_new_scenario_counterpackages_pass_constraints_for_both_roles(filename: str) -> None:
    scenario = _scenario(filename)
    opening = authored_opening(scenario)[2]
    required = scenario["terms"]["required_term_ids"]
    extremes = [
        (scenario["terms"]["definitions"][term]["value_schema"]["minimum"], scenario["terms"]["definitions"][term]["value_schema"]["maximum"])
        for term in required
    ]
    for role, combination in product(scenario["roles"], product(*extremes)):
        received = dict(zip(required, combination))
        result = select_counterproposal(scenario, role, received, opening)
        if result is not None:
            assert not validate_terms(scenario, result.terms, complete=True)
            assert all(not constraint_violations(scenario, actor, result.terms) for actor in scenario["roles"])
            assert evaluate_utility(scenario, role, result.terms) >= scenario["utility_model"]["role_models"][role]["reservation_utility"]


def test_legacy_midpoint_is_validated_against_every_role_and_cannot_return_partial_opening() -> None:
    scenario = _scenario("scenario_supplier_001_v4.yaml")
    complete = {"price": 110000, "prepayment_fraction": 0.5, "delivery_weeks": 4}
    result = select_counterproposal(scenario, "seller", complete, {"price": 120000})
    assert result is not None and result.reason_code == "validated_midpoint"
    assert result.terms["price"] == 115000
    impossible = {"price": 125000, "prepayment_fraction": 0, "delivery_weeks": 1}
    assert select_counterproposal(scenario, "seller", impossible, {"price": 120000}) is None


def test_safe_previous_own_offer_is_fallback_when_no_new_exchange_is_supported() -> None:
    scenario = _scenario("scenario_supplier_001_v4.yaml")
    previous = {"price": 112000, "prepayment_fraction": 0.75, "delivery_weeks": 4}
    received = {"price": 103000, "prepayment_fraction": 0, "delivery_weeks": 1}
    result = select_counterproposal(scenario, "seller", received, {"price": 120000}, previous)
    assert result is not None and result.reason_code == "validated_own_offer"
    assert result.terms == previous


@pytest.mark.parametrize("difficulty", ["guided", "easy", "normal", "expert"])
def test_difficulty_assistance_and_role_style_do_not_change_economic_selection(difficulty: str) -> None:
    scenario = _scenario()
    received = {"price": 103000, "prepayment_fraction": 0, "delivery_weeks": 2}
    original = select_counterproposal(scenario, "seller", received, {"price": 120000})
    scenario["assistance"] = {difficulty: {"show_coaching": difficulty == "guided"}}
    scenario["roles"]["seller"]["conversation_style"] = "relationship_focused"
    assert select_counterproposal(scenario, "seller", received, {"price": 120000}) == original


@pytest.mark.parametrize(("language", "scenario_id", "version", "filename", "message", "exchange_phrase"), [
    ("ru", "supplier_001", 5, "scenario_supplier_001_v5.yaml",
     "Предлагаю цену 103000 евро, предоплату 0% и срок поставки 2 недели.", "Предлагаю обмен уступками"),
    ("en", "office_lease_en", 4, "scenario_office_lease_en_v4.yaml",
     "I offer annual rent of 1800000 RUB, prepayment 0%, and office readiness in 1 week.", "I propose a trade"),
])
def test_player_api_delivers_canonical_exchange_with_same_validated_package(
    client: TestClient, language: str, scenario_id: str, version: int,
    filename: str, message: str, exchange_phrase: str,
) -> None:
    payload = create_payload("exchange-session-" + language, language=language)
    payload.update(scenario_id=scenario_id, scenario_version=version)
    created_response = client.post("/api/v1/sessions", json=payload)
    assert created_response.status_code == 201
    created = created_response.json()
    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(credentials(created)["buyer"]),
        json={"message": message, "expected_revision": created["revision"], "idempotency_key": "exchange-message"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    npc_action = next(action for action in body["committed_actions"] if action["action"] == "counter_offer" and action.get("speech_act") == "complete_counteroffer")
    assert exchange_phrase in npc_action["message"]
    terms = body["observation"]["active_offers"][0]["terms"]
    scenario = _scenario(filename)
    assert not validate_terms(scenario, terms, complete=True)
    assert all(not constraint_violations(scenario, role, terms) for role in scenario["roles"])
    assert evaluate_utility(scenario, "seller", terms) >= scenario["utility_model"]["role_models"]["seller"]["reservation_utility"]
    assert "npc_utility" not in response.text
    assert "reservation_utility" not in response.text
