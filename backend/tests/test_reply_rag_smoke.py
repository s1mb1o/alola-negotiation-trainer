"""Safety and isolation checks for the retrieved-example ablation harness."""

import json

from backend import reply_rag_smoke
from backend.live_dialogue_smoke import CallBudget, OfflineProvider


def test_default_plan_does_not_prepare_sessions_or_call_provider(monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        raise AssertionError("Plan mode must not execute")
    monkeypatch.setattr(reply_rag_smoke, "prepare_requests", unexpected)
    monkeypatch.setattr(reply_rag_smoke, "provider_for", unexpected)
    assert reply_rag_smoke.main([]) == 0
    assert json.loads(capsys.readouterr().out)["maximum_calls"] == 16


def test_ablation_keeps_approved_input_identical_except_examples():
    cases = reply_rag_smoke.prepare_requests()
    assert len(cases) == 4
    class RecordingProvider(OfflineProvider):
        def __init__(self):
            super().__init__()
            self.inputs = []

        def generate(self, messages, *, instructions=None):
            payload = json.loads(messages[0]["content"].split("\n", 2)[1])
            self.inputs.append(payload)
            return super().generate(messages, instructions=instructions)

    provider = RecordingProvider()
    budget = CallBudget(16)
    results = reply_rag_smoke.compare(cases, provider, budget)
    assert budget.used == 8 and budget.denied == 0
    for offset in range(0, len(provider.inputs), 2):
        first, second = provider.inputs[offset:offset + 2]
        assert bool(first.pop("retrieved_reply_examples")) != bool(second.pop("retrieved_reply_examples"))
        assert first == second
    assert all(not arm["result"]["fallback_used"] for case in results for arm in case["arms"].values())
    serialized = json.dumps(results)
    assert "participant_token" not in serialized and "reservation_utility" not in serialized


def test_comparison_cannot_exceed_provider_call_limit():
    budget = CallBudget(1)
    results = reply_rag_smoke.compare(reply_rag_smoke.prepare_requests()[:1], OfflineProvider(), budget)
    assert budget.used == 1 and budget.denied == 1
    assert results[0]["arms"]["with_retrieval"]["result"]["failure_reason"] == "provider_failure"
