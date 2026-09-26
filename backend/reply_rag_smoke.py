"""Compare NPC wording with and without retrieval on synthetic approved requests."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.dialogue import LlmNpcDialogueRenderer, template_dialogue_result
from backend.app.main import create_app
from backend.app.reply_retrieval import LIBRARY_VERSION
from backend.live_dialogue_smoke import BudgetedProvider, CallBudget, OfflineProvider
from clients.providers import QwenCloudProvider, provider_for


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("personal_question", "Здравствуйте! Рад снова поработать с вами: прошлую сделку вспоминаю с удовольствием. Кстати, как зовут вашу собаку?"),
    ("conditional_trade", "Что для вас важнее — размер предоплаты или срок запуска? Хочу понять, где возможен обмен уступками."),
    ("price_reason", "Почему такая высокая цена?"),
    ("price_focus", "Давайте сначала обсудим цену подписки. Оплату обсудим позже."),
)


class CaptureRenderer:
    def __init__(self):
        self.requests = []

    def render(self, request):
        self.requests.append(request)
        return template_dialogue_result(request)


def prepare_requests():
    """Use isolated API sessions to select actions and disclosure permissions."""
    renderer = CaptureRenderer()
    cases = []
    with tempfile.TemporaryDirectory(prefix="reply-rag-") as directory:
        settings = Settings(
            database_path=Path(directory) / "test.sqlite3",
            scenario_directories=(ROOT / "examples",),
            scenario_schema_path=ROOT / "schemas/scenario-v1.schema.json",
            admin_token=None,
            npc_provider="template",
        )
        with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
            for case_id, message in CASES:
                created = client.post("/api/v1/sessions", json={
                    "idempotency_key": case_id, "scenario_id": "saas_subscription_ru",
                    "scenario_version": 3, "language": "ru", "run_mode": "training",
                    "difficulty": "normal", "hints_enabled": False,
                    "participants": [{"role": "buyer", "controller": "human"},
                                     {"role": "seller", "controller": "built_in_npc"}],
                    "training": {"profile": "sociable", "relationship": "successful_history",
                                 "personal_detail": True,
                                 "shared_background": "Ранее успешно заключали сделки."},
                })
                created.raise_for_status()
                session = created.json()
                before = len(renderer.requests)
                response = client.post(
                    f"/api/v1/sessions/{session['session_id']}/messages",
                    headers={"Authorization": "Bearer " + session["participant_token"]},
                    json={"message": message, "expected_revision": session["revision"],
                          "idempotency_key": case_id + "-message"},
                )
                response.raise_for_status()
                if len(renderer.requests) != before + 1:
                    raise RuntimeError("Expected exactly one captured NPC request")
                request = renderer.requests[-1]
                if not request.retrieved_reply_examples:
                    raise RuntimeError("Comparison case has no retrieved examples: " + case_id)
                cases.append((case_id, message, request))
    return cases


class MeasuredProvider:
    def __init__(self, provider):
        self.provider, self.config = provider, provider.config
        self.calls = []

    def generate(self, messages, *, instructions=None):
        stage = "grounding" if "CANDIDATE_REPLY_JSON" in messages[0]["content"] else "generation"
        try:
            result = self.provider.generate(messages, instructions=instructions)
        except Exception:
            self.calls.append({"stage": stage, "status": "failed"})
            raise
        self.calls.append({"stage": stage, "status": "completed", "latency_ms": result.latency_ms,
                           "usage": dict(result.usage)})
        return result


def compare(cases, provider, budget):
    measured = MeasuredProvider(BudgetedProvider(provider, budget))
    renderer = LlmNpcDialogueRenderer(measured)
    results = []
    for index, (case_id, message, request) in enumerate(cases):
        case = {"id": case_id, "message": message, "speech_act": request.speech_act,
                "approved_reason_ids": [item[0] for item in request.approved_reasons],
                "examples": [asdict(item) for item in request.retrieved_reply_examples], "arms": {}}
        # Alternate order to reduce a systematic warm-up or network-order effect.
        order = ("without_retrieval", "with_retrieval") if index % 2 == 0 else ("with_retrieval", "without_retrieval")
        case["order"] = order
        for arm in order:
            current = replace(request, retrieved_reply_examples=()) if arm == "without_retrieval" else request
            before = len(measured.calls)
            result = renderer.render(current)
            case["arms"][arm] = {"result": asdict(result), "calls": measured.calls[before:]}
            print(json.dumps({"case": case_id, "arm": arm, "mode": result.mode,
                              "fallback": result.fallback_used, "latency_ms": result.latency_ms}), flush=True)
        results.append(case)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "offline", "live"), default="plan")
    parser.add_argument("--max-provider-calls", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.mode == "plan":
        print(json.dumps({"cases": [item[0] for item in CASES], "arms": 2, "maximum_calls": 16,
                          "model": "qwen3.8-max", "library_version": LIBRARY_VERSION}, indent=2))
        return 0
    if args.output is None or not 1 <= args.max_provider_calls <= 16:
        parser.error("Execution requires --output and --max-provider-calls between 1 and 16")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the output before any provider call. Never overwrite an earlier run.
    with args.output.open("x", encoding="utf-8") as output:
        cases = prepare_requests()
        provider = OfflineProvider() if args.mode == "offline" else provider_for(
            "qwen", model="qwen3.8-max", api_key_env="QWENCLOUD_TOKEN_PLAN_API_KEY",
            base_url=QwenCloudProvider.TOKEN_PLAN_BASE_URL, max_output_tokens=500,
            temperature=0.3, seed=42, timeout=45, max_attempts=1,
        )
        budget = CallBudget(args.max_provider_calls)
        results = compare(cases, provider, budget)
        report = {"created_at": datetime.now(timezone.utc).isoformat(), "mode": args.mode,
                  "scope": "Synthetic renderer ablation; not a policy benchmark or a human study.",
                  "scenario_id": "saas_subscription_ru", "scenario_version": 3,
                  "library_version": LIBRARY_VERSION, "provider_config": asdict(provider.config),
                  "seed_reproducibility_guaranteed": False,
                  "provider_calls": budget.used, "denied_calls": budget.denied, "cases": results}
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
