from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from backend.app.scenarios import (
    ScenarioCatalog,
    ScenarioError,
    authored_opening,
    compile_scenario,
    constraint_violations,
    evaluate_utility,
    validate_terms,
)
from backend.app.supply import (
    _devices,
    evaluate_supply_utility,
    format_supply_terms,
    is_supply_scenario,
    settle_reserve_unit,
    supply_constraint_violations,
    supply_financial_summary,
    unresolved_supply_terms,
    validate_supply_configuration,
    validate_supply_terms,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "quantity,noun",
    [
        (1, "устройство"),
        (2, "устройства"),
        (3, "устройства"),
        (4, "устройства"),
        (5, "устройств"),
        (11, "устройств"),
        (12, "устройств"),
        (14, "устройств"),
        (21, "устройство"),
        (22, "устройства"),
        (100, "устройств"),
        (111, "устройств"),
    ],
)
def test_russian_device_count_has_correct_plural(quantity, noun):
    assert _devices(quantity, "ru") == f"{quantity} {noun}"


def test_english_device_count_has_correct_plural():
    assert _devices(1, "en") == "1 device"
    assert _devices(3, "en") == "3 devices"


@pytest.fixture
def scenario():
    return yaml.safe_load((ROOT / "examples/scenario_supplier_integration_ru.yaml").read_text())[
        "scenario"
    ]


@pytest.fixture
def package():
    return {
        "base_price": {"currency": "EUR", "minor_units": 10950000},
        "delivery_lots": [
            {
                "lot_id": "early",
                "quantity": 10,
                "window_start": "2026-11-05",
                "window_end": "2026-11-07",
            },
            {
                "lot_id": "remaining",
                "quantity": 90,
                "window_start": "2026-11-20",
                "window_end": "2026-11-20",
            },
        ],
        "payment_schedule": [
            {"lot_id": "early", "advance_bps": 10000, "balance_days": 0},
            {"lot_id": "remaining", "advance_bps": 5000, "balance_days": 0},
        ],
        "delivery_basis": {"basis": "DDP", "destination_id": "vector_site"},
        "reserve_policy": {
            "mode": "contingent",
            "quantity": 3,
            "delivery_lot_id": "remaining",
            "use_cutoff": "2026-12-01",
            "unused_payable_on": "2026-12-02",
            "unit_price_rule": "base_unit_ceil",
            "diagnosis_policy_id": "hardware-replacement-v1",
        },
    }


@pytest.mark.parametrize("language", ["ru", "en"])
def test_new_scenarios_pass_schema_and_compiler(language):
    path = ROOT / f"examples/scenario_supplier_integration_{language}.yaml"
    document = yaml.safe_load(path.read_text())
    schema = json.loads((ROOT / "schemas/scenario-v1.schema.json").read_text())
    assert list(Draft202012Validator(schema).iter_errors(document)) == []
    compiled = compile_scenario(document, path)
    assert compiled.id == f"supplier_integration_{language}"
    assert compiled.public_metadata()["negotiation_contract_version"] == "supply-package-v1"
    assert "supply_model" not in compiled.public_metadata()
    role, kind, opening = authored_opening(compiled.source)
    assert (role, kind) == ("seller", "opening_position")
    assert set(opening) == {"base_price", "delivery_lots"}
    assert unresolved_supply_terms(compiled.source, opening) == [
        "payment_schedule",
        "delivery_basis",
        "reserve_policy",
    ]


def test_catalog_retains_legacy_contracts():
    entries = ScenarioCatalog(
        [ROOT / "examples"], ROOT / "schemas/scenario-v1.schema.json"
    ).discover()
    assert len([item for item in entries if is_supply_scenario(item.source)]) == 2
    old = next(item for item in entries if item.id == "supplier_001" and item.version == 5)
    assert not is_supply_scenario(old.source)
    assert authored_opening(old.source)[2] == {"price": 120000}
    assert "negotiation_contract_version" not in old.public_metadata()


