"""Independent fault-injection checks. These tests never call live providers."""

from dataclasses import replace
import json

from backend import live_dialogue_smoke as smoke
from backend.app.dialogue import TemplateNpcDialogueRenderer
from backend.dialogue_smoke_cases import grounded_cases


def _spec(case=None, *, suite="grounded"):
    return smoke.TrialSpec(
        "openai", "audit-offline-target", "easy", case or grounded_cases("ru")[0], suite
    )


def test_plan_does_not_construct_provider_or_application(monkeypatch, capsys):
    import backend.app.main as application

    def forbidden(*args, **kwargs):
        raise AssertionError("Planning must not execute a session or construct a provider")

    monkeypatch.setattr(smoke, "provider_for", forbidden)
    monkeypatch.setattr(application, "create_app", forbidden)
    assert smoke.main(["--providers", "openai", "--languages", "ru", "--difficulties", "easy"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["execution_mode"] == "plan"
    assert plan["session_count"] == 3
    assert plan["live_evidence"] is False


def test_unobserved_template_reply_cannot_pass_as_generated_dialogue(monkeypatch):
    # Inject a renderer instrumentation failure. No observed request means that
    # a conversational template reply cannot count as successful LLM generation.
    monkeypatch.setattr(
        smoke.ObservedRenderer,
        "render",
        lambda self, request: TemplateNpcDialogueRenderer().render(request),
    )
    original = grounded_cases("ru")[0]
    quote_only = replace(original, steps=(original.steps[1],))
    result, _ = smoke.run_trial(_spec(quote_only), mode="offline", budget=smoke.CallBudget(10))
    assert result["passed"] is False


def test_quote_coverage_uses_delivered_text_not_successful_renderer_candidate(monkeypatch):
    import backend.app.service as service

    # The real renderer creates a quote, but delivery validation replaces it.
    # A prevalidation candidate is not evidence that the participant saw it.
    monkeypatch.setattr(
        service,
        "validated_dialogue_result",
        lambda request, rendered: TemplateNpcDialogueRenderer().render(request),
    )
    original = grounded_cases("ru")[0]
    first = replace(original, steps=original.steps[:1])
    result, _ = smoke.run_trial(_spec(first), mode="offline", budget=smoke.CallBudget(10))
    assert result["provider_calls"] == 2
    assert result["steps"][0]["quote"]["eligible"] > 0
    assert result["steps"][0]["quote"]["used"] == 0
    assert result["steps"][0]["checks"]["numeric_quote_used"] is False
    assert result["passed"] is False


def test_grounding_call_shares_budget_and_offline_cannot_construct_live_provider(monkeypatch):
    import clients.providers as providers

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline validation must not access a provider endpoint")

    monkeypatch.setattr(smoke, "provider_for", forbidden)
    monkeypatch.setattr(providers, "_post_json", forbidden)
    original = grounded_cases("ru")[0]
    first = replace(original, steps=original.steps[:1])
    budget = smoke.CallBudget(1)
    result, _ = smoke.run_trial(_spec(first), mode="offline", budget=budget)
    assert budget.used == 1
    assert budget.denied == 1
    assert result["provider_calls"] == 1
    assert result["passed"] is False


def test_legacy_continuity_rejects_wrong_committed_partial_price(monkeypatch):
    import backend.app.service as service

    original_parser = service.parse_message

    def wrong_price(message, *args, **kwargs):
        result = original_parser(message, *args, **kwargs)
        if message == "Предлагаю цену 105 000 евро.":
            return replace(result, terms_delta={"price": 110000})
        return result

    monkeypatch.setattr(service, "parse_message", wrong_price)
    legacy = smoke.selected_cases("continuity", "ru")[0]
    initial_steps = replace(legacy, steps=legacy.steps[:2])
    result, _ = smoke.run_trial(
        _spec(initial_steps, suite="continuity"), mode="offline", budget=smoke.CallBudget(10)
    )
    assert result["passed"] is False
