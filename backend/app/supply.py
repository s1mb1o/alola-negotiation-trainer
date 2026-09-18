"""Versioned, deterministic supply-package grammar and authored economics.

This module does not extract messages, select participants, or call providers.
Missing values remain missing. Monetary obligations use integer minor units.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jsonschema import Draft202012Validator


SUPPLY_CONTRACT = "supply-package-v1"
SUPPLY_EVALUATOR = "supply-economics-v1"
SUPPLY_FORMATTER = "supply-package-display-v1"
TERM_IDS = ("base_price", "delivery_lots", "payment_schedule", "delivery_basis", "reserve_policy")


def is_supply_scenario(scenario: dict[str, Any]) -> bool:
    return scenario.get("negotiation_contract") == SUPPLY_CONTRACT


def _integer(value: Any, minimum: int = 0, maximum: int | None = None) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= minimum
        and (maximum is None or value <= maximum)
    )


def _date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        result = date.fromisoformat(value)
    except ValueError:
        return None
    return result if result.isoformat() == value else None


def validate_supply_configuration(scenario: dict[str, Any]) -> list[str]:
    """Reject incomplete or unknown evaluator configuration at publication time."""

    model = scenario.get("supply_model")
    if not is_supply_scenario(scenario) or not isinstance(model, dict):
        return ["invalid_supply_configuration"]
    expected = {
        "version",
        "evaluator_version",
        "calendar",
        "capabilities",
        "bounds",
        "reserve_rules",
        "economics",
        "npc_policy",
    }
    errors: list[str] = []
    if set(model) != expected:
        errors.append("invalid_supply_configuration_fields")
    if (
        model.get("version") != SUPPLY_CONTRACT
        or model.get("evaluator_version") != SUPPLY_EVALUATOR
    ):
        errors.append("unsupported_supply_evaluator")
    if scenario.get("currency") != "EUR" or set(scenario.get("roles", {})) != {"buyer", "seller"}:
        errors.append("invalid_supply_roles_or_currency")
    calendar = model.get("calendar", {})
    calendar_dates = {
        "negotiation_date",
        "earliest_date",
        "earliest_full_date",
        "latest_date",
        "early_november_start",
        "early_november_end",
        "integration_deadline",
        "completion_deadline",
    }
    if not isinstance(calendar, dict) or set(calendar) != calendar_dates | {"timezone"}:
        errors.append("invalid_supply_calendar")
    elif any(_date(calendar[key]) is None for key in calendar_dates):
        errors.append("invalid_supply_calendar_date")
    else:
        if not (
            calendar["negotiation_date"]
            < calendar["earliest_date"]
            <= calendar["early_november_start"]
            <= calendar["early_november_end"]
            <= calendar["integration_deadline"]
            < calendar["earliest_full_date"]
            <= calendar["completion_deadline"]
            <= calendar["latest_date"]
        ):
            errors.append("invalid_supply_calendar_order")
    try:
        ZoneInfo(calendar.get("timezone", ""))
    except (ZoneInfoNotFoundError, ValueError, TypeError, AttributeError):
        errors.append("invalid_supply_timezone")
    capabilities = model.get("capabilities", {})
    capability_fields = {
        "main_quantity",
        "max_lots",
        "max_early_quantity",
        "max_reserve_quantity",
        "lot_ids",
        "delivery_basis",
        "destination_id",
        "balance_days",
    }
    if not isinstance(capabilities, dict) or set(capabilities) != capability_fields:
        errors.append("invalid_supply_capabilities")
    elif not (
        _integer(capabilities["main_quantity"], 1)
        and capabilities["max_lots"] == 2
        and _integer(capabilities["max_early_quantity"], 1, capabilities["main_quantity"] - 1)
        and _integer(capabilities["max_reserve_quantity"], 1, 3)
        and capabilities["lot_ids"] == ["main", "early", "remaining"]
        and capabilities["delivery_basis"] == "DDP"
        and capabilities["destination_id"] == "vector_site"
        and capabilities["balance_days"] == [0, 30]
    ):
        errors.append("unsupported_supply_capabilities")
    bounds = model.get("bounds", {})
    if not isinstance(bounds, dict) or set(bounds) != {
        "base_price_min_minor",
        "base_price_max_minor",
    }:
        errors.append("invalid_supply_bounds")
    elif not (
        _integer(bounds["base_price_min_minor"], 1)
        and _integer(bounds["base_price_max_minor"], bounds["base_price_min_minor"])
    ):
        errors.append("invalid_supply_price_bounds")
    rules = model.get("reserve_rules", {})
    rule_fields = {
        "use_cutoff",
        "unused_payable_on",
        "diagnosis_days",
        "unit_price_rule",
        "diagnosis_policy_id",
        "inconclusive_deadline_outcome",
        "hardware_precedence",
    }
    if not isinstance(rules, dict) or set(rules) != rule_fields:
        errors.append("invalid_supply_reserve_rules")
    elif not (
        _date(rules["use_cutoff"]) is not None
        and _date(rules["unused_payable_on"]) is not None
        and rules["use_cutoff"] < rules["unused_payable_on"]
        and _integer(rules["diagnosis_days"], 1, 60)
        and rules["unit_price_rule"] == "base_unit_ceil"
        and rules["diagnosis_policy_id"] == "hardware-replacement-v1"
        and rules["inconclusive_deadline_outcome"] == "free"
        and rules["hardware_precedence"] is True
    ):
        errors.append("unsupported_supply_reserve_rules")
    economics = model.get("economics", {})
    role_fields = {
        "buyer": {
            "maximum_liability_minor",
            "comparison_value_minor",
            "integration_value_minor",
            "completion_value_minor",
            "financing_cost_minor",
            "reserve_value_per_unit_minor",
            "delayed_balance_benefit_minor",
        },
        "seller": {
            "minimum_base_price_minor",
            "base_cost_minor",
            "split_cost_minor",
            "acceleration_cost_per_unit_minor",
            "financing_credit_minor",
            "reserve_cost_per_unit_minor",
            "delayed_balance_cost_minor",
        },
    }
    if not isinstance(economics, dict) or set(economics) != {
        "buyer",
        "seller",
        "utility_divisor_minor",
    }:
        errors.append("invalid_supply_economics")
    else:
        if not _integer(economics["utility_divisor_minor"], 1):
            errors.append("invalid_supply_utility_divisor")
        for role, fields in role_fields.items():
            values = economics.get(role)
            if (
                not isinstance(values, dict)
                or set(values) != fields
                or any(not _integer(value) for value in values.values())
            ):
                errors.append(f"invalid_supply_economics:{role}")
    npc_policy = model.get("npc_policy", {})
    if not isinstance(npc_policy, dict) or set(npc_policy) != {
        "price_candidates_minor",
        "standard_price_index",
        "advance_price_index",
        "split_price_index",
        "advance_threshold_bps",
    }:
        errors.append("invalid_supply_npc_policy")
    else:
        candidates = npc_policy["price_candidates_minor"]
        if (
            not isinstance(candidates, list)
            or not 1 <= len(candidates) <= 16
            or any(not _integer(value, 1) for value in candidates)
            or len(set(candidates)) != len(candidates)
        ):
            errors.append("invalid_supply_price_candidates")
        elif "invalid_supply_bounds" not in errors and "invalid_supply_price_bounds" not in errors:
            if any(
                not bounds["base_price_min_minor"] <= value <= bounds["base_price_max_minor"]
                for value in candidates
            ):
                errors.append("supply_price_candidate_out_of_bounds")
        if isinstance(candidates, list) and any(
            not _integer(npc_policy[key], 0, len(candidates) - 1)
            for key in ("standard_price_index", "advance_price_index", "split_price_index")
        ):
            errors.append("invalid_supply_price_tier")
        if not _integer(npc_policy["advance_threshold_bps"], 0, 10000):
            errors.append("invalid_supply_advance_threshold")
    terms = scenario.get("terms", {})
    if set(terms.get("definitions", {})) != set(TERM_IDS) or terms.get("required_term_ids") != list(
        TERM_IDS
    ):
        errors.append("invalid_supply_term_definitions")
    if terms.get("optional_term_ids") != []:
        errors.append("invalid_supply_optional_terms")
    if scenario.get("hard_constraints") != []:
        errors.append("supply_constraints_must_use_authored_economics")
    term_model = scenario.get("term_model", {})
    expected_primitives = {
        "money",
        "quantity",
        "date_window",
        "fraction",
        "schedule",
        "condition",
        "obligation",
    }
    if set(term_model.get("primitives", {})) != expected_primitives:
        errors.append("unsupported_supply_primitives")
    rules = term_model.get("evaluation_rules", {})
    if set(rules) != {"supply_economics"} or rules.get("supply_economics") != {
        "applies_to_roles": ["buyer", "seller"],
        "input_types": ["supply_package"],
        "expression": {"type": SUPPLY_EVALUATOR, "source": "supply_model"},
    }:
        errors.append("unsupported_supply_evaluation_rule")
    for definition in terms.get("definitions", {}).values():
        if definition.get("evaluation_rule_ids") != ["supply_economics"]:
            errors.append("unsupported_supply_term_evaluator")
    utility = scenario.get("utility_model", {})
    if utility.get("normalization") != {"minimum": 0, "maximum": 100}:
        errors.append("unsupported_supply_utility_range")
    for role in ("buyer", "seller"):
        role_model = utility.get("role_models", {}).get(role, {})
        if (
            role_model.get("aggregation") != SUPPLY_EVALUATOR
            or role_model.get("value_functions") != {}
        ):
            errors.append(f"invalid_supply_utility_model:{role}")
        reservation = role_model.get("reservation_utility")
        if (
            not isinstance(reservation, (int, float))
            or isinstance(reservation, bool)
            or not 0 <= reservation <= 100
        ):
            errors.append(f"invalid_supply_reservation:{role}")
        if (
            scenario.get("roles", {})
            .get(role, {})
            .get("constraints", {})
            .get("reservation_utility")
            != reservation
        ):
            errors.append(f"inconsistent_supply_reservation:{role}")
    return errors


def unresolved_supply_terms(scenario: dict[str, Any], terms: dict[str, Any]) -> list[str]:
    """Return stable nested paths. No omitted value receives a default."""

    missing: list[str] = []
    for key in TERM_IDS:
        if key not in terms:
            missing.append(key)
    for key, fields in {
        "base_price": ("currency", "minor_units"),
        "delivery_basis": ("basis", "destination_id"),
    }.items():
        if isinstance(terms.get(key), dict):
            missing.extend(f"{key}.{field}" for field in fields if field not in terms[key])
    lots = terms.get("delivery_lots", [])
    payments = terms.get("payment_schedule", [])
    if isinstance(lots, list):
        for index, lot in enumerate(lots):
            if not isinstance(lot, dict):
                continue
            lot_id = lot.get("lot_id", str(index))
            for field in ("lot_id", "quantity", "window_start", "window_end"):
                if field not in lot:
                    missing.append(f"delivery_lots.{lot_id}.{field}")
            if isinstance(payments, list) and "payment_schedule" in terms and "lot_id" in lot:
                entries = [
                    item
                    for item in payments
                    if isinstance(item, dict) and item.get("lot_id") == lot_id
                ]
                if not entries:
                    missing.append(f"payment_schedule.{lot_id}")
    if isinstance(payments, list):
        for index, payment in enumerate(payments):
            if isinstance(payment, dict):
                lot_id = payment.get("lot_id", str(index))
                for field in ("lot_id", "advance_bps", "balance_days"):
                    if field not in payment:
                        missing.append(f"payment_schedule.{lot_id}.{field}")
    reserve = terms.get("reserve_policy")
    if isinstance(reserve, dict):
        if "mode" not in reserve:
            missing.append("reserve_policy.mode")
        elif reserve["mode"] == "contingent":
            for field in (
                "quantity",
                "delivery_lot_id",
                "use_cutoff",
                "unused_payable_on",
                "unit_price_rule",
                "diagnosis_policy_id",
            ):
                if field not in reserve:
                    missing.append(f"reserve_policy.{field}")
    return missing


def validate_supply_terms(
    scenario: dict[str, Any], terms: dict[str, Any], complete: bool = False
) -> list[str]:
    """Validate grammar, conservation, capabilities, and cross-field references."""

    if not isinstance(terms, dict):
        return ["invalid_supply_package"]
    if any(key not in TERM_IDS for key in terms):
        return ["term_not_in_compiled_grammar"]
    model = scenario["supply_model"]
    capabilities, calendar, bounds = model["capabilities"], model["calendar"], model["bounds"]
    violations: list[str] = []
    for key, value in terms.items():
        schema = scenario["terms"]["definitions"][key]["value_schema"]
        if next(Draft202012Validator(schema).iter_errors(value), None) is not None:
            violations.append(f"invalid_term:{key}")

    def invalid(path: str) -> None:
        violations.append(f"invalid_term:{path}")

    def obj(value: Any, fields: set[str], path: str) -> bool:
        if not isinstance(value, dict) or not set(value) <= fields:
            invalid(path)
            return False
        return True

    if "base_price" in terms:
        price = terms["base_price"]
        if obj(price, {"currency", "minor_units"}, "base_price"):
            if "currency" in price and price["currency"] != scenario["currency"]:
                invalid("base_price.currency")
            if "minor_units" in price and not _integer(
                price["minor_units"], bounds["base_price_min_minor"], bounds["base_price_max_minor"]
            ):
                invalid("base_price.minor_units")
    lots = terms.get("delivery_lots", [])
    lot_ids: list[str] = []
    if "delivery_lots" in terms:
        if not isinstance(lots, list) or not 1 <= len(lots) <= capabilities["max_lots"]:
            invalid("delivery_lots")
            lots = []
        for index, lot in enumerate(lots):
            path = f"delivery_lots.{index}"
            if not obj(lot, {"lot_id", "quantity", "window_start", "window_end"}, path):
                continue
            lot_id = lot.get("lot_id")
            if (
                not isinstance(lot_id, str)
                or lot_id not in capabilities["lot_ids"]
                or lot_id in lot_ids
            ):
                invalid(f"{path}.lot_id")
            else:
                lot_ids.append(lot_id)
            if "quantity" in lot and not _integer(
                lot["quantity"], 1, capabilities["main_quantity"]
            ):
                invalid(f"{path}.quantity")
            for field in ("window_start", "window_end"):
                if field in lot and (
                    _date(lot[field]) is None
                    or not calendar["earliest_date"] <= lot[field] <= calendar["latest_date"]
                ):
                    invalid(f"{path}.{field}")
            if (
                _date(lot.get("window_start"))
                and _date(lot.get("window_end"))
                and lot["window_start"] > lot["window_end"]
            ):
                invalid(f"{path}.window_order")
        quantities = [lot.get("quantity") for lot in lots if isinstance(lot, dict)]
        if (
            lots
            and len(quantities) == len(lots)
            and all(_integer(quantity, 1) for quantity in quantities)
        ):
            if sum(quantities) != capabilities["main_quantity"]:
                invalid("delivery_lots.quantity_conservation")
            early_quantity = sum(
                lot["quantity"]
                for lot in lots
                if _date(lot.get("window_start"))
                and lot["window_start"] < calendar["earliest_full_date"]
            )
            if early_quantity > capabilities["max_early_quantity"]:
                invalid("delivery_lots.early_capacity")
        if len(lot_ids) == len(lots) and lots:
            expected_ids = {"main"} if len(lots) == 1 else {"early", "remaining"}
            if set(lot_ids) != expected_ids:
                invalid("delivery_lots.identity")
    if "payment_schedule" in terms:
        payments = terms["payment_schedule"]
        if not isinstance(payments, list) or not 1 <= len(payments) <= capabilities["max_lots"]:
            invalid("payment_schedule")
            payments = []
        payment_ids: list[str] = []
        for index, payment in enumerate(payments):
            path = f"payment_schedule.{index}"
            if not obj(payment, {"lot_id", "advance_bps", "balance_days"}, path):
                continue
            lot_id = payment.get("lot_id")
            if not isinstance(lot_id, str) or lot_id not in lot_ids or lot_id in payment_ids:
                invalid(f"{path}.lot_id")
            else:
                payment_ids.append(lot_id)
            if "advance_bps" in payment and not _integer(payment["advance_bps"], 0, 10000):
                invalid(f"{path}.advance_bps")
            if "balance_days" in payment and (
                not _integer(payment["balance_days"])
                or payment["balance_days"] not in capabilities["balance_days"]
            ):
                invalid(f"{path}.balance_days")
    if "delivery_basis" in terms:
        basis = terms["delivery_basis"]
        if obj(basis, {"basis", "destination_id"}, "delivery_basis"):
            for key, value in {
                "basis": capabilities["delivery_basis"],
                "destination_id": capabilities["destination_id"],
            }.items():
                if key in basis and basis[key] != value:
                    invalid(f"delivery_basis.{key}")
    if "reserve_policy" in terms:
        reserve = terms["reserve_policy"]
        fields = {
            "mode",
            "quantity",
            "delivery_lot_id",
            "use_cutoff",
            "unused_payable_on",
            "unit_price_rule",
            "diagnosis_policy_id",
        }
        if obj(reserve, fields, "reserve_policy"):
            if "mode" in reserve and (
                not isinstance(reserve["mode"], str)
                or reserve["mode"] not in {"none", "contingent"}
            ):
                invalid("reserve_policy.mode")
            if reserve.get("mode") == "none" and set(reserve) != {"mode"}:
                invalid("reserve_policy.none_has_terms")
            if "quantity" in reserve and not _integer(
                reserve["quantity"], 1, capabilities["max_reserve_quantity"]
            ):
                invalid("reserve_policy.quantity")
            if "delivery_lot_id" in reserve and reserve["delivery_lot_id"] not in lot_ids:
                invalid("reserve_policy.delivery_lot_id")
            for key in (
                "use_cutoff",
                "unused_payable_on",
                "unit_price_rule",
                "diagnosis_policy_id",
            ):
                if key in reserve and reserve[key] != model["reserve_rules"][key]:
                    invalid(f"reserve_policy.{key}")
    if complete:
        violations.extend(
            f"missing_required_term:{path}" for path in unresolved_supply_terms(scenario, terms)
        )
    return list(dict.fromkeys(violations))


def _require_complete(scenario: dict[str, Any], terms: dict[str, Any]) -> None:
    errors = validate_supply_terms(scenario, terms, complete=True)
    if errors:
        raise ValueError("Supply package is not complete and valid: " + ", ".join(errors))


def supply_financial_summary(scenario: dict[str, Any], terms: dict[str, Any]) -> dict[str, Any]:
    """Return obligations derived only from a complete validated public package."""

    _require_complete(scenario, terms)
    base = terms["base_price"]["minor_units"]
    quantity = scenario["supply_model"]["capabilities"]["main_quantity"]
    order = {"main": 0, "early": 1, "remaining": 2}
    lots = sorted(terms["delivery_lots"], key=lambda lot: order[lot["lot_id"]])
    payments = {payment["lot_id"]: payment for payment in terms["payment_schedule"]}
    rows: list[dict[str, Any]] = []
    allocated = 0
    for index, lot in enumerate(lots):
        payment = payments[lot["lot_id"]]
        price = base - allocated if index == len(lots) - 1 else base * lot["quantity"] // quantity
        allocated += price
        advance = (price * payment["advance_bps"] + 5000) // 10000
        rows.append(
            {
                "lot_id": lot["lot_id"],
                "quantity": lot["quantity"],
                "price_minor": price,
                "advance_minor": advance,
                "balance_minor": price - advance,
                "balance_days": payment["balance_days"],
            }
        )
    reserve = terms["reserve_policy"]
    reserve_quantity = reserve["quantity"] if reserve["mode"] == "contingent" else 0
    reserve_unit = (base + quantity - 1) // quantity
    total_advance = sum(row["advance_minor"] for row in rows)
    delayed_balance = sum(row["balance_minor"] for row in rows if row["balance_days"] == 30)
    return {
        "currency": scenario["currency"],
        "base_price_minor": base,
        "reserve_quantity": reserve_quantity,
        "reserve_unit_price_minor": reserve_unit,
        "maximum_reserve_liability_minor": reserve_quantity * reserve_unit,
        "maximum_liability_minor": base + reserve_quantity * reserve_unit,
        "advance_minor": total_advance,
        "balance_minor": base - total_advance,
        "weighted_advance_fraction": float(Decimal(total_advance) / base),
        "delayed_balance_fraction": float(Decimal(delayed_balance) / base),
        "lots": rows,
    }


def supply_constraint_violations(
    scenario: dict[str, Any], role: str, terms: dict[str, Any]
) -> list[str]:
    if role not in {"buyer", "seller"}:
        return ["unknown_supply_role"]
    errors = validate_supply_terms(scenario, terms, complete=True)
    if errors:
        return errors
    summary = supply_financial_summary(scenario, terms)
    model = scenario["supply_model"]["economics"][role]
    if role == "buyer" and summary["maximum_liability_minor"] > model["maximum_liability_minor"]:
        return ["buyer_budget_exceeded"]
    if role == "seller" and summary["base_price_minor"] < model["minimum_base_price_minor"]:
        return ["seller_floor_not_met"]
    return []


def evaluate_supply_utility(scenario: dict[str, Any], role: str, terms: dict[str, Any]) -> float:
    """Evaluate complete grammar-valid packages, including economically bad ones."""

    if role not in {"buyer", "seller"}:
        raise ValueError("Unknown supply role")
    summary = supply_financial_summary(scenario, terms)
    model = scenario["supply_model"]
    economics = model["economics"][role]
    base = Decimal(summary["base_price_minor"])
    advance_fraction = Decimal(summary["advance_minor"]) / base
    delayed_fraction = (
        Decimal(sum(row["balance_minor"] for row in summary["lots"] if row["balance_days"] == 30))
        / base
    )
    lots = terms["delivery_lots"]
    if role == "seller":
        accelerated = sum(
            lot["quantity"]
            for lot in lots
            if lot["window_start"] < model["calendar"]["latest_date"]
        )
        margin = (
            base
            - economics["base_cost_minor"]
            - (economics["split_cost_minor"] if len(lots) > 1 else 0)
            - accelerated * economics["acceleration_cost_per_unit_minor"]
            - summary["reserve_quantity"] * economics["reserve_cost_per_unit_minor"]
            + advance_fraction * economics["financing_credit_minor"]
            - delayed_fraction * economics["delayed_balance_cost_minor"]
        )
    else:
        early_quantity = sum(
            lot["quantity"]
            for lot in lots
            if lot["window_end"] <= model["calendar"]["integration_deadline"]
        )
        integration = (
            economics["integration_value_minor"]
            if early_quantity >= model["capabilities"]["max_early_quantity"]
            else 0
        )
        completion = (
            economics["completion_value_minor"]
            if all(lot["window_end"] <= model["calendar"]["completion_deadline"] for lot in lots)
            else 0
        )
        reserve = terms["reserve_policy"]
        reserve_benefit = 0
        if reserve["mode"] == "contingent":
            reserve_lot = next(lot for lot in lots if lot["lot_id"] == reserve["delivery_lot_id"])
            if reserve_lot["window_end"] <= model["calendar"]["completion_deadline"]:
                reserve_benefit = (
                    summary["reserve_quantity"] * economics["reserve_value_per_unit_minor"]
                )
        margin = (
            Decimal(economics["comparison_value_minor"] - summary["maximum_liability_minor"])
            + integration
            + completion
            + reserve_benefit
            - advance_fraction * economics["financing_cost_minor"]
            + delayed_fraction * economics["delayed_balance_benefit_minor"]
        )
    utility = max(
        Decimal(0), min(Decimal(100), margin / model["economics"]["utility_divisor_minor"])
    )
    return float(utility.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def settle_reserve_unit(
    scenario: dict[str, Any],
    terms: dict[str, Any],
    *,
    as_of: str,
    used_on: str | None = None,
    received_on: str | None = None,
    diagnosed_on: str | None = None,
    hardware_defect: bool = False,
    supplier_repair: bool = False,
    buyer_cause: bool = False,
    verified: bool = False,
) -> dict[str, Any]:
    """Select one outcome for one reserve unit from verified scenario facts.

    This pure calculation does not invoice or alter inventory. A caller must
    persist a unit identity if it operates a later settlement workflow.
    """

    summary = supply_financial_summary(scenario, terms)
    if not summary["reserve_quantity"]:
        raise ValueError("The package has no reserve")
    if _date(as_of) is None or any(
        value is not None and _date(value) is None for value in (used_on, received_on, diagnosed_on)
    ):
        raise ValueError("Invalid reserve outcome date")
    if any(
        not isinstance(value, bool)
        for value in (hardware_defect, supplier_repair, buyer_cause, verified)
    ):
        raise ValueError("Reserve outcome flags must be booleans")
    if used_on is not None and used_on > as_of:
        raise ValueError("A future use is not an observed outcome")
    if received_on is not None and (
        used_on is None or received_on < used_on or received_on > as_of
    ):
        raise ValueError("Invalid diagnostic receipt chronology")
    if diagnosed_on is not None and (
        received_on is None or diagnosed_on < received_on or diagnosed_on > as_of
    ):
        raise ValueError("Invalid diagnosis chronology")
    reserve_lot = next(
        lot
        for lot in terms["delivery_lots"]
        if lot["lot_id"] == terms["reserve_policy"]["delivery_lot_id"]
    )
    if used_on is not None and used_on < reserve_lot["window_start"]:
        raise ValueError("Reserve cannot be used before its delivery window")
    rules = scenario["supply_model"]["reserve_rules"]
    result = {
        "outcome": "unused_pending",
        "charge_minor": 0,
        "charge_due": False,
        "original_disposition": "not_applicable",
        "reserve_disposition": "held_by_buyer",
        "final": False,
    }
    timely = used_on is not None and used_on <= rules["use_cutoff"]
    if not timely:
        if as_of >= rules["unused_payable_on"]:
            result.update(
                outcome="unused_purchase",
                charge_minor=summary["reserve_unit_price_minor"],
                charge_due=True,
                reserve_disposition="purchased_by_buyer",
                final=True,
            )
        return result
    result.update(
        outcome="diagnosis_pending",
        original_disposition="awaiting_supplier_receipt",
        reserve_disposition="provisional_replacement",
    )
    if received_on is None:
        return result
    result["original_disposition"] = "held_by_supplier"
    deadline = _date(received_on) + timedelta(days=rules["diagnosis_days"])
    result["diagnosis_deadline"] = deadline.isoformat()
    timely_diagnosis = (diagnosed_on or as_of) <= deadline.isoformat()
    if verified and timely_diagnosis and (hardware_defect or supplier_repair):
        result.update(
            outcome="hardware_free_replacement",
            original_disposition="retained_by_supplier",
            reserve_disposition="retained_by_buyer",
            final=True,
        )
    elif verified and timely_diagnosis and buyer_cause:
        result.update(
            outcome="buyer_cause_purchase",
            charge_minor=summary["reserve_unit_price_minor"],
            charge_due=True,
            original_disposition="returned_to_buyer",
            reserve_disposition="purchased_by_buyer",
            final=True,
        )
    elif _date(as_of) >= deadline:
        result.update(
            outcome="deadline_free_replacement",
            original_disposition="retained_by_supplier",
            reserve_disposition="retained_by_buyer",
            final=True,
        )
    return result


def _money(minor: int, language: str, currency: str = "EUR") -> str:
    whole, cents = divmod(minor, 100)
    separator = " " if language == "ru" else ","
    text = f"{whole:,}".replace(",", separator)
    if cents:
        text += ("," if language == "ru" else ".") + f"{cents:02}"
    return text + " " + currency


def _display_date(value: str, language: str) -> str:
    parsed = _date(value)
    if parsed is None:
        return value
    months = (
        (
            "января",
            "февраля",
            "марта",
            "апреля",
            "мая",
            "июня",
            "июля",
            "августа",
            "сентября",
            "октября",
            "ноября",
            "декабря",
        )
        if language == "ru"
        else (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    )
    return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"


def _devices(quantity: int, language: str) -> str:
    if language != "ru":
        return f"{quantity} " + ("device" if quantity == 1 else "devices")
    if 11 <= quantity % 100 <= 14:
        noun = "устройств"
    elif quantity % 10 == 1:
        noun = "устройство"
    elif 2 <= quantity % 10 <= 4:
        noun = "устройства"
    else:
        noun = "устройств"
    return f"{quantity} {noun}"


def format_supply_terms(scenario: dict[str, Any], terms: dict[str, Any], language: str) -> str:
    """Create a human-readable immutable block without inventing missing terms."""

    errors = validate_supply_terms(scenario, terms)
    if errors:
        raise ValueError("Cannot format invalid supply terms: " + ", ".join(errors))
    ru = language == "ru"
    lines: list[str] = []
    price = terms.get("base_price", {})
    if "minor_units" in price:
        lines.append(
            ("Стоимость основных устройств: " if ru else "Main-device price: ")
            + _money(price["minor_units"], language)
            + "."
        )
    labels = {
        "main": "основная партия" if ru else "main lot",
        "early": "первая партия" if ru else "early lot",
        "remaining": "оставшаяся партия" if ru else "remaining lot",
    }
    for lot in terms.get("delivery_lots", []):
        details: list[str] = []
        if "quantity" in lot:
            details.append(_devices(lot["quantity"], language))
        start, end = lot.get("window_start"), lot.get("window_end")
        if start and end:
            window = (
                _display_date(end, language)
                if start == end
                else _display_date(start, language) + " — " + _display_date(end, language)
            )
            details.append(("поставка " if ru else "delivery ") + window)
        elif start:
            details.append(
                ("поставка не ранее " if ru else "delivery no earlier than ")
                + _display_date(start, language)
            )
        elif end:
            details.append(
                ("поставка не позднее " if ru else "delivery no later than ")
                + _display_date(end, language)
            )
        lines.append(labels[lot["lot_id"]].capitalize() + ": " + "; ".join(details) + ".")
    for payment in terms.get("payment_schedule", []):
        details = []
        if "advance_bps" in payment:
            percent = (
                format(Decimal(payment["advance_bps"]) / 100, "f").rstrip("0").rstrip(".")
                if payment["advance_bps"] % 100
                else str(payment["advance_bps"] // 100)
            )
            details.append(("аванс " if ru else "advance ") + percent + "%")
        if "balance_days" in payment:
            days = payment["balance_days"]
            details.append(
                ("остаток при поставке" if ru else "balance on delivery")
                if days == 0
                else (
                    f"остаток через {days} дней после поставки"
                    if ru
                    else f"balance {days} days after delivery"
                )
            )
        lines.append(
            ("Оплата — " if ru else "Payment — ")
            + labels[payment["lot_id"]]
            + ": "
            + "; ".join(details)
            + "."
        )
    basis = terms.get("delivery_basis", {})
    if "basis" in basis:
        lines.append(
            ("Условия поставки: " if ru else "Delivery basis: ")
            + basis["basis"]
            + (
                (" до площадки Vector" if ru else " to the Vector site")
                if "destination_id" in basis
                else ""
            )
            + "."
        )
    reserve = terms.get("reserve_policy", {})
    if reserve.get("mode") == "none":
        lines.append(
            "Дополнительный резерв не включён." if ru else "No additional reserve is included."
        )
    elif reserve.get("mode") == "contingent":
        label = "Дополнительный резерв" if ru else "Additional reserve"
        if "quantity" in reserve:
            label += (
                ": "
                + _devices(reserve["quantity"], language)
                + (" сверх основного заказа" if ru else " outside the main order")
            )
        if "delivery_lot_id" in reserve:
            label += (
                ("; поставка вместе с партией «" if ru else "; delivered with the ")
                + labels[reserve["delivery_lot_id"]]
                + ("»" if ru else "")
            )
        lines.append(label + ".")
        if "use_cutoff" in reserve:
            lines.append(
                (
                    "Об использовании резерва нужно сообщить не позднее "
                    if ru
                    else "Report reserve use no later than "
                )
                + _display_date(reserve["use_cutoff"], language)
                + "."
            )
        if "unused_payable_on" in reserve:
            lines.append(
                ("Неиспользованный резерв оплачивается " if ru else "Unused reserve is payable on ")
                + _display_date(reserve["unused_payable_on"], language)
                + "."
            )
        if "unit_price_rule" in reserve and "minor_units" in price:
            quantity = scenario["supply_model"]["capabilities"]["main_quantity"]
            unit = (price["minor_units"] + quantity - 1) // quantity
            lines.append(
                (
                    "Цена оплачиваемого резервного устройства: "
                    if ru
                    else "Price per payable reserve device: "
                )
                + _money(unit, language)
                + "."
            )
        if "diagnosis_policy_id" in reserve:
            days = scenario["supply_model"]["reserve_rules"]["diagnosis_days"]
            lines.append(
                f"При подтверждённой аппаратной неисправности или ремонте замена бесплатна; исходное устройство остаётся у поставщика. Если подтверждена только причина на стороне покупателя, резерв оплачивается, а исходное устройство возвращается покупателю. Срок диагностики — {days} календарных дней после получения устройства поставщиком. Неподтверждённый диагноз до срока не создаёт платёж; по истечении срока замена бесплатна, исходное устройство остаётся у поставщика. Подтверждённая аппаратная неисправность имеет приоритет. Использованное вовремя устройство не включается в счёт за неиспользованный резерв. Позднее обращение не отменяет уже наступивший выкуп."
                if ru
                else f"A verified hardware fault or repair makes the replacement free; the supplier retains the original. A verified buyer-side cause without a hardware fault makes the reserve payable; the original returns to the buyer. Diagnosis is due within {days} calendar days after supplier receipt. An inconclusive diagnosis creates no payment before the deadline; at the deadline the replacement is free and the supplier retains the original. Verified hardware fault takes precedence. Timely used units are excluded from unused-reserve billing. A late claim does not reverse an unused-unit purchase."
            )
    if not unresolved_supply_terms(scenario, terms):
        summary = supply_financial_summary(scenario, terms)
        lines.append(
            (
                "Максимальная сумма с учётом оплаты всего резерва: "
                if ru
                else "Maximum total including all payable reserve units: "
            )
            + _money(summary["maximum_liability_minor"], language)
            + "."
        )
    return "\n".join(lines)