def test_reference_package_is_viable_and_liability_is_separate(scenario, package):
    assert validate_supply_configuration(scenario) == []
    assert validate_supply_terms(scenario, package, complete=True) == []
    assert unresolved_supply_terms(scenario, package) == []
    assert supply_constraint_violations(scenario, "buyer", package) == []
    assert supply_constraint_violations(scenario, "seller", package) == []
    summary = supply_financial_summary(scenario, package)
    assert summary["base_price_minor"] == 10950000
    assert summary["reserve_unit_price_minor"] == 109500
    assert summary["maximum_liability_minor"] == 11278500
    assert summary["advance_minor"] == 6022500
    assert summary["weighted_advance_fraction"] == 0.55
    assert evaluate_supply_utility(scenario, "seller", package) == 40.375
    assert evaluate_supply_utility(scenario, "buyer", package) == 73.325
    assert evaluate_utility(scenario, "seller", package) == 40.375
    assert constraint_violations(scenario, "buyer", package) == []
    assert validate_terms(scenario, package, True) == []


def test_money_uses_integer_rounding_and_canonical_residual(scenario, package):
    package["base_price"]["minor_units"] = 10950005
    package["payment_schedule"][0]["advance_bps"] = 5000
    summary = supply_financial_summary(scenario, package)
    assert summary["lots"][0]["price_minor"] == 1095000
    assert summary["lots"][1]["price_minor"] == 9855005
    assert summary["lots"][1]["advance_minor"] == 4927503
    assert summary["reserve_unit_price_minor"] == 109501
    assert sum(row["price_minor"] for row in summary["lots"]) == 10950005
    assert sum(row["advance_minor"] + row["balance_minor"] for row in summary["lots"]) == 10950005
    package["delivery_lots"].reverse()
    package["payment_schedule"].reverse()
    assert supply_financial_summary(scenario, package) == summary


@pytest.mark.parametrize(
    "term", ["base_price", "payment_schedule", "delivery_basis", "reserve_policy"]
)
def test_missing_terms_never_get_complete_utility(scenario, package, term):
    del package[term]
    assert term in unresolved_supply_terms(scenario, package)
    with pytest.raises(ValueError, match="not complete"):
        evaluate_supply_utility(scenario, "buyer", package)
    with pytest.raises(ValueError, match="not complete"):
        evaluate_utility(scenario, "seller", package)


def test_nested_missing_values_and_explicit_zero(scenario, package):
    del package["payment_schedule"][1]["advance_bps"]
    del package["payment_schedule"][0]["balance_days"]
    assert set(unresolved_supply_terms(scenario, package)) == {
        "payment_schedule.early.balance_days",
        "payment_schedule.remaining.advance_bps",
    }
    assert validate_supply_terms(scenario, package) == []
    assert validate_supply_terms(scenario, package, True)
    package["payment_schedule"][1]["advance_bps"] = 0
    package["payment_schedule"][0]["balance_days"] = 0
    assert unresolved_supply_terms(scenario, package) == []
    assert supply_financial_summary(scenario, package)["weighted_advance_fraction"] == 0.1


def test_missing_payment_for_existing_lot_remains_unresolved(scenario, package):
    package["payment_schedule"].pop()
    assert unresolved_supply_terms(scenario, package) == ["payment_schedule.remaining"]
    assert validate_supply_terms(scenario, package) == []


@pytest.mark.parametrize("bad", [True, 10950000.0, "10950000", None, -1, 12500001])
def test_money_rejects_coercion_and_bounds(scenario, package, bad):
    package["base_price"]["minor_units"] = bad
    assert "invalid_term:base_price.minor_units" in validate_supply_terms(scenario, package)


@pytest.mark.parametrize("bad", [True, "5000", 5000.0, -1, 10001, None])
def test_fractions_reject_coercion_and_bounds(scenario, package, bad):
    package["payment_schedule"][0]["advance_bps"] = bad
    assert validate_supply_terms(scenario, package)


