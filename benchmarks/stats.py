"""Credential-free aggregate statistics for benchmark run records."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import fmean
from typing import Any, Iterable, Mapping


def _model_key(seat: Mapping[str, Any]) -> str:
    return f"{seat.get('provider', 'unknown')}:{seat.get('model', 'unknown')}"


def _agreement(run: Mapping[str, Any]) -> bool:
    review = run.get("review")
    if isinstance(review, dict):
        outcome = review.get("outcome")
        if isinstance(outcome, dict) and isinstance(outcome.get("agreement"), bool):
            return bool(outcome["agreement"])
    return run.get("status") == "agreement_reached"


def _role_review(run: Mapping[str, Any], role: str) -> Mapping[str, Any] | None:
    reviews = run.get("reviews_by_role")
    if isinstance(reviews, dict) and isinstance(reviews.get(role), dict):
        return reviews[role]
    review = run.get("review")
    return review if isinstance(review, dict) else None


def _role_utility(run: Mapping[str, Any], role: str) -> float | None:
    review = _role_review(run, role)
    if review is None:
        return None
    outcome = review.get("outcome")
    if not isinstance(outcome, dict):
        return None
    utilities = outcome.get("participant_utilities")
    value = (
        utilities.get(role) if isinstance(utilities, dict) else outcome.get("participant_utility")
    )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _role_score(run: Mapping[str, Any], role: str, name: str) -> float | None:
    review = _role_review(run, role)
    if review is None:
        return None
    scores = review.get("scores")
    value = scores.get(name) if isinstance(scores, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _turn_tokens(usage: Any) -> float:
    if not isinstance(usage, dict):
        return 0.0
    total = usage.get("total_tokens")
    if isinstance(total, (int, float)) and not isinstance(total, bool):
        return float(total)
    pairs = (("input_tokens", "output_tokens"), ("prompt_tokens", "completion_tokens"))
    for left, right in pairs:
        values = [usage.get(left), usage.get(right)]
        if any(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            return sum(
                float(value)
                for value in values
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            )
    return 0.0


def _telemetry_turns(run: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return committed turns plus one distinct in-flight generation."""

    raw_turns = run.get("turns")
    records = (
        [turn for turn in raw_turns if isinstance(turn, Mapping)]
        if isinstance(raw_turns, list)
        else []
    )
    attempted = run.get("attempted_turn")
    if isinstance(attempted, Mapping) and not any(attempted == turn for turn in records):
        records.append(attempted)
    return records


