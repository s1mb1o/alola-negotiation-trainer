"""Bounded package selection. Public proposals never authorize private-value leakage."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import Any

from .scenarios import (
    MAX_EXCHANGE_CANDIDATES,
    authored_opening,
    canonical_json,
    constraint_violations,
    evaluate_utility,
    validate_terms,
)

COOPERATIVE_POLICY_VERSION = "cooperative-v1"


@dataclass(frozen=True, slots=True)
class CounterProposal:
    terms: dict[str, Any]
    reason_code: str
    monetary_term_id: str | None = None
    trade_term_ids: tuple[str, ...] = ()


def _eligible(scenario: dict[str, Any], role: str, terms: dict[str, Any]) -> bool:
    if validate_terms(scenario, terms, complete=True):
        return False
    if any(constraint_violations(scenario, actor, terms) for actor in scenario["roles"]):
        return False
    reservation = scenario["utility_model"]["role_models"][role]["reservation_utility"]
    utility = evaluate_utility(scenario, role, terms)
    return math.isfinite(utility) and utility >= float(reservation)


def _monetary_direction(scenario: dict[str, Any], role: str, term_id: str) -> int | None:
    """Return the NPC's own monotonic preference. Never read another utility model."""

    function = scenario["utility_model"]["role_models"][role]["value_functions"].get(term_id)
    if not function or not function["weight"]:
        return None
    if function["type"] == "linear":
        change = float(function["utility_at_max"]) - float(function["utility_at_min"])
        return 1 if change > 0 else -1 if change < 0 else None
    if function["type"] == "piecewise_linear":
        utilities = [float(point[1]) for point in function["points"]]
        changes = [right - left for left, right in zip(utilities, utilities[1:])]
        if any(change > 0 for change in changes) and all(change >= 0 for change in changes):
            return 1
        if any(change < 0 for change in changes) and all(change <= 0 for change in changes):
            return -1
    return None


def _cooperative_counterproposal(
    scenario: dict[str, Any], role: str, received: dict[str, Any],
    monetary_term: str, direction: int, anchor: float | None,
) -> CounterProposal | None:
    """Prefer proximity to public terms. Never rank by the other actor's utility."""
    values = scenario.get("exchange_policy", {}).get("candidate_values", {})
    candidates = []
    if values and math.prod(len(items) for items in values.values()) <= MAX_EXCHANGE_CANDIDATES:
        keys = tuple(sorted(values))
        candidates.extend(
            {**received, **dict(zip(keys, combination))}
            for combination in product(*(values[key] for key in keys))
        )
        # Preserve the player's exact secondary terms when one change is sufficient.
        candidates.extend(
            {**received, term: value} for term, items in values.items() for value in items
        )
    if anchor is not None:
        candidates.append({
            **received, monetary_term: int(round((anchor + float(received[monetary_term])) / 2)),
        })
    choices = []
    definitions = scenario["terms"]["definitions"]
    for candidate in candidates:
        price = float(candidate[monetary_term])
        if anchor is not None and direction * (price - anchor) > 0:
            continue
        if direction * (price - float(received[monetary_term])) < 0:
            continue
        if not _eligible(scenario, role, candidate):
            continue
        changed = tuple(sorted(term for term in candidate if candidate[term] != received.get(term)))
        trades = tuple(term for term in changed if term != monetary_term)
        baseline = {**received, monetary_term: candidate[monetary_term]}
        baseline_utility = evaluate_utility(scenario, role, baseline)
        if not all(
            evaluate_utility(scenario, role, {**baseline, term: candidate[term]}) > baseline_utility
            for term in trades
        ):
            continue
        distance = sum(
            abs(float(candidate[term]) - float(received[term]))
            / max(1e-12, float(definitions[term]["value_schema"]["maximum"])
                  - float(definitions[term]["value_schema"]["minimum"]))
            for term in changed
        )
        rank = (distance, len(changed), -evaluate_utility(scenario, role, candidate),
                canonical_json(candidate))
        choices.append((rank, CounterProposal(
            candidate, "conditional_exchange" if trades else "cooperative_compromise",
            monetary_term, trades,
        )))
    return min(choices, key=lambda choice: choice[0])[1] if choices else None