@pytest.mark.parametrize(
    "path,value",
    [
        (("delivery_lots", 0, "quantity"), 11),
        (("delivery_lots", 0, "lot_id"), "remaining"),
        (("delivery_lots", 0, "window_start"), "2026-11-04"),
        (("delivery_lots", 0, "window_start"), "2026-11-08"),
        (("delivery_lots", 0, "window_start"), "2026-02-30"),
        (("delivery_lots", 0, "window_end"), "2026-11-27"),
        (("delivery_lots", 0, "window_end"), "2026-11-5"),
        (("payment_schedule", 1, "lot_id"), "early"),
        (("payment_schedule", 0, "lot_id"), "invented"),
        (("payment_schedule", 0, "balance_days"), 60),
        (("reserve_policy", "delivery_lot_id"), "main"),
        (("reserve_policy", "mode"), []),
        (("reserve_policy", "quantity"), 4),
        (("reserve_policy", "use_cutoff"), "2026-12-05"),
        (("reserve_policy", "unit_price_rule"), "invented_formula"),
        (("reserve_policy", "diagnosis_policy_id"), "llm_decides"),
        (("delivery_basis", "basis"), "FOB"),
        (("delivery_basis", "destination_id"), "secret_address"),
    ],
)
def test_invalid_capabilities_and_references(scenario, package, path, value):
    target = package
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert validate_supply_terms(scenario, package)


def test_capacity_and_total_quantity_are_independent(scenario, package):
    package["delivery_lots"][0]["quantity"] = 11
    package["delivery_lots"][1]["quantity"] = 89
    violations = validate_supply_terms(scenario, package)
    assert "invalid_term:delivery_lots.early_capacity" in violations
    assert "invalid_term:delivery_lots.quantity_conservation" not in violations


def test_reserves_are_outside_main_quantity_and_budget(scenario, package):
    package["base_price"]["minor_units"] = 11300000
    assert validate_supply_terms(scenario, package, True) == []
    assert supply_constraint_violations(scenario, "buyer", package) == ["buyer_budget_exceeded"]
    package["reserve_policy"] = {"mode": "none"}
    assert supply_constraint_violations(scenario, "buyer", package) == []
    package["reserve_policy"]["quantity"] = 0
    assert validate_supply_terms(scenario, package)


def test_private_coefficients_are_authored_and_not_counterpart_inputs(scenario, package):
    old_seller = evaluate_supply_utility(scenario, "seller", package)
    scenario["supply_model"]["economics"]["buyer"]["comparison_value_minor"] = 99999999
    assert evaluate_supply_utility(scenario, "seller", package) == old_seller
    scenario["supply_model"]["economics"]["seller"]["acceleration_cost_per_unit_minor"] = 0
    assert evaluate_supply_utility(scenario, "seller", package) == old_seller + 5


def test_guaranteed_end_not_optimistic_start_drives_buyer_benefit(scenario, package):
    before = evaluate_supply_utility(scenario, "buyer", package)
    package["delivery_lots"][0]["window_end"] = "2026-11-08"
    assert evaluate_supply_utility(scenario, "buyer", package) == before - 25


def test_balance_financing_uses_only_delayed_unpaid_fraction(scenario, package):
    seller = evaluate_supply_utility(scenario, "seller", package)
    buyer = evaluate_supply_utility(scenario, "buyer", package)
    package["payment_schedule"][1]["balance_days"] = 30
    assert supply_financial_summary(scenario, package)["delayed_balance_fraction"] == 0.45
    assert evaluate_supply_utility(scenario, "seller", package) == seller - 1.125
    assert evaluate_supply_utility(scenario, "buyer", package) == buyer + 0.5625


@pytest.mark.parametrize("language", ["ru", "en"])
def test_formatter_is_human_readable_and_keeps_exact_terms(scenario, package, language):
    before = copy.deepcopy(package)
    text = format_supply_terms(scenario, package, language)
    assert "100%" in text and "50%" in text
    assert ("109 500 EUR" if language == "ru" else "109,500 EUR") in text
    assert ("112 785 EUR" if language == "ru" else "112,785 EUR") in text
    assert "hardware-replacement-v1" not in text
    assert "minor_units" not in text and "reserve_policy" not in text
    assert package == before
    opening = authored_opening(scenario)[2]
    text = format_supply_terms(scenario, opening, language)
    assert "%" not in text and "DDP" not in text
    assert ("резерв" if language == "ru" else "reserve") not in text