def aggregate_model_stats(runs: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate model outcomes, role splits, latency, and token usage."""

    run_list = list(runs)
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    utilities: dict[str, list[float]] = defaultdict(list)
    outcomes: dict[str, list[float]] = defaultdict(list)
    skills: dict[str, list[float]] = defaultdict(list)
    latencies: dict[str, list[float]] = defaultdict(list)
    tokens: dict[str, float] = defaultdict(float)
    turns: dict[str, int] = defaultdict(int)
    role_runs: dict[str, Counter[str]] = defaultdict(Counter)
    role_utilities: dict[tuple[str, str], list[float]] = defaultdict(list)
    technical_failure_runs = 0
    failure_sources: Counter[str] = Counter()
    outcome_run_count = 0

    for run in run_list:
        agreement = _agreement(run)
        status = str(run.get("status", "unknown"))
        technical_failure = status == "technical_failure"
        failure = run.get("failure")
        failure_source = (
            str(failure.get("source", "unknown")) if isinstance(failure, dict) else "unknown"
        )
        failing_role = run.get("failing_role")
        if failing_role is None and isinstance(failure, dict):
            failing_role = failure.get("failing_role")
        if technical_failure:
            technical_failure_runs += 1
            failure_sources[failure_source] += 1
        else:
            outcome_run_count += 1
        seats = run.get("seats")
        if not isinstance(seats, list):
            seats = []
        role_models: dict[str, str] = {}
        for seat in seats:
            if not isinstance(seat, dict):
                continue
            role = str(seat.get("role", "unknown"))
            model_key = _model_key(seat)
            role_models[role] = model_key
            counters[model_key]["runs"] += 1
            role_runs[model_key][role] += 1
            if technical_failure:
                if failure_source in {"provider", "agent"} and role == failing_role:
                    counters[model_key]["provider_failures"] += 1
                    role_runs[model_key][f"failure:{role}"] += 1
                continue
            counters[model_key]["outcome_runs"] += 1
            counters[model_key]["agreements"] += int(agreement)
            counters[model_key][f"status:{status}"] += 1
            role_runs[model_key][f"outcome:{role}"] += 1
            utility = _role_utility(run, role)
            if utility is not None:
                utilities[model_key].append(utility)
                role_utilities[(model_key, role)].append(utility)
            outcome_score = _role_score(run, role, "outcome_score")
            if outcome_score is not None:
                outcomes[model_key].append(outcome_score)
            skill_score = _role_score(run, role, "skill_score")
            if skill_score is not None:
                skills[model_key].append(skill_score)
        for turn in _telemetry_turns(run):
            role = str(turn.get("role", "unknown"))
            model_key = (
                role_models.get(role)
                or f"{turn.get('provider', 'unknown')}:{turn.get('model', 'unknown')}"
            )
            turns[model_key] += 1
            latency = turn.get("latency_ms")
            if isinstance(latency, (int, float)) and not isinstance(latency, bool):
                latencies[model_key].append(float(latency))
            tokens[model_key] += _turn_tokens(turn.get("usage"))

    model_stats: dict[str, Any] = {}
    for model_key in sorted(counters):
        counts = counters[model_key]
        run_count = counts["runs"]
        roles: dict[str, Any] = {}
        for role, count in sorted(role_runs[model_key].items()):
            if role.startswith(("failure:", "outcome:")):
                continue
            role_values = role_utilities[(model_key, role)]
            roles[role] = {
                "runs": count,
                "seat_assignments": count,
                "outcome_runs": role_runs[model_key][f"outcome:{role}"],
                "provider_failures": role_runs[model_key][f"failure:{role}"],
                "mean_utility": round(fmean(role_values), 4) if role_values else None,
            }
        outcome_runs = counts["outcome_runs"]
        # The mean of the per-role means gives each role equal weight even when a model
        # completed more outcome runs in one role than in the other.
        role_mean_utilities = [
            fmean(role_utilities[(model_key, role)])
            for role in roles
            if role_utilities[(model_key, role)]
        ]
        model_stats[model_key] = {
            "runs": run_count,
            "seat_assignments": run_count,
            "outcome_runs": outcome_runs,
            "provider_failures": counts["provider_failures"],
            "agreements": counts["agreements"],
            "agreement_rate": round(counts["agreements"] / outcome_runs, 4)
            if outcome_runs
            else None,
            "mean_utility": round(fmean(utilities[model_key]), 4) if utilities[model_key] else None,
            "mean_utility_role_balanced": round(fmean(role_mean_utilities), 4)
            if role_mean_utilities
            else None,
            "mean_outcome_score": round(fmean(outcomes[model_key]), 4)
            if outcomes[model_key]
            else None,
            "mean_skill_score": round(fmean(skills[model_key]), 4) if skills[model_key] else None,
            "turns": turns[model_key],
            "mean_turn_latency_ms": round(fmean(latencies[model_key]), 3)
            if latencies[model_key]
            else None,
            "total_tokens": round(tokens[model_key], 3),
            "status_counts": {
                key.removeprefix("status:"): value
                for key, value in sorted(counts.items())
                if key.startswith("status:")
            },
            "roles": roles,
        }
    return {
        "run_count": len(run_list),
        "negotiation_outcome_run_count": outcome_run_count,
        "technical_failure_runs": technical_failure_runs,
        "failure_source_counts": dict(sorted(failure_sources.items())),
        "models": model_stats,
    }
