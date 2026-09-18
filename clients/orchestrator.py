"""External-agent self-play over the role-neutral natural-language API."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping
from uuid import uuid4

from .agent import NegotiationAgent, PROMPT_VERSION
from .api import (
    ApiError,
    NegotiationApiClient,
    new_idempotency_key,
    redact_secrets,
    response_revision,
    response_status,
)
from .providers import Generation, ProviderError, TextProvider, provider_seed_metadata


TERMINAL_STATUSES = {
    "agreement_reached",
    "walked_away",
    "expired",
    "aborted",
    "technical_failure",
}

RECOVERABLE_RECORDED_DOMAIN_ERRORS = {
    "offer_not_active",
    "offer_not_bindable",
    "offer_not_owned",
}

ADMIN_TOKEN_ENV = "NEGOTIATION_ADMIN_TOKEN"


@dataclass(slots=True)
class AgentSeat:
    role: str
    provider: TextProvider
    participant_token: str | None = None
    prompt_version: str = PROMPT_VERSION

    def participant_spec(self) -> dict[str, str]:
        return {
            "role": self.role,
            "controller": "external_agent",
            "provider": self.provider.config.provider,
            "model": self.provider.config.model,
            "prompt_version": self.prompt_version,
        }


def _session_id(response: Mapping[str, Any]) -> str:
    value = response.get("session_id") or response.get("id")
    if not isinstance(value, str) or not value:
        raise ApiError("Session creation did not return session_id")
    return value


def extract_participant_credentials(response: Mapping[str, Any]) -> dict[str, str]:
    """Read common credential envelopes without returning them to run output."""

    found: dict[str, str] = {}
    for container_key in ("participant_credentials", "credentials", "participant_tokens"):
        container = response.get(container_key)
        if isinstance(container, dict):
            for role, value in container.items():
                if isinstance(value, str):
                    found[str(role)] = value
                elif isinstance(value, dict):
                    token = (
                        value.get("participant_token")
                        or value.get("token")
                        or value.get("credential")
                    )
                    resolved_role = value.get("role") or role
                    if isinstance(token, str):
                        found[str(resolved_role)] = token
        elif isinstance(container, list):
            for item in container:
                if not isinstance(item, dict):
                    continue
                role = item.get("role")
                token = item.get("participant_token") or item.get("token") or item.get("credential")
                if isinstance(role, str) and isinstance(token, str):
                    found[role] = token
    return found


def extract_participant_roles(response: Mapping[str, Any]) -> dict[str, str]:
    """Map opaque participant IDs from the public create response to role IDs."""

    found: dict[str, str] = {}
    participants = response.get("participants")
    if isinstance(participants, list):
        for item in participants:
            if not isinstance(item, dict):
                continue
            participant_id = item.get("participant_id") or item.get("id")
            role = item.get("role")
            if isinstance(participant_id, str) and isinstance(role, str):
                found[participant_id] = role
    return found


def _role_for_actor(actor: Any, roles: set[str], participant_roles: Mapping[str, str]) -> str:
    if not isinstance(actor, str):
        raise ApiError("Active session response does not identify next_actor")
    if actor in roles:
        return actor
    if actor in participant_roles and participant_roles[actor] in roles:
        return participant_roles[actor]
    for role in roles:
        if actor == f"participant_{role}" or actor.endswith(f"_{role}"):
            return role
    raise ApiError(f"Cannot map next_actor {actor!r} to a configured role")


def _next_actor(response: Mapping[str, Any]) -> Any:
    if response.get("next_actor") is not None:
        return response.get("next_actor")
    observation = response.get("observation")
    if isinstance(observation, dict):
        return observation.get("next_actor")
    return None


def actor_safe_protocol_result(response: Mapping[str, Any]) -> dict[str, Any]:
    """Keep protocol fields while excluding the prior caller's observation."""

    allowed = {
        "result",
        "revision",
        "status",
        "next_actor",
        "round",
        "substantive_turn_count",
        "clarification",
        "pending_confirmation",
        "pending_offer_publication",
        "confirmation_kind",
        "negotiation_contract_version",
    }
    return {key: response[key] for key in allowed if key in response}


def _domain_error_identifier(exc: ApiError) -> str | None:
    for value in (exc.error, exc.code):
        if value in RECOVERABLE_RECORDED_DOMAIN_ERRORS:
            return value
    return None