def test_unknown_grammar_never_gets_formatted_or_evaluated(scenario, package):
    package["late_penalty"] = {"rate": 0.5}
    assert validate_supply_terms(scenario, package) == ["term_not_in_compiled_grammar"]
    with pytest.raises(ValueError):
        format_supply_terms(scenario, package, "ru")
    with pytest.raises(ValueError):
        evaluate_supply_utility(scenario, "buyer", package)


def test_domain_also_honors_stricter_authored_value_schema(scenario, package):
    schema = scenario["terms"]["definitions"]["base_price"]["value_schema"]
    schema["properties"]["minor_units"]["minimum"] = 11000000
    assert "invalid_term:base_price" in validate_supply_terms(scenario, package)
    with pytest.raises(ValueError):
        evaluate_supply_utility(scenario, "seller", package)


@pytest.mark.parametrize("mutation", ["expression", "primitive", "constraint", "term_evaluator"])
def test_compiler_rejects_ignored_supply_rules(scenario, mutation):
    if mutation == "expression":
        scenario["term_model"]["evaluation_rules"]["supply_economics"]["expression"] = {
            "type": "llm_utility"
        }
    elif mutation == "primitive":
        scenario["term_model"]["primitives"]["arbitrary"] = {}
    elif mutation == "constraint":
        scenario["hard_constraints"] = [
            {
                "id": "ignored",
                "applies_to_role": "buyer",
                "expression": {"op": "eq", "left": {"const": 1}, "right": {"const": 0}},
            }
        ]
    else:
        scenario["terms"]["definitions"]["base_price"]["evaluation_rule_ids"] = ["llm_utility"]
    with pytest.raises(ScenarioError, match="Invalid supply"):
        compile_scenario({"scenario": scenario}, ROOT / "test.yaml")


@pytest.mark.parametrize(
    "mutation",
    [
        "evaluator",
        "missing_cost",
        "zero_divisor",
        "bad_date",
        "unknown_rule",
        "unknown_coefficient",
        "bad_price_tier",
    ],
)
def test_compiler_rejects_unsupported_or_incomplete_authored_configuration(scenario, mutation):
    model = scenario["supply_model"]
    if mutation == "evaluator":
        model["evaluator_version"] = "llm-utility"
    elif mutation == "missing_cost":
        del model["economics"]["seller"]["base_cost_minor"]
    elif mutation == "zero_divisor":
        model["economics"]["utility_divisor_minor"] = 0
    elif mutation == "bad_date":
        model["calendar"]["earliest_date"] = "2026-02-30"
    elif mutation == "unknown_rule":
        model["reserve_rules"]["inconclusive_deadline_outcome"] = "charge"
    elif mutation == "unknown_coefficient":
        model["economics"]["seller"]["secret_probability"] = 0.1
    else:
        model["npc_policy"]["split_price_index"] = 99
    with pytest.raises(ScenarioError, match="Invalid supply"):
        compile_scenario({"scenario": scenario}, ROOT / "test.yaml")


def test_complete_opening_cannot_be_published_as_an_offer(scenario, package):
    del scenario["roles"]["seller"]["opening_position"]
    scenario["roles"]["seller"]["opening_offer"] = package
    with pytest.raises(ScenarioError, match="preliminary"):
        compile_scenario({"scenario": scenario}, ROOT / "test.yaml")


