"""Multi-model, role-swapped negotiation benchmark runner."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Iterable
from uuid import uuid4

from clients.agent import PROMPT_VERSION
from clients.api import (
    ApiError,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    NegotiationApiClient,
    redact_secrets,
)
from clients.orchestrator import ADMIN_TOKEN_ENV, AgentSeat, run_self_play, seat_seeds
from clients.providers import ProviderError, provider_for, provider_seed_metadata

from .stats import aggregate_model_stats


BASELINE_MODELS = ("openai:gpt-5.6-luna", "qwen:qwen3.7-plus")
EXTENDED_MODELS = ("openai:gpt-5.6-terra", "qwen:qwen3.8-max")

# Each seat samples with its own seed: trial seed + seat offset. Trial seeds advance by the
# number of seats so that no two seats in one run share a seed.
SEAT_SEED_OFFSETS = {"buyer": 0, "seller": 1}
SEATS_PER_TRIAL = len(SEAT_SEED_OFFSETS)


@dataclass(frozen=True, slots=True)
class ModelSpec:
    provider: str
    model: str

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}"


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    scenario_id: str
    version: int
    language: str


def parse_model_spec(value: str) -> ModelSpec:
    provider, separator, model = value.partition(":")
    if not separator or not provider or not model:
        raise ValueError(f"Invalid model spec {value!r}; use PROVIDER:MODEL")
    provider = provider.lower()
    if provider not in {"openai", "qwen"}:
        raise ValueError(f"Unsupported benchmark provider: {provider}")
    return ModelSpec(provider, model)


def parse_scenario_spec(value: str) -> ScenarioSpec:
    parts = value.split(":")
    if len(parts) > 3 or not parts[0]:
        raise ValueError(f"Invalid scenario spec {value!r}; use ID[:VERSION[:LANGUAGE]]")
    scenario_id = parts[0]
    version = int(parts[1]) if len(parts) >= 2 and parts[1] else 1
    language = (
        parts[2]
        if len(parts) == 3 and parts[2]
        else ("en" if scenario_id.endswith("_en") else "ru")
    )
    if language not in {"ru", "en"}:
        raise ValueError("Scenario language must be ru or en")
    return ScenarioSpec(scenario_id, version, language)


def comparison_pairs(models: list[ModelSpec]) -> list[tuple[ModelSpec, ModelSpec]]:
    if not models:
        raise ValueError("At least one model is required")
    if len(models) == 1:
        return [(models[0], models[0])]
    pairs: list[tuple[ModelSpec, ModelSpec]] = []
    for left_index, left in enumerate(models):
        for right in models[left_index + 1 :]:
            pairs.extend(((left, right), (right, left)))
    return pairs


def _write_json(path: Path, value: Any) -> None:
    safe = redact_secrets(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(safe, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _deferred_review_result(
    api: NegotiationApiClient,
    result: dict[str, Any],
    seats: list[AgentSeat],
) -> None:
    """Refresh actor-safe final projections after the complete run set is terminal."""

    session_id = result.get("session_id")
    if not isinstance(session_id, str):
        return
    reviews: dict[str, Any] = {}
    histories: dict[str, Any] = {}
    for seat in seats:
        if not seat.participant_token:
            reviews[seat.role] = {"unavailable": True, "error": "credential unavailable"}
            histories[seat.role] = {"unavailable": True, "error": "credential unavailable"}
            continue
        participant_api = api.with_participant_token(seat.participant_token)
        try:
            reviews[seat.role] = participant_api.review(session_id)
        except ApiError as exc:
            reviews[seat.role] = {
                "unavailable": True,
                "error": str(exc),
                "status": exc.status,
                "code": exc.code,
                "backend_error": exc.error,
            }
        try:
            histories[seat.role] = participant_api.history(session_id)
        except ApiError as exc:
            histories[seat.role] = {
                "unavailable": True,
                "error": str(exc),
                "status": exc.status,
                "code": exc.code,
                "backend_error": exc.error,
            }
    result["review"] = reviews.get(seats[0].role)
    result["reviews_by_role"] = reviews
    result["history"] = histories.get(seats[0].role)
    result["history_by_role"] = histories


def run_benchmark(
    api: NegotiationApiClient,
    *,
    scenarios: Iterable[ScenarioSpec],
    models: list[ModelSpec],
    repetitions: int,
    seed: int,
    max_messages: int,
    output_dir: Path,
    benchmark_run_id: str,
    openai_key_env: str = "OPENAI_API_KEY",
    qwen_key_env: str = "QWEN_API_KEY",
    max_output_tokens: int = 500,
    temperature: float | None = None,
    provider_timeout: float = 60.0,
    provider_max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    provider_retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> dict[str, Any]:
    """Run fresh role-swapped trials and write safe per-trial records."""

    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    if provider_max_attempts < 1:
        raise ValueError("provider_max_attempts must be at least 1")
    scenario_list = list(scenarios)
    if not scenario_list:
        raise ValueError("At least one scenario is required")
    runs: list[dict[str, Any]] = []
    review_contexts: list[tuple[dict[str, Any], list[AgentSeat], str]] = []
    trial_number = 0
    pairs = comparison_pairs(models)
    expected_trials = len(scenario_list) * repetitions * len(pairs)
    generation_configuration = {
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
        "temperature_handling": "explicit" if temperature is not None else "provider_default",
        "provider_timeout_seconds": provider_timeout,
        "provider_max_attempts": provider_max_attempts,
        "provider_retry_backoff_seconds": provider_retry_backoff_seconds,
        "prompt_version": PROMPT_VERSION,
    }
    for scenario in scenario_list:
        for repetition in range(1, repetitions + 1):
            for buyer_spec, seller_spec in pairs:
                trial_number += 1
                trial_id = f"{benchmark_run_id}_t{trial_number:04d}"
                trial_seed = seed + (trial_number - 1) * SEATS_PER_TRIAL
                buyer = provider_for(
                    buyer_spec.provider,
                    model=buyer_spec.model,
                    api_key_env=openai_key_env if buyer_spec.provider == "openai" else qwen_key_env,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    seed=trial_seed + SEAT_SEED_OFFSETS["buyer"],
                    timeout=provider_timeout,
                    max_attempts=provider_max_attempts,
                    retry_backoff_seconds=provider_retry_backoff_seconds,
                )
                seller = provider_for(
                    seller_spec.provider,
                    model=seller_spec.model,
                    api_key_env=openai_key_env
                    if seller_spec.provider == "openai"
                    else qwen_key_env,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    seed=trial_seed + SEAT_SEED_OFFSETS["seller"],
                    timeout=provider_timeout,
                    max_attempts=provider_max_attempts,
                    retry_backoff_seconds=provider_retry_backoff_seconds,
                )
                seats = [AgentSeat("buyer", buyer), AgentSeat("seller", seller)]
                try:
                    result = run_self_play(
                        api,
                        scenario_id=scenario.scenario_id,
                        scenario_version=scenario.version,
                        language=scenario.language,
                        seats=seats,
                        max_messages=max_messages,
                        run_mode="benchmark",
                        benchmark_run_id=benchmark_run_id,
                        trial_id=trial_id,
                        benchmark_expected_trials=expected_trials,
                        seed=trial_seed,
                    )
                except (ApiError, ProviderError) as exc:
                    if isinstance(exc, ApiError) and exc.status == 401:
                        # Every trial would fail the same way: stop the run with a clear message.
                        raise ApiError(
                            "Benchmark session creation requires the administrator credential. "
                            f"Set {ADMIN_TOKEN_ENV} to the token configured on the backend. "
                            f"Original error: {exc}",
                            status=exc.status,
                            code=exc.code,
                            error=exc.error,
                        ) from None
                    message = str(exc)
                    if isinstance(exc, ApiError) and exc.status in {400, 422}:
                        message = (
                            "The backend rejected the benchmark contract. It must accept "
                            "benchmark_run_id, trial_id, seed, and participant "
                            f"provider/model/prompt_version metadata. Original error: {exc}"
                        )
                    source = "provider" if isinstance(exc, ProviderError) else "api"
                    result = {
                        "benchmark_run_id": benchmark_run_id,
                        "trial_id": trial_id,
                        "seed": trial_seed,
                        "seat_seeds": seat_seeds(seats),
                        "determinism": {
                            "reproducibility_guaranteed": False,
                            "statement": "A provider seed can reduce sampling variance but does not guarantee identical output.",
                            "seats": {
                                seat.role: provider_seed_metadata(seat.provider) for seat in seats
                            },
                        },
                        "session_id": None,
                        "scenario_id": scenario.scenario_id,
                        "scenario_version": scenario.version,
                        "language": scenario.language,
                        "seats": [
                            {
                                "role": seat.role,
                                "provider": seat.provider.config.provider,
                                "model": seat.provider.config.model,
                                "prompt_version": seat.prompt_version,
                                "seed_handling": provider_seed_metadata(seat.provider),
                            }
                            for seat in seats
                        ],
                        "status": "technical_failure",
                        "partial": True,
                        "session_status": None,
                        "failing_role": None,
                        "turns": [],
                        "attempted_turn": None,
                        "history": None,
                        "history_by_role": {},
                        "failure": {
                            "source": source,
                            "type": type(exc).__name__,
                            "message": message,
                            "failing_role": None,
                            "status": exc.status if isinstance(exc, ApiError) else None,
                            "code": exc.code if isinstance(exc, ApiError) else None,
                            "backend_error": exc.error if isinstance(exc, ApiError) else None,
                            "retry_count": int(getattr(exc, "retry_count", 0) or 0),
                            "failure_diagnostics": getattr(exc, "failure_diagnostics", None),
                        },
                        "administrative_close": {
                            "attempted": False,
                            "closed": False,
                            "reason": "session_not_created_or_unknown",
                        },
                    }
                result["generation_configuration"] = dict(generation_configuration)
                runs.append(result)
                review_contexts.append((result, seats, trial_id))
                _write_json(output_dir / "trials" / f"{trial_id}.json", result)
    for result, seats, trial_id in review_contexts:
        _deferred_review_result(api, result, seats)
        _write_json(output_dir / "trials" / f"{trial_id}.json", result)
    local_stats = aggregate_model_stats(runs)
    try:
        backend_stats: Any = api.stats()
    except ApiError as exc:
        backend_stats = {
            "unavailable": True,
            "error": str(exc),
            "status": exc.status,
            "code": exc.code,
            "backend_error": exc.error,
        }
    summary = {
        "benchmark_run_id": benchmark_run_id,
        "configuration": {
            "models": [model.key for model in models],
            "scenarios": [
                {
                    "id": scenario.scenario_id,
                    "version": scenario.version,
                    "language": scenario.language,
                }
                for scenario in scenario_list
            ],
            "repetitions": repetitions,
            "expected_trials": expected_trials,
            "seed_schedule": {
                "base_seed": seed,
                "increment_per_trial": SEATS_PER_TRIAL,
                "seat_seed_offsets": dict(SEAT_SEED_OFFSETS),
                "provider_parameter_sent_only_when_supported": True,
                "reproducibility_guaranteed": False,
            },
            "max_messages": max_messages,
            "generation": generation_configuration,
        },
        "local_stats": local_stats,
        "backend_stats": backend_stats,
        "failed_trials": sum(run.get("status") == "technical_failure" for run in runs),
        "trial_ids": [run.get("trial_id") for run in runs],
    }
    _write_json(output_dir / "summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default=None, help="Negotiation API base URL (default: http://127.0.0.1:8170)"
    )
    parser.add_argument(
        "--scenario",
        action="append",
        required=True,
        help="ID[:VERSION[:LANGUAGE]]; repeat as needed",
    )
    parser.add_argument("--model", action="append", help="PROVIDER:MODEL; repeat as needed")
    parser.add_argument("--include-extended-defaults", action="store_true")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--seed",
        type=int,
        default=1729,
        help="Base sampling seed where supported; identical outputs are not guaranteed",
    )
    parser.add_argument("--max-messages", type=int, default=40)
    parser.add_argument("--max-output-tokens", type=int, default=500)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--api-timeout", type=float, default=30.0)
    parser.add_argument("--provider-timeout", type=float, default=60.0)
    parser.add_argument(
        "--provider-max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help="Attempts per provider call for rate limits, 5xx, timeouts, and connection errors",
    )
    parser.add_argument(
        "--provider-retry-backoff",
        type=float,
        default=DEFAULT_RETRY_BACKOFF_SECONDS,
        help="Base backoff in seconds between provider attempts (doubles per attempt)",
    )
    parser.add_argument("--openai-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--qwen-key-env", default="QWEN_API_KEY")
    parser.add_argument("--benchmark-run-id")
    parser.add_argument("--output-dir")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        raw_models = list(args.model or BASELINE_MODELS)
        if args.include_extended_defaults:
            raw_models.extend(EXTENDED_MODELS)
        models = [parse_model_spec(value) for value in dict.fromkeys(raw_models)]
        scenarios = [parse_scenario_spec(value) for value in args.scenario]
        benchmark_run_id = args.benchmark_run_id or f"bench_{uuid4().hex}"
        output_dir = (
            Path(args.output_dir or f"benchmark-results/{benchmark_run_id}").expanduser().resolve()
        )
        api = NegotiationApiClient(args.base_url, timeout=args.api_timeout)
        summary = run_benchmark(
            api,
            scenarios=scenarios,
            models=models,
            repetitions=args.repetitions,
            seed=args.seed,
            max_messages=args.max_messages,
            output_dir=output_dir,
            benchmark_run_id=benchmark_run_id,
            openai_key_env=args.openai_key_env,
            qwen_key_env=args.qwen_key_env,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
            provider_timeout=args.provider_timeout,
            provider_max_attempts=args.provider_max_attempts,
            provider_retry_backoff_seconds=args.provider_retry_backoff,
        )
        print(json.dumps(redact_secrets(summary), ensure_ascii=False, indent=2, sort_keys=True))
        print(f"summary: {output_dir / 'summary.json'}")
        return 0
    except (ApiError, ProviderError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