def select_counterproposal(
    scenario: dict[str, Any],
    npc_role: str,
    received_terms: dict[str, Any],
    opening_terms: dict[str, Any],
    previous_counter_terms: dict[str, Any] | None = None,
    *,
    cooperative: bool = False,
) -> CounterProposal | None:
    """Select a complete exchange or a validated midpoint/previous public offer.

    The caller supplies only the NPC's own latest counteroffer as ``previous_counter_terms``.
    An incomplete received proposal returns ``None``. This function cannot fill an opening.
    The scenario's counterpart constraints are validators, not a utility-ranking input.
    """

    if validate_terms(scenario, received_terms, complete=True):
        return None
    monetary_term = next((term for term in ("price", "annual_rent") if term in received_terms), None)
    if monetary_term is None:
        return None
    direction = _monetary_direction(scenario, npc_role, monetary_term)
    if direction is None:
        return None
    opening_role, _kind, authored_terms = authored_opening(scenario)
    own_opening = opening_terms if opening_role == npc_role and opening_terms == authored_terms else None
    own_anchor = previous_counter_terms or own_opening
    anchor = float(own_anchor[monetary_term]) if own_anchor and monetary_term in own_anchor else None
    received_price = float(received_terms[monetary_term])

    if cooperative:
        compromise = _cooperative_counterproposal(
            scenario, npc_role, received_terms, monetary_term, direction, anchor,
        )
        if compromise is not None:
            return compromise

    def preserves_concession(terms: dict[str, Any]) -> bool:
        return anchor is None or direction * (float(terms[monetary_term]) - anchor) <= 0

    values = scenario.get("exchange_policy", {}).get("candidate_values", {})
    if monetary_term in values and math.prod(len(items) for items in values.values()) <= MAX_EXCHANGE_CANDIDATES:
        keys = tuple(sorted(values))
        choices: list[tuple[tuple[Any, ...], CounterProposal]] = []
        for combination in product(*(values[key] for key in keys)):
            candidate = {**received_terms, **dict(zip(keys, combination))}
            price = float(candidate[monetary_term])
            if not preserves_concession(candidate):
                continue
            # A previously published anchor must move towards the other participant.
            if anchor is not None and direction * (price - anchor) >= 0:
                continue
            if direction * (price - received_price) < 0:
                continue
            if not _eligible(scenario, npc_role, candidate):
                continue
            at_received_conditions = {**received_terms, monetary_term: candidate[monetary_term]}
            baseline_utility = evaluate_utility(scenario, npc_role, at_received_conditions)
            changed_terms = tuple(
                term for term in keys
                if term != monetary_term and candidate[term] != received_terms[term]
            )
            if not changed_terms:
                continue
            # Every named condition must demonstrably help the NPC at the selected price.
            if not all(
                evaluate_utility(scenario, npc_role, {**at_received_conditions, term: candidate[term]})
                > baseline_utility
                for term in changed_terms
            ):
                continue
            utility = evaluate_utility(scenario, npc_role, candidate)
            if utility <= baseline_utility:
                continue
            rank = (-utility, len(changed_terms), canonical_json(candidate))
            choices.append((rank, CounterProposal(candidate, "conditional_exchange", monetary_term, changed_terms)))
        if choices:
            return min(choices, key=lambda choice: choice[0])[1]

    # Preserve the prior midpoint strategy where it produces a bindable, acceptable package.
    midpoint_anchor = anchor
    if midpoint_anchor is None and monetary_term in opening_terms:
        midpoint_anchor = float(opening_terms[monetary_term])
    if midpoint_anchor is not None:
        midpoint = (received_price + midpoint_anchor) / 2
        price = max(received_price, min(midpoint_anchor, midpoint)) if direction > 0 else min(received_price, max(midpoint_anchor, midpoint))
        candidate = {**received_terms, monetary_term: int(round(price))}
        if preserves_concession(candidate) and _eligible(scenario, npc_role, candidate):
            return CounterProposal(candidate, "validated_midpoint", monetary_term)
    for previous in (previous_counter_terms, own_opening):
        if previous and preserves_concession(previous) and _eligible(scenario, npc_role, previous):
            return CounterProposal(dict(previous), "validated_own_offer", monetary_term)
    return None