@pytest.mark.parametrize(
    "flags,outcome,charge,original",
    [
        (
            {"hardware_defect": True, "verified": True},
            "hardware_free_replacement",
            0,
            "retained_by_supplier",
        ),
        (
            {"supplier_repair": True, "verified": True},
            "hardware_free_replacement",
            0,
            "retained_by_supplier",
        ),
        (
            {"buyer_cause": True, "verified": True},
            "buyer_cause_purchase",
            109500,
            "returned_to_buyer",
        ),
        ({"buyer_cause": True}, "diagnosis_pending", 0, "held_by_supplier"),
        (
            {"buyer_cause": True, "hardware_defect": True, "verified": True},
            "hardware_free_replacement",
            0,
            "retained_by_supplier",
        ),
    ],
)
def test_settlement_requires_verified_exclusive_outcome(
    scenario, package, flags, outcome, charge, original
):
    result = settle_reserve_unit(
        scenario,
        package,
        used_on="2026-11-25",
        received_on="2026-11-26",
        as_of="2026-12-02",
        **flags,
    )
    assert result["outcome"] == outcome
    assert result["charge_minor"] == charge
    assert result["original_disposition"] == original


def test_inconclusive_is_free_at_deadline_not_automatic_payment(scenario, package):
    before = settle_reserve_unit(
        scenario, package, used_on="2026-12-01", received_on="2026-12-02", as_of="2026-12-11"
    )
    at_deadline = settle_reserve_unit(
        scenario, package, used_on="2026-12-01", received_on="2026-12-02", as_of="2026-12-12"
    )
    late_diagnosis = settle_reserve_unit(
        scenario,
        package,
        used_on="2026-12-01",
        received_on="2026-12-02",
        as_of="2026-12-13",
        buyer_cause=True,
        verified=True,
    )
    assert before["outcome"] == "diagnosis_pending" and before["charge_due"] is False
    assert at_deadline["outcome"] == "deadline_free_replacement"
    assert at_deadline["charge_minor"] == 0 and at_deadline["final"] is True
    assert late_diagnosis["outcome"] == "deadline_free_replacement"


def test_timely_diagnosis_can_be_replayed_after_its_deadline(scenario, package):
    result = settle_reserve_unit(
        scenario,
        package,
        used_on="2026-12-01",
        received_on="2026-12-02",
        diagnosed_on="2026-12-05",
        as_of="2026-12-20",
        buyer_cause=True,
        verified=True,
    )
    assert result["outcome"] == "buyer_cause_purchase"
    assert result["charge_minor"] == 109500


def test_unused_and_used_bills_never_accumulate(scenario, package):
    pending = settle_reserve_unit(scenario, package, as_of="2026-12-01")
    unused = settle_reserve_unit(scenario, package, as_of="2026-12-02")
    late = settle_reserve_unit(
        scenario,
        package,
        as_of="2026-12-04",
        used_on="2026-12-03",
        received_on="2026-12-04",
        hardware_defect=True,
        verified=True,
    )
    assert pending["charge_minor"] == 0 and pending["final"] is False
    assert unused["outcome"] == "unused_purchase" and unused["charge_minor"] == 109500
    assert late["outcome"] == "unused_purchase" and late["charge_minor"] == 109500
    outcomes = [
        {},
        {
            "used_on": "2026-11-25",
            "received_on": "2026-11-26",
            "hardware_defect": True,
            "verified": True,
        },
        {
            "used_on": "2026-11-25",
            "received_on": "2026-11-26",
            "buyer_cause": True,
            "verified": True,
        },
    ]
    totals = [
        sum(
            settle_reserve_unit(scenario, package, as_of="2026-12-02", **item)["charge_minor"]
            for item in branch
        )
        for branch in itertools.product(outcomes, repeat=3)
    ]
    assert (
        max(totals)
        == supply_financial_summary(scenario, package)["maximum_reserve_liability_minor"]
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"used_on": "2026-11-01"},
        {"used_on": "2026-12-10"},
        {"received_on": "2026-11-26"},
        {"used_on": "2026-11-25", "received_on": "2026-11-24"},
        {"used_on": "2026-11-25", "received_on": "2026-11-26", "diagnosed_on": "2026-11-25"},
        {"used_on": "not-a-date"},
        {"buyer_cause": "verified"},
    ],
)
def test_settlement_rejects_impossible_dates_and_untyped_evidence(scenario, package, kwargs):
    with pytest.raises(ValueError):
        settle_reserve_unit(scenario, package, as_of="2026-12-02", **kwargs)
