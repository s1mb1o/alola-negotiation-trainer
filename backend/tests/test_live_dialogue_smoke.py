import json

import pytest

from backend import live_dialogue_smoke as smoke
from backend.dialogue_smoke_cases import grounded_cases
from benchmarks.dialogue_quality import analyze, export_scorecard


def spec(language="ru", difficulty="normal", case_index=0):
    return smoke.TrialSpec(
        "openai", "gpt-5.6-luna", difficulty, grounded_cases(language)[case_index]
    )


def test_default_cli_plans_without_live_factory_or_database(monkeypatch, capsys):
    monkeypatch.setattr(
        smoke, "provider_for", lambda *a, **kw: pytest.fail("Plan constructed live provider")
    )
    monkeypatch.setattr(smoke, "TestClient", lambda *a, **kw: pytest.fail("Plan created a session"))
    assert smoke.main([]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["execution_mode"] == "plan" and plan["live_evidence"] is False
    assert plan["session_count"] == 48
    assert {item["case"]["scenario_version"] for item in plan["trials"]} == {4, 5}
    assert len({item["configuration_id"] for item in plan["trials"]}) == 48


@pytest.mark.parametrize("language", ["ru", "en"])
@pytest.mark.parametrize("difficulty", smoke.DIFFICULTIES)
def test_grounded_case_matrix_uses_real_render_validation_without_network(
    language, difficulty, monkeypatch
):
    monkeypatch.setattr(
        smoke, "provider_for", lambda *a, **kw: pytest.fail("Offline constructed live provider")
    )
    specs = [
        smoke.TrialSpec("qwen", "qwen3.8-max", difficulty, case)
        for case in grounded_cases(language)
    ]
    artifact = smoke.execute(specs, mode="offline", max_provider_calls=100, workers=3)
    assert artifact["passed"], artifact["trials"]
    assert artifact["network_calls"] == 0 and artifact["live_evidence"] is False
    assert len({row["session_id"] for row in artifact["sessions"]}) == 3
    assert all(row["provider"] == "offline-fixture" for row in artifact["sessions"])
    assert all(row["run_metadata"]["target_provider"] == "qwen" for row in artifact["sessions"])
    assert any(step["quote"]["used"] for trial in artifact["trials"] for step in trial["steps"])
    assert all(row["source_digest"] for row in export_scorecard(artifact)["sessions"])
    assert all(group["human_coverage"]["rated_turns"] == 0 for group in analyze(artifact)["groups"])


class NoQuote(smoke.OfflineProvider):
    def generate(self, messages, *, instructions=None):
        self.prefer_quote = False
        return super().generate(messages, instructions=instructions)


class InvalidNumber(smoke.OfflineProvider):
    def generate(self, messages, *, instructions=None):
        approved = json.loads(messages[0]["content"].split("\n", 2)[1])
        return smoke.Generation(
            json.dumps({"speech_act": approved["speech_act"], "reply": "Цена 99999 EUR."}),
            "offline-fixture",
            "invalid-number",
            0,
        )


class Failing(smoke.OfflineProvider):
    def generate(self, messages, *, instructions=None):
        raise RuntimeError("SECRET-DO-NOT-EXPORT")


@pytest.mark.parametrize("provider", [NoQuote, InvalidNumber, Failing])
def test_model_nonuse_rejection_and_failure_cannot_pass_quote_coverage(provider):
    result, session = smoke.run_trial(
        spec(), mode="offline", budget=smoke.CallBudget(20), text_provider=provider()
    )
    assert not result["passed"]
    assert result["steps"][0]["checks"]["numeric_quote_used"] is False
    assert session is not None
    assert "SECRET-DO-NOT-EXPORT" not in json.dumps({"trial": result, "session": session})


def test_budget_counts_generation_and_grounding_separately():
    budget = smoke.CallBudget(1)
    result, session = smoke.run_trial(spec(), mode="offline", budget=budget)
    assert budget.used == 1 and budget.denied == 1
    assert not result["passed"] and session is not None
    assert result["steps"][0]["generation_succeeded"] is False
    assert result["failure"] == "provider_call_budget_exhausted"


def test_budget_is_atomic_across_concurrent_sessions():
    artifact = smoke.execute(
        [spec(), spec("en"), spec(difficulty="expert")],
        mode="offline",
        max_provider_calls=2,
        workers=3,
    )
    assert artifact["provider_calls"] == 2
    assert not artifact["passed"]
    assert all(trial["failure"] == "provider_call_budget_exhausted" for trial in artifact["trials"])


def test_live_requires_explicit_positive_limit_before_any_provider_call(tmp_path, monkeypatch):
    monkeypatch.setattr(
        smoke, "provider_for", lambda *a, **kw: pytest.fail("Unexpected live factory")
    )
    with pytest.raises(SystemExit):
        smoke.main(["--mode", "live", "--output", str(tmp_path / "results.json")])
    assert not (tmp_path / "results.json").exists()


def test_output_refuses_overwrite_before_execution(tmp_path, monkeypatch):
    output = tmp_path / "existing.json"
    output.write_text("keep me")
    monkeypatch.setattr(
        smoke, "execute", lambda *a, **kw: pytest.fail("Executed before protecting existing result")
    )
    assert smoke.main(["--mode", "offline", "--output", str(output)]) == 2
    assert output.read_text() == "keep me"


def test_live_adapter_has_no_unbudgeted_retry(monkeypatch):
    observed = []

    def factory(*args, **kwargs):
        observed.append(kwargs)
        return NoQuote()

    monkeypatch.setattr(smoke, "provider_for", factory)
    result, _ = smoke.run_trial(spec(), mode="live", budget=smoke.CallBudget(20))
    assert result["passed"] is False
    assert observed[0]["max_attempts"] == 1


@pytest.mark.parametrize("suite", ["contextual", "continuity"])
@pytest.mark.parametrize("language", ["ru", "en"])
def test_explicit_legacy_suites_remain_executable_offline(suite, language):
    case = smoke.selected_cases(suite, language)[0]
    result, session = smoke.run_trial(
        smoke.TrialSpec("openai", "gpt-5.6-luna", "easy", case, suite),
        mode="offline",
        budget=smoke.CallBudget(40),
    )
    assert result["passed"], result
    assert session is not None


def test_model_identifier_cannot_contain_a_configured_credential(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "a-custom-secret-value")
    with pytest.raises(ValueError):
        smoke.TrialSpec("openai", "a-custom-secret-value", "easy", grounded_cases("ru")[0])


def test_configuration_identity_changes_for_case_model_and_difficulty():
    originals = [spec(), spec("en"), spec(difficulty="easy"), spec(case_index=1)]
    assert len({item.configuration_id for item in originals}) == len(originals)