def _clarification_question(error: str, language: str) -> str:
    questions = {
        "en": {
            "offer_not_active": (
                "That offer is no longer active. Restate your intent for the current negotiation state."
            ),
            "offer_not_bindable": (
                "That offer cannot be accepted as written. Clarify or propose a complete valid package."
            ),
            "offer_not_owned": (
                "Only the offer author can take that action. Clarify your intent for the current offer."
            ),
        },
        "ru": {
            "offer_not_active": (
                "Это предложение больше не активно. Уточните намерение с учетом текущего состояния переговоров."
            ),
            "offer_not_bindable": (
                "Это предложение нельзя принять в текущем виде. Уточните намерение или предложите полный допустимый пакет."
            ),
            "offer_not_owned": (
                "Это действие доступно только автору предложения. Уточните намерение относительно текущего предложения."
            ),
        },
    }
    selected = questions["ru"] if language.casefold() == "ru" else questions["en"]
    return selected[error]


def _recorded_domain_clarification(
    exc: ApiError,
    *,
    language: str,
    previous_revision: int,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Convert one known recorded domain error into an actor-safe retry state."""

    error = _domain_error_identifier(exc)
    payload = exc.details
    if error is None or not isinstance(payload, Mapping):
        return None
    revision = payload.get("revision")
    status = payload.get("status") or payload.get("session_status")
    if (
        not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision <= previous_revision
        or not isinstance(status, str)
        or "next_actor" not in payload
    ):
        return None
    next_actor = payload.get("next_actor")
    if next_actor is not None and not isinstance(next_actor, str):
        return None
    protocol_result = {
        "result": "clarification_required",
        "revision": revision,
        "status": status,
        "next_actor": next_actor,
        "clarification": {
            "reason_code": error,
            "question": _clarification_question(error, language),
            "source": "recorded_domain_error",
        },
    }
    api_result = {
        "recorded": True,
        "result": "clarification_required",
        "error": error,
        "revision": revision,
        "status": status,
        "next_actor": next_actor,
        "same_actor_retry": status not in TERMINAL_STATUSES,
    }
    return protocol_result, api_result


def _revision_conflict_state(
    exc: ApiError,
    participant_api: NegotiationApiClient,
    session_id: str,
    *,
    expected_revision: int,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Refetch the participant-scoped state after a conflict that followed a retried submit.

    A retried submit may have been committed server-side before its response was lost. The
    loop continues from the fresh state only when the session really moved past the revision
    that was submitted; an unexplained conflict stays a failure.
    """

    if "revision_conflict" not in {exc.error, exc.code}:
        return None
    try:
        observed = participant_api.get_session(session_id)
        observed_revision = response_revision(observed)
    except ApiError:
        return None
    if observed_revision <= expected_revision:
        return None
    api_result = {
        "recorded": None,
        "result": "revision_conflict",
        "error": "revision_conflict",
        "expected_revision": expected_revision,
        "revision": observed_revision,
        "status": response_status(observed),
        "next_actor": _next_actor(observed),
        "recovered_from_scoped_state": True,
    }
    return observed, api_result


def _safe_generation(generation: Generation, role: str, step: int) -> dict[str, Any]:
    return {
        "step": step,
        "role": role,
        "provider": generation.provider,
        "model": generation.model,
        "model_reported": generation.model_reported,
        "message": generation.text,
        "latency_ms": round(generation.latency_ms, 3),
        "usage": dict(generation.usage),
        "request_id": generation.request_id,
        "retry_count": generation.retry_count,
    }


class _MaxMessagesExceeded(RuntimeError):
    pass


def _seat_provenance(seat: AgentSeat) -> dict[str, Any]:
    return {
        "role": seat.role,
        "provider": seat.provider.config.provider,
        "model": seat.provider.config.model,
        "prompt_version": seat.prompt_version,
        "seed_handling": provider_seed_metadata(seat.provider),
    }


def _determinism_record(seats: list[AgentSeat]) -> dict[str, Any]:
    return {
        "reproducibility_guaranteed": False,
        "statement": "A provider seed can reduce sampling variance but does not guarantee identical output.",
        "seats": {seat.role: provider_seed_metadata(seat.provider) for seat in seats},
    }


def seat_seeds(seats: list[AgentSeat]) -> dict[str, int | None]:
    """Return the seed configured for each seat's provider."""

    return {seat.role: seat.provider.config.seed for seat in seats}


def _safe_api_error(exc: ApiError) -> dict[str, Any]:
    return {
        "message": str(exc),
        "status": exc.status,
        "code": exc.code,
        "backend_error": exc.error,
    }


def _capture_partial_history(
    api: NegotiationApiClient,
    session_id: str,
    seats: list[AgentSeat],
    fallback_revision: int,
) -> tuple[dict[str, Any], int, str | None]:
    histories: dict[str, Any] = {}
    revision = fallback_revision
    session_status: str | None = None
    for seat in seats:
        if not seat.participant_token:
            histories[seat.role] = {
                "unavailable": True,
                "error": "participant credential unavailable",
            }
            continue
        participant_api = api.with_participant_token(seat.participant_token)
        try:
            state = participant_api.get_session(session_id)
            revision = max(revision, response_revision(state))
            session_status = response_status(state)
        except ApiError:
            pass
        try:
            histories[seat.role] = participant_api.history(session_id)
            history = histories[seat.role]
            if isinstance(history, dict) and isinstance(history.get("revision"), int):
                revision = max(revision, int(history["revision"]))
        except ApiError as exc:
            histories[seat.role] = {"unavailable": True, **_safe_api_error(exc)}
    return histories, revision, session_status


def _try_close_failed_session(
    api: NegotiationApiClient,
    session_id: str,
    revision: int,
    session_status: str | None,
    failure_source: str,
) -> dict[str, Any]:
    if session_status in TERMINAL_STATUSES:
        return {
            "attempted": False,
            "closed": False,
            "reason": "session_already_terminal",
            "session_status": session_status,
        }
    admin_token = os.getenv(ADMIN_TOKEN_ENV)
    if not admin_token:
        return {
            "attempted": False,
            "closed": False,
            "reason": "admin_token_not_configured",
            "session_status": session_status,
        }
    try:
        response = api.close_session(
            session_id,
            expected_revision=revision,
            reason=f"Self-play stopped after {failure_source} failure.",
            admin_token=admin_token,
        )
        return {
            "attempted": True,
            "closed": response_status(response) in TERMINAL_STATUSES,
            "reason": "administrative_close_requested",
            "session_status": response_status(response),
            "revision": response_revision(response),
        }
    except ApiError as exc:
        return {
            "attempted": True,
            "closed": False,
            "reason": "administrative_close_failed",
            "session_status": session_status,
            "error": _safe_api_error(exc),
        }


def _failure_source(exc: BaseException) -> str:
    if isinstance(exc, ProviderError):
        return "provider"
    if isinstance(exc, ApiError):
        return "api"
    return "orchestrator_limit"


def _failure_record(exc: BaseException, failing_role: str | None) -> dict[str, Any]:
    failure: dict[str, Any] = {
        "source": _failure_source(exc),
        "type": type(exc).__name__,
        "message": str(exc),
        "failing_role": failing_role,
        "retry_count": int(getattr(exc, "retry_count", 0) or 0),
    }
    if isinstance(exc, ApiError):
        failure.update(status=exc.status, code=exc.code, backend_error=exc.error)
    if isinstance(exc, ProviderError):
        failure["provider_http_status"] = exc.status
        if exc.failure_diagnostics is not None:
            failure["failure_diagnostics"] = dict(exc.failure_diagnostics)
    return failure


def create_run_session(
    api: NegotiationApiClient,
    *,
    run_mode: str,
    admin_token: str | None,
    **session_fields: Any,
) -> dict[str, Any]:
    """Create the session; a benchmark session carries the administrator credential."""

    creator = api.with_participant_token(admin_token) if admin_token else api
    try:
        return creator.create_session(run_mode=run_mode, **session_fields)
    except ApiError as exc:
        if exc.status == 401 and run_mode == "benchmark":
            raise ApiError(
                message=(
                    f"Benchmark session creation was rejected ({exc.message}). "
                    f"Set {ADMIN_TOKEN_ENV} to the administrator token configured on the backend."
                ),
                status=exc.status,
                code=exc.code,
                error=exc.error,
                details=exc.details,
            ) from None
        raise


def run_self_play(
    api: NegotiationApiClient,
    *,
    scenario_id: str,
    scenario_version: int,
    language: str,
    seats: list[AgentSeat],
    max_messages: int = 40,
    run_mode: str = "benchmark",
    benchmark_run_id: str | None = None,
    trial_id: str | None = None,
    benchmark_expected_trials: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run a fresh two-seat session and return credential-free results."""

    if len(seats) != 2 or len({seat.role for seat in seats}) != 2:
        raise ValueError("Self-play requires exactly two distinct roles")
    if run_mode == "benchmark" and not benchmark_run_id:
        benchmark_run_id = f"bench_{uuid4().hex}"
    if run_mode == "benchmark" and not trial_id:
        trial_id = f"trial_{uuid4().hex}"
    if run_mode == "benchmark" and benchmark_expected_trials is None:
        benchmark_expected_trials = 1
    admin_token = os.getenv(ADMIN_TOKEN_ENV) if run_mode == "benchmark" else None
    created = create_run_session(
        api,
        run_mode=run_mode,
        admin_token=admin_token,
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        language=language,
        participants=[seat.participant_spec() for seat in seats],
        difficulty="normal",
        hints_enabled=False,
        benchmark_run_id=benchmark_run_id,
        trial_id=trial_id,
        benchmark_expected_trials=benchmark_expected_trials,
        seed=seed,
    )
    session_id = _session_id(created)
    current: Mapping[str, Any] = created
    revision = int(created.get("revision", 0))
    turns: list[dict[str, Any]] = []
    attempted_turn: dict[str, Any] | None = None
    failing_role: str | None = None
    last_actor_role: str | None = None

    def secrets() -> tuple[str, ...]:
        return tuple(seat.participant_token or "" for seat in seats) + (admin_token or "",)

    try:
        credentials = extract_participant_credentials(created)
        participant_roles = extract_participant_roles(created)
        by_role = {seat.role: seat for seat in seats}
        for seat in seats:
            failing_role = seat.role
            seat.participant_token = seat.participant_token or credentials.get(seat.role)
            if not seat.participant_token:
                raise ApiError(
                    f"No participant credential was delivered for role {seat.role!r}; "
                    "supply it through the orchestrator's secure configuration"
                )
        agents = {
            seat.role: NegotiationAgent(
                seat.provider,
                role=seat.role,
                language=language,
                prompt_version=seat.prompt_version,
            )
            for seat in seats
        }
        for step in range(1, max_messages + 1):
            status = response_status(current)
            if status in TERMINAL_STATUSES:
                break
            failing_role = _role_for_actor(_next_actor(current), set(by_role), participant_roles)
            seat = by_role[failing_role]
            participant_api = api.with_participant_token(seat.participant_token)
            scoped_state = participant_api.get_session(session_id)
            scoped_actor = _next_actor(scoped_state)
            if (
                scoped_actor is not None
                and _role_for_actor(scoped_actor, set(by_role), participant_roles) != failing_role
            ):
                raise ApiError("Participant-scoped state disagrees with the committed next_actor")
            revision = response_revision(scoped_state)
            history = participant_api.history(session_id)
            observation = scoped_state.get("observation", {})
            # The observation is passed on its own; the protocol state must not repeat it.
            protocol_state = {
                key: value for key, value in scoped_state.items() if key != "observation"
            }
            if failing_role == last_actor_role and current.get("result") in {
                "clarification_required",
                "confirmation_required",
            }:
                protocol_state.update(actor_safe_protocol_result(current))
            generation = agents[failing_role].generate_turn(
                observation=observation,
                history=history,
                protocol_result=protocol_state,
            )
            attempted_turn = _safe_generation(generation, failing_role, step)
            # One key per generated message: a transport retry reuses it, so an ambiguous
            # submit that the server already committed returns the stored result.
            idempotency_key = new_idempotency_key()
            try:
                current = participant_api.submit_message(
                    session_id,
                    generation.text,
                    expected_revision=revision,
                    idempotency_key=idempotency_key,
                )
            except ApiError as exc:
                api_retry_count = int(getattr(participant_api, "last_retry_count", 0) or 0)
                attempted_turn["api_retry_count"] = api_retry_count
                conflict = (
                    _revision_conflict_state(
                        exc, participant_api, session_id, expected_revision=revision
                    )
                    if api_retry_count > 0
                    else None
                )
                if conflict is not None:
                    observed_state, api_result = conflict
                    api_result["ambiguous_submit"] = api_retry_count > 0
                    revision = response_revision(observed_state)
                    attempted_turn["api_result"] = api_result
                    turns.append(attempted_turn)
                    attempted_turn = None
                    last_actor_role = failing_role
                    current = observed_state
                    continue
                recovery = _recorded_domain_clarification(
                    exc,
                    language=language,
                    previous_revision=revision,
                )
                if recovery is None:
                    raise
                recovered_current, api_result = recovery
                recovered_status = response_status(recovered_current)
                if recovered_status not in TERMINAL_STATUSES:
                    try:
                        recovered_role = _role_for_actor(
                            _next_actor(recovered_current), set(by_role), participant_roles
                        )
                    except ApiError:
                        raise exc
                    if recovered_role != failing_role:
                        raise exc
                revision = response_revision(recovered_current)
                attempted_turn["api_result"] = api_result
                turns.append(attempted_turn)
                attempted_turn = None
                last_actor_role = failing_role
                current = recovered_current
                continue
            attempted_turn["api_retry_count"] = int(
                getattr(participant_api, "last_retry_count", 0) or 0
            )
            revision = response_revision(current)
            turns.append(attempted_turn)
            attempted_turn = None
            last_actor_role = failing_role

        final_status = response_status(current)
        if final_status not in TERMINAL_STATUSES:
            try:
                failing_role = _role_for_actor(
                    _next_actor(current), set(by_role), participant_roles
                )
            except ApiError:
                failing_role = None
            raise _MaxMessagesExceeded(
                f"Self-play exceeded max_messages={max_messages} while session remained "
                f"{final_status}"
            )
    except (ApiError, ProviderError, _MaxMessagesExceeded) as exc:
        source = _failure_source(exc)
        histories, revision, observed_status = _capture_partial_history(
            api, session_id, seats, revision
        )
        close_result = _try_close_failed_session(
            api,
            session_id,
            revision,
            observed_status or response_status(current),
            source,
        )
        if close_result.get("closed"):
            histories, revision, observed_status = _capture_partial_history(
                api, session_id, seats, int(close_result.get("revision", revision))
            )
        return redact_secrets(
            {
                "benchmark_run_id": benchmark_run_id,
                "trial_id": trial_id,
                "benchmark_expected_trials": benchmark_expected_trials,
                "seed": seed,
                "seat_seeds": seat_seeds(seats),
                "determinism": _determinism_record(seats),
                "session_id": session_id,
                "scenario_id": scenario_id,
                "scenario_version": scenario_version,
                "language": language,
                "seats": [_seat_provenance(seat) for seat in seats],
                "status": "technical_failure",
                "partial": True,
                "session_status": close_result.get("session_status")
                or observed_status
                or response_status(current),
                "revision": revision,
                "failing_role": failing_role,
                "failure": _failure_record(exc, failing_role),
                "turns": turns,
                "attempted_turn": attempted_turn,
                "history": histories.get(seats[0].role),
                "history_by_role": histories,
                "administrative_close": close_result,
            },
            secrets(),
        )

    reviews: dict[str, Any] = {}
    histories: dict[str, Any] = {}
    for seat in seats:
        review_client = api.with_participant_token(seat.participant_token)
        try:
            reviews[seat.role] = review_client.review(session_id)
        except ApiError as exc:
            reviews[seat.role] = {
                "unavailable": True,
                "error": str(exc),
                "status": exc.status,
                "code": exc.code,
                "backend_error": exc.error,
            }
        try:
            histories[seat.role] = review_client.history(session_id)
        except ApiError as exc:
            histories[seat.role] = {
                "unavailable": True,
                "error": str(exc),
                "status": exc.status,
                "code": exc.code,
                "backend_error": exc.error,
            }
    return redact_secrets(
        {
            "benchmark_run_id": benchmark_run_id,
            "trial_id": trial_id,
            "benchmark_expected_trials": benchmark_expected_trials,
            "seed": seed,
            "seat_seeds": seat_seeds(seats),
            "determinism": _determinism_record(seats),
            "session_id": session_id,
            "scenario_id": scenario_id,
            "scenario_version": scenario_version,
            "language": language,
            "seats": [_seat_provenance(seat) for seat in seats],
            "status": final_status,
            "revision": revision,
            "turns": turns,
            "history": histories[seats[0].role],
            "history_by_role": histories,
            "review": reviews[seats[0].role],
            "reviews_by_role": reviews,
        },
        secrets(),
    )
