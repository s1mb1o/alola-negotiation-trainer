from __future__ import annotations

from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.runner import ModelSpec, ScenarioSpec, main, run_benchmark
from clients.api import ApiError
from clients.providers import ProviderError


class FakeApi:
    def stats(self):
        return {"totals": {"total_sessions": 0}}


class BenchmarkRunnerTest(unittest.TestCase):
    def test_provider_failure_is_a_safe_explicit_trial_result(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "benchmarks.runner.run_self_play",
                side_effect=ProviderError("provider unavailable"),
            ):
                summary = run_benchmark(
                    FakeApi(),
                    scenarios=[ScenarioSpec("saas_subscription_en", 1, "en")],
                    models=[ModelSpec("openai", "gpt-test")],
                    repetitions=1,
                    seed=1,
                    max_messages=2,
                    output_dir=Path(directory),
                    benchmark_run_id="bench_failure",
                )
            trial = Path(directory, "trials", "bench_failure_t0001.json").read_text(
                encoding="utf-8"
            )
        self.assertEqual(summary["failed_trials"], 1)
        self.assertEqual(summary["local_stats"]["models"]["openai:gpt-test"]["runs"], 2)
        self.assertEqual(summary["local_stats"]["negotiation_outcome_run_count"], 0)
        self.assertFalse(summary["configuration"]["seed_schedule"]["reproducibility_guaranteed"])
        self.assertEqual(summary["configuration"]["generation"]["max_output_tokens"], 500)
        self.assertEqual(
            summary["configuration"]["generation"]["prompt_version"], "natural-language-agent-v5"
        )
        self.assertIn('"status": "technical_failure"', trial)
        self.assertIn('"max_output_tokens": 500', trial)
        self.assertIn('"prompt_version": "natural-language-agent-v5"', trial)
        self.assertIn("provider unavailable", trial)
        self.assertIn('"handling": "unsupported_not_sent"', trial)
        self.assertIn('"seat_seeds"', trial)
        self.assertEqual(summary["configuration"]["generation"]["provider_max_attempts"], 3)
        self.assertEqual(
            summary["configuration"]["generation"]["provider_retry_backoff_seconds"], 1.0
        )

    def test_runner_declares_the_complete_trial_set(self):
        expected_values = []

        def fake_self_play(api, **kwargs):
            expected_values.append(kwargs["benchmark_expected_trials"])
            seats = kwargs["seats"]
            return {
                "benchmark_run_id": kwargs["benchmark_run_id"],
                "trial_id": kwargs["trial_id"],
                "session_id": None,
                "status": "technical_failure",
                "failing_role": None,
                "failure": {"source": "test"},
                "turns": [],
                "seats": [
                    {
                        "role": seat.role,
                        "provider": seat.provider.config.provider,
                        "model": seat.provider.config.model,
                    }
                    for seat in seats
                ],
            }

        with tempfile.TemporaryDirectory() as directory:
            with patch("benchmarks.runner.run_self_play", side_effect=fake_self_play):
                summary = run_benchmark(
                    FakeApi(),
                    scenarios=[ScenarioSpec("saas_subscription_en", 1, "en")],
                    models=[ModelSpec("openai", "gpt-test"), ModelSpec("qwen", "qwen-test")],
                    repetitions=1,
                    seed=1,
                    max_messages=2,
                    output_dir=Path(directory),
                    benchmark_run_id="bench_manifest",
                )

        self.assertEqual(expected_values, [2, 2])
        self.assertEqual(summary["configuration"]["expected_trials"], 2)

    def test_each_seat_gets_a_distinct_seed_and_the_schedule_is_recorded(self):
        observed = []

        def fake_self_play(api, **kwargs):
            seats = kwargs["seats"]
            observed.append(
                (kwargs["seed"], {seat.role: seat.provider.config.seed for seat in seats})
            )
            return {
                "trial_id": kwargs["trial_id"],
                "session_id": None,
                "status": "technical_failure",
                "failure": {"source": "test"},
                "turns": [],
                "seats": [],
            }

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("benchmarks.runner.run_self_play", side_effect=fake_self_play),
        ):
            summary = run_benchmark(
                FakeApi(),
                scenarios=[ScenarioSpec("saas_subscription_en", 1, "en")],
                models=[ModelSpec("openai", "gpt-test"), ModelSpec("qwen", "qwen-test")],
                repetitions=1,
                seed=100,
                max_messages=2,
                output_dir=Path(directory),
                benchmark_run_id="bench_seeds",
                provider_max_attempts=4,
            )

        self.assertEqual(
            observed,
            [
                (100, {"buyer": 100, "seller": 101}),
                (102, {"buyer": 102, "seller": 103}),
            ],
        )
        schedule = summary["configuration"]["seed_schedule"]
        self.assertEqual(schedule["base_seed"], 100)
        self.assertEqual(schedule["increment_per_trial"], 2)
        self.assertEqual(schedule["seat_seed_offsets"], {"buyer": 0, "seller": 1})
        self.assertEqual(summary["configuration"]["generation"]["provider_max_attempts"], 4)

    def test_provider_failure_record_keeps_retry_count_and_diagnostics(self):
        error = ProviderError(
            "Qwen response did not contain message content (finish_reason=length, ...)",
            failure_diagnostics={"finish_reason": "length", "has_reasoning_content": True},
            retry_count=2,
        )
        with tempfile.TemporaryDirectory() as directory:
            with patch("benchmarks.runner.run_self_play", side_effect=error):
                run_benchmark(
                    FakeApi(),
                    scenarios=[ScenarioSpec("saas_subscription_en", 1, "en")],
                    models=[ModelSpec("qwen", "qwen-test")],
                    repetitions=1,
                    seed=1,
                    max_messages=2,
                    output_dir=Path(directory),
                    benchmark_run_id="bench_diag",
                )
            trial = json.loads(
                Path(directory, "trials", "bench_diag_t0001.json").read_text(encoding="utf-8")
            )
        self.assertEqual(trial["failure"]["retry_count"], 2)
        self.assertEqual(
            trial["failure"]["failure_diagnostics"],
            {"finish_reason": "length", "has_reasoning_content": True},
        )
        self.assertEqual(trial["seat_seeds"], {"buyer": 1, "seller": 2})

    def test_creation_401_aborts_the_run_and_names_the_admin_token_variable(self):
        rejection = ApiError(
            "A valid administrator Bearer credential is required",
            status=401,
            error="administrator_unauthorized",
        )
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("benchmarks.runner.run_self_play", side_effect=rejection),
                self.assertRaises(ApiError) as raised,
            ):
                run_benchmark(
                    FakeApi(),
                    scenarios=[ScenarioSpec("saas_subscription_en", 1, "en")],
                    models=[ModelSpec("openai", "gpt-test")],
                    repetitions=1,
                    seed=1,
                    max_messages=2,
                    output_dir=Path(directory),
                    benchmark_run_id="bench_401",
                )
            self.assertFalse(Path(directory, "summary.json").exists())
        self.assertEqual(raised.exception.status, 401)
        self.assertIn("NEGOTIATION_ADMIN_TOKEN", str(raised.exception))

        stderr = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("benchmarks.runner.run_self_play", side_effect=rejection),
            redirect_stderr(stderr),
        ):
            code = main(
                [
                    "--scenario",
                    "saas_subscription_en",
                    "--model",
                    "openai:gpt-test",
                    "--repetitions",
                    "1",
                    "--output-dir",
                    directory,
                    "--provider-max-attempts",
                    "2",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("NEGOTIATION_ADMIN_TOKEN", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
