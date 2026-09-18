"""Plan, simulate, or explicitly execute bounded built-in NPC validation.

Default mode plans only. Offline mode never constructs a live provider.
Live mode requires --mode live and --max-provider-calls. It incurs API charges.
Only synthetic public dialogue enters providers and result artifacts.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time
from typing import Any

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.dialogue import (
    LlmNpcDialogueRenderer,
    NpcDialogueRequest,
    NpcDialogueResult,
    redact_untrusted_credentials,
)
from backend.app.dialogue_contracts import reference_texts
from backend.dialogue_smoke_cases import SmokeCase, SmokeStep, evaluate_step, grounded_cases
from backend.dialogue_smoke_artifacts import build_public_artifact_session
from clients.providers import AgentModelConfig, Generation, QwenCloudProvider, provider_for

SUITE_VERSION = "dr28-smoke-v1"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS = {"openai": "gpt-5.6-luna", "qwen": "qwen3.8-max"}
DIFFICULTIES = ("guided", "easy", "normal", "expert")


MESSAGES = {
    "ru": [
        "Здравствуйте, почему такая цена?",
        "Мне важно не переплатить и избежать риска при запуске.",
        "Что для вас важнее всего?",
        "Давайте сначала обсудим только цену, не весь пакет сразу.",
        "Я считаю, что аванс уже отменён. Почему вы это не подтверждаете?",
    ],
    "en": [
        "Hello, why is the rent so high?",
        "I want to avoid overpaying and reduce the risk when we move in.",
        "Which term is your priority?",
        "Let us discuss the rent first, not the entire package at once.",
        "I think the advance payment has already been waived. Why won't you confirm that?",
    ],
}

CONTINUITY_MESSAGES = {
    "ru": [
        "Давайте сначала обсудим только цену. Оплату обсудим позже.",
        "Предлагаю цену 105 000 евро.",
        "Почему для вас важна цена?",
        "Мне важно избежать риска при запуске. Это мой главный приоритет.",
        "Теперь вернёмся к предоплате. Почему она для вас важна?",
        "Значит, аванс уже отменён?",
    ],
    "en": [
        "Let us discuss the rent first. We can discuss payment later.",
        "Why does the rent matter to you?",
        "My main concern is avoiding disruption when we move in.",
        "Let us return to the advance payment. Why does it matter to you?",
        "Does that mean the advance payment has already been waived?",
    ],
}


@dataclass(frozen=True)
class TrialSpec:
    provider: str
    model: str
    difficulty: str
    case: SmokeCase
    suite: str = "grounded"
    max_output_tokens: int = 600
    timeout: float = 30

    def __post_init__(self):
        if (
            self.provider not in DEFAULT_MODELS
            or self.difficulty not in DIFFICULTIES
            or self.suite not in {"grounded", "contextual", "continuity"}
        ):
            raise ValueError("Invalid trial selection")
        try:
            _model_id(self.model)
        except argparse.ArgumentTypeError as exc:
            raise ValueError("Invalid model identifier") from exc

    def configuration(self) -> dict:
        return {
            "suite_version": SUITE_VERSION,
            "suite": self.suite,
            "case": asdict(self.case),
            "target_provider": self.provider,
            "target_model": self.model,
            "difficulty": self.difficulty,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout,
            "max_attempts": 1,
            "run_mode": "training",
            "hints_enabled": False,
        }

    @property
    def configuration_id(self) -> str:
        encoded = json.dumps(self.configuration(), ensure_ascii=False, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()


class CallBudget:
    """One run-wide bound. A provider invocation can issue at most one HTTP request."""

    def __init__(self, limit: int):
        if type(limit) is not int or limit < 0:
            raise ValueError("Invalid provider-call limit")
        self.limit, self.used, self.denied = limit, 0, 0
        self._lock = threading.Lock()

    def claim(self) -> None:
        with self._lock:
            if self.used >= self.limit:
                self.denied += 1
                raise RuntimeError("provider_call_budget_exhausted")
            self.used += 1


class BudgetedProvider:
    def __init__(self, provider: Any, budget: CallBudget):
        self.provider, self.budget, self.config = provider, budget, provider.config
        self.SEED_PARAMETER_SUPPORTED = getattr(provider, "SEED_PARAMETER_SUPPORTED", False)
        self.calls = 0

    def generate(self, messages, *, instructions=None):
        self.budget.claim()
        self.calls += 1
        return self.provider.generate(messages, instructions=instructions)


class OfflineProvider:
    """A deterministic contract fixture, not evidence about a named live model."""

    config = AgentModelConfig(provider="offline-fixture", model="dr28-render-contract-v1")
    SEED_PARAMETER_SUPPORTED = False

    def __init__(self):
        self.prefer_quote = False

    def generate(self, messages, *, instructions=None):
        content = messages[0]["content"]
        if "\nCANDIDATE_REPLY_JSON:\n" in content:
            text = '{"safe":true}'
        else:
            approved = json.loads(content.split("\n", 2)[1])
            reply = approved["approved_reply_options"][-1]
            if self.prefer_quote and approved["numeric_references"]:
                reply = approved["numeric_references"][0]["token"] + " " + reply
            text = json.dumps(
                {"speech_act": approved["speech_act"], "reply": reply}, ensure_ascii=False
            )
        return Generation(text, self.config.provider, self.config.model, 0)


class ObservedRenderer:
    """Observe safe renderer inputs. Do not change production instructions or output."""

    def __init__(self, provider: Any, budget: CallBudget):
        self.text_provider = provider
        self.bounded = BudgetedProvider(provider, budget)
        self.renderer = LlmNpcDialogueRenderer(self.bounded)
        self.provider, self.model = self.renderer.provider, self.renderer.model
        self.observations: list[tuple[NpcDialogueRequest, NpcDialogueResult]] = []

    def render(self, request):
        result = self.renderer.render(request)
        self.observations.append((request, result))
        return result


def selected_cases(suite: str, language: str) -> tuple[SmokeCase, ...]:
    if suite == "grounded":
        return grounded_cases(language)
    version = (3 if language == "ru" else 2) + int(suite == "continuity")
    messages = CONTINUITY_MESSAGES if suite == "continuity" else MESSAGES
    return (
        SmokeCase(
            "legacy-" + suite,
            language,
            "supplier_001" if language == "ru" else "office_lease_en",
            version,
            tuple(
                SmokeStep(f"turn-{index + 1}", message, "legacy")
                for index, message in enumerate(messages[language])
            ),
        ),
    )


def run_plan(specs: list[TrialSpec]) -> dict:
    return {
        "version": 1,
        "suite_version": SUITE_VERSION,
        "execution_mode": "plan",
        "live_evidence": False,
        "session_count": len(specs),
        "max_provider_calls_without_retries": sum(len(s.case.steps) * 2 for s in specs),
        "human_quality": "unrated",
        "production_sessions_changed": False,
        "destinations": {
            "openai": "https://api.openai.com/v1",
            "qwen": QwenCloudProvider.TOKEN_PLAN_BASE_URL,
        },
        "limitations": [
            "Call bounds are not monetary cost estimates.",
            "A passed contract does not prove natural dialogue.",
        ],
        "trials": [
            dict(spec.configuration(), configuration_id=spec.configuration_id) for spec in specs
        ],
    }


def _known_secrets() -> tuple[str, ...]:
    names = ["OPENAI_API_KEY", "QWEN_API_KEY", "DASHSCOPE_API_KEY", "NEGOTIATION_ADMIN_TOKEN"]
    custom = os.getenv("NEGOTIATION_NPC_API_KEY_ENV")
    if custom and re.fullmatch(r"[A-Z_][A-Z0-9_]*", custom):
        names.append(custom)
    return tuple(value for name in names if (value := os.getenv(name)))


def _quote_check(observed, public_offers: list[dict], delivered_text: str) -> dict:
    if observed is None:
        return {"eligible": 0, "used": 0, "sources_valid": None}
    request, _result = observed
    quotes = reference_texts(request)
    used = [
        slot for slot in request.numeric_references if delivered_text.count(quotes[slot.token]) == 1
    ]
    valid = all(
        any(
            offer.get("offer_id") == slot.offer_id
            and offer.get("offer_revision") == slot.offer_revision
            and offer.get("proposer_role") == slot.proposer_role
            and offer.get("terms", {}).get(slot.term_id) == slot.value
            for offer in public_offers
        )
        for slot in used
    )
    return {"eligible": len(quotes), "used": len(used), "sources_valid": valid if used else None}


def _legacy_checks(spec: TrialSpec, index: int, state: dict, delivery: dict) -> dict:
    checks = {"session_active": state["status"] == "active"}
    if spec.suite == "continuity":
        if index == 0:
            checks["focus_routed"] = delivery.get("speech_act") == "focused_discussion"
        if spec.case.language == "ru" and index >= 1:
            active = state.get("observation", {}).get("active_offers", [])
            checks["missing_terms_not_filled"] = len(active) == 1 and active[0].get("terms") == {
                "price": 105000
            }
            if index == 1:
                checks["partial_offer_routed"] = (
                    delivery.get("speech_act") == "acknowledge_partial_offer"
                )
    return checks


def _expected_generation_bypass(state: dict, delivery: dict, events: list[dict]) -> bool:
    if not delivery:
        return state.get("result") == "clarification_required" and any(
            event.get("type") == "clarification.required" for event in events
        )
    return (
        delivery.get("speech_act")
        in {"complete_counteroffer", "offer_acceptance", "offer_rejection"}
        and delivery.get("action") in {"counter_offer", "accept", "reject"}
        and delivery.get("dialogue_renderer", {}).get("mode") == "template"
        and delivery.get("dialogue_renderer", {}).get("fallback_used") is False
    )


def run_trial(
    spec: TrialSpec, *, mode: str, budget: CallBudget, text_provider=None
) -> tuple[dict, dict | None]:
    from backend.app.main import create_app

    if mode not in {"offline", "live"}:
        raise ValueError("A trial requires offline or live execution mode")
    steps: list[dict] = []
    result = {
        "configuration_id": spec.configuration_id,
        "case_id": spec.case.case_id,
        "execution_mode": mode,
        "target_provider": spec.provider,
        "target_model": spec.model,
        "language": spec.case.language,
        "difficulty": spec.difficulty,
        "scenario_id": spec.case.scenario_id,
        "scenario_version": spec.case.scenario_version,
        "steps": steps,
        "passed": False,
        "failure": None,
    }
    if text_provider is None:
        text_provider = (
            OfflineProvider()
            if mode == "offline"
            else provider_for(
                spec.provider,
                model=spec.model,
                api_key_env="OPENAI_API_KEY" if spec.provider == "openai" else "QWEN_API_KEY",
                base_url=QwenCloudProvider.TOKEN_PLAN_BASE_URL if spec.provider == "qwen" else None,
                max_output_tokens=spec.max_output_tokens,
                timeout=spec.timeout,
                max_attempts=1,
            )
        )
    renderer = ObservedRenderer(text_provider, budget)
    secret_values = _known_secrets()
    exported = None
    with tempfile.TemporaryDirectory(prefix="negotiation-dr28-") as directory:
        admin_token = secrets.token_urlsafe(32)
        settings = Settings(
            database_path=Path(directory) / "session.sqlite3",
            scenario_directories=(ROOT / "examples",),
            scenario_schema_path=ROOT / "schemas/scenario-v1.schema.json",
            admin_token=admin_token,
            npc_provider="template",
        )
        try:
            with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
                response = client.post(
                    "/api/v1/sessions",
                    json={
                        "idempotency_key": "smoke-create",
                        "scenario_id": spec.case.scenario_id,
                        "scenario_version": spec.case.scenario_version,
                        "language": spec.case.language,
                        "participants": [
                            {"role": "buyer", "controller": "human"},
                            {"role": "seller", "controller": "built_in_npc"},
                        ],
                        "difficulty": spec.difficulty,
                        "hints_enabled": False,
                        "run_mode": "training",
                    },
                )
                if response.status_code != 201:
                    result["failure"] = "session_creation_failed"
                    return result, None
                state = response.json()
                token, session_id = state["participant_token"], state["session_id"]
                participant_id = state["observation"]["participant_id"]
                headers = {"Authorization": f"Bearer {token}"}
                admin_headers = {"Authorization": f"Bearer {admin_token}"}
                result["session_id"] = session_id
                known = (*secret_values, admin_token, token)
                events = client.get(
                    f"/api/v1/sessions/{session_id}/history", headers=headers
                ).json()["events"]
                style = None
                for index, step in enumerate(spec.case.steps):
                    if state["status"] != "active":
                        result["failure"] = "unexpected_terminal_state"
                        break
                    if budget.used >= budget.limit:
                        result["failure"] = "provider_call_budget_exhausted"
                        break
                    if isinstance(text_provider, OfflineProvider):
                        text_provider.prefer_quote = step.quote_requested
                    before, observed_count = state, len(renderer.observations)
                    started = time.monotonic()
                    response = client.post(
                        f"/api/v1/sessions/{session_id}/messages",
                        headers=headers,
                        json={
                            "message": step.message,
                            "idempotency_key": f"smoke-{index}",
                            "expected_revision": state["revision"],
                        },
                    )
                    if response.status_code != 200:
                        result["failure"] = "message_http_failure"
                        steps.append(
                            {
                                "step_id": step.step_id,
                                "http_status": response.status_code,
                                "passed": False,
                            }
                        )
                        break
                    state = response.json()
                    current_events = client.get(
                        f"/api/v1/sessions/{session_id}/history", headers=headers
                    ).json()["events"]
                    previous_ids = {event["event_id"] for event in events}
                    new_events = [
                        event for event in current_events if event["event_id"] not in previous_ids
                    ]
                    events = current_events
                    observed = (
                        renderer.observations[-1]
                        if len(renderer.observations) > observed_count
                        else None
                    )
                    delivery = next(
                        (
                            item
                            for item in reversed(state.get("committed_actions", []))
                            if item.get("participant_id") != participant_id
                            and "dialogue_renderer" in item
                        ),
                        {},
                    )
                    checks = (
                        evaluate_step(step, before, state, new_events, participant_id)
                        if spec.suite == "grounded"
                        else _legacy_checks(spec, index, state, delivery)
                    )
                    quote = _quote_check(
                        observed,
                        state.get("observation", {}).get("active_offers", []),
                        delivery.get("message", ""),
                    )
                    bypassed = observed is None and _expected_generation_bypass(
                        state, delivery, new_events
                    )
                    generation_ok = None if bypassed else False
                    if observed:
                        request, rendered = observed
                        metadata = delivery.get("dialogue_renderer", {})
                        generation_ok = (
                            metadata.get("mode") == "llm" and metadata.get("fallback_used") is False
                        )
                        style = request.conversation_style if style is None else style
                        checks["difficulty_profile"] = request.difficulty == spec.difficulty
                        checks["stable_style"] = request.conversation_style == style
                    if step.quote_requested:
                        checks["numeric_quote_used"] = quote["used"] > 0
                        checks["numeric_quote_source"] = quote["sources_valid"] is True
                    steps.append(
                        {
                            "step_id": step.step_id,
                            "checks": checks,
                            "quote": quote,
                            "generation_succeeded": generation_ok,
                            "expected_generation_bypass": bypassed,
                            "seconds": round(time.monotonic() - started, 3),
                            "passed": bool(checks)
                            and all(checks.values())
                            and generation_ok is not False,
                        }
                    )
                detail_response = client.get(
                    f"/api/v1/admin/sessions/{session_id}", headers=admin_headers
                )
                if detail_response.status_code == 200:
                    exported = build_public_artifact_session(
                        detail_response.json(),
                        metadata={
                            "provider": renderer.provider,
                            "model": renderer.model,
                            "target_provider": spec.provider,
                            "target_model": spec.model,
                            "execution_mode": mode,
                            "suite": spec.suite,
                            "case_id": spec.case.case_id,
                            "configuration_id": spec.configuration_id,
                            "prompt_version": SUITE_VERSION,
                            "seed": None,
                            "max_turns": len(spec.case.steps),
                        },
                        known_secrets=known,
                    )
                else:
                    result["failure"] = "public_export_failed"
                result["final_status"] = state["status"]
        except Exception:
            # No response body, traceback, key, or provider exception enters artifacts.
            result["failure"] = "trial_execution_failed"
    result["provider_calls"] = renderer.bounded.calls
    result["completed_steps"] = len(steps)
    result["passed"] = (
        result["failure"] is None
        and len(steps) == len(spec.case.steps)
        and bool(steps)
        and all(step["passed"] for step in steps)
        and exported is not None
    )
    return result, exported


def execute(
    specs: list[TrialSpec], *, mode: str, max_provider_calls: int, workers: int = 1
) -> dict:
    if mode not in {"offline", "live"} or not specs or not 1 <= workers <= 4:
        raise ValueError("Invalid execution configuration")
    if max_provider_calls <= 0:
        raise ValueError("Execution requires a positive provider-call limit")
    if mode == "live" and any(
        not os.getenv("OPENAI_API_KEY" if spec.provider == "openai" else "QWEN_API_KEY")
        for spec in specs
    ):
        raise ValueError("A selected live provider credential is missing")
    budget = CallBudget(max_provider_calls)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda spec: run_trial(spec, mode=mode, budget=budget), specs))
    return {
        "version": 1,
        "suite_version": SUITE_VERSION,
        "execution_mode": mode,
        "live_evidence": mode == "live",
        "human_quality": "unrated",
        "sessions": [session for _, session in results if session is not None],
        "trials": [trial for trial, _ in results],
        "provider_calls": budget.used,
        "network_calls": None if mode == "live" else 0,
        "network_call_upper_bound": budget.used if mode == "live" else 0,
        "provider_call_limit": budget.limit,
        "budget_denials": budget.denied,
        "passed": all(trial["passed"] for trial, _ in results),
        "limitations": [
            "Offline fixtures do not measure live model quality.",
            "Technical success is not a human-quality score.",
            "Temporary session IDs are source references, not replay links to the running UI.",
        ],
    }


def _model_id(value: str) -> str:
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", value)
        or redact_untrusted_credentials(value, *_known_secrets()) != value
    ):
        raise argparse.ArgumentTypeError("Invalid model identifier")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers", nargs="+", choices=tuple(DEFAULT_MODELS), default=list(DEFAULT_MODELS)
    )
    parser.add_argument("--languages", nargs="+", choices=("ru", "en"), default=["ru", "en"])
    parser.add_argument(
        "--difficulties", nargs="+", choices=DIFFICULTIES, default=list(DIFFICULTIES)
    )
    parser.add_argument(
        "--suite", choices=("grounded", "contextual", "continuity"), default="grounded"
    )
    parser.add_argument("--mode", choices=("plan", "offline", "live"), default="plan")
    parser.add_argument("--openai-model", type=_model_id, default=DEFAULT_MODELS["openai"])
    parser.add_argument("--qwen-model", type=_model_id, default=DEFAULT_MODELS["qwen"])
    parser.add_argument("--max-provider-calls", type=int)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.mode == "live" and (
        args.max_provider_calls is None or not 1 <= args.max_provider_calls <= 1000
    ):
        parser.error(
            "Live mode requires --max-provider-calls from 1 to 1000; this is not a monetary budget"
        )
    if args.max_provider_calls is not None and not 1 <= args.max_provider_calls <= 1000:
        parser.error("--max-provider-calls must be from 1 to 1000")
    if args.mode != "plan" and args.output is None:
        parser.error("Execution requires --output to retain public results")
    specs = [
        TrialSpec(
            provider,
            args.openai_model if provider == "openai" else args.qwen_model,
            difficulty,
            case,
            args.suite,
        )
        for provider in dict.fromkeys(args.providers)
        for language in dict.fromkeys(args.languages)
        for difficulty in dict.fromkeys(args.difficulties)
        for case in selected_cases(args.suite, language)
    ]
    # Reserve the exact output before any paid work; never overwrite an artifact.
    output = None
    try:
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            output = args.output.open("x", encoding="utf-8")
        artifact = (
            run_plan(specs)
            if args.mode == "plan"
            else execute(
                specs,
                mode=args.mode,
                max_provider_calls=args.max_provider_calls
                or sum(len(s.case.steps) * 2 for s in specs),
                workers=args.workers,
            )
        )
        serialized = json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if output:
            output.write(serialized)
            print(
                json.dumps(
                    {
                        "execution_mode": args.mode,
                        "passed": artifact.get("passed"),
                        "output": str(args.output),
                    }
                )
            )
        else:
            print(serialized, end="")
        return 0 if args.mode == "plan" or artifact["passed"] else 1
    except (OSError, ValueError):
        print(
            json.dumps(
                {"error": "configuration_or_output_failure", "external_error_details_omitted": True}
            )
        )
        return 2
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
