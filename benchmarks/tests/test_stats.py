from __future__ import annotations

import unittest

from benchmarks.runner import ModelSpec, comparison_pairs
from benchmarks.stats import aggregate_model_stats


class BenchmarkStatsTest(unittest.TestCase):
    def test_pair_matrix_swaps_each_model_across_roles(self):
        left = ModelSpec("openai", "gpt-a")
        right = ModelSpec("qwen", "qwen-b")
        self.assertEqual(comparison_pairs([left, right]), [(left, right), (right, left)])

    def test_aggregate_model_and_role_statistics(self):
        runs = [
            {
                "status": "agreement_reached",
                "seats": [
                    {"role": "buyer", "provider": "openai", "model": "gpt-a"},
                    {"role": "seller", "provider": "qwen", "model": "qwen-b"},
                ],
                "turns": [
                    {
                        "role": "buyer",
                        "provider": "openai",
                        "model": "gpt-a",
                        "latency_ms": 100,
                        "usage": {"total_tokens": 20},
                    },
                    {
                        "role": "seller",
                        "provider": "qwen",
                        "model": "qwen-b",
                        "latency_ms": 200,
                        "usage": {"total_tokens": 30},
                    },
                ],
                "review": {"outcome": {"agreement": True}},
                "reviews_by_role": {
                    "buyer": {
                        "outcome": {"agreement": True, "participant_utility": 80},
                        "scores": {"outcome_score": 82, "skill_score": 75},
                    },
                    "seller": {
                        "outcome": {"agreement": True, "participant_utility": 60},
                        "scores": {"outcome_score": 62, "skill_score": 70},
                    },
                },
            }
        ]
        result = aggregate_model_stats(runs)
        self.assertEqual(result["models"]["openai:gpt-a"]["mean_utility"], 80.0)
        self.assertEqual(result["models"]["openai:gpt-a"]["mean_utility_role_balanced"], 80.0)
        self.assertEqual(result["models"]["qwen:qwen-b"]["total_tokens"], 30.0)
        self.assertEqual(result["models"]["openai:gpt-a"]["roles"]["buyer"]["runs"], 1)
        self.assertEqual(result["models"]["openai:gpt-a"]["mean_outcome_score"], 82.0)
        self.assertEqual(result["models"]["qwen:qwen-b"]["mean_skill_score"], 70.0)
        self.assertEqual(result["models"]["openai:gpt-a"]["outcome_runs"], 1)

    def test_role_balanced_mean_utility_weights_each_role_equally(self):
        def run(buyer_model, seller_model, buyer_utility, seller_utility):
            return {
                "status": "agreement_reached",
                "seats": [
                    {"role": "buyer", "provider": "openai", "model": buyer_model},
                    {"role": "seller", "provider": "qwen", "model": seller_model},
                ],
                "turns": [],
                "reviews_by_role": {
                    "buyer": {"outcome": {"agreement": True, "participant_utility": buyer_utility}},
                    "seller": {
                        "outcome": {"agreement": True, "participant_utility": seller_utility}
                    },
                },
            }

        runs = [
            run("gpt-a", "qwen-b", 80, 10),
            run("gpt-a", "qwen-b", 60, 30),
            {
                **run("qwen-b", "gpt-a", 50, 20),
                "seats": [
                    {"role": "buyer", "provider": "qwen", "model": "qwen-b"},
                    {"role": "seller", "provider": "openai", "model": "gpt-a"},
                ],
            },
        ]
        result = aggregate_model_stats(runs)
        gpt = result["models"]["openai:gpt-a"]
        self.assertEqual(gpt["roles"]["buyer"]["mean_utility"], 70.0)
        self.assertEqual(gpt["roles"]["seller"]["mean_utility"], 20.0)
        self.assertEqual(gpt["mean_utility"], 53.3333)
        self.assertEqual(gpt["mean_utility_role_balanced"], 45.0)
        qwen = result["models"]["qwen:qwen-b"]
        self.assertEqual(qwen["mean_utility"], 30.0)
        self.assertEqual(qwen["mean_utility_role_balanced"], 35.0)

    def test_role_balanced_mean_utility_is_none_without_utilities(self):
        result = aggregate_model_stats(
            [
                {
                    "status": "walked_away",
                    "seats": [{"role": "buyer", "provider": "openai", "model": "gpt-a"}],
                    "turns": [],
                }
            ]
        )
        self.assertIsNone(result["models"]["openai:gpt-a"]["mean_utility"])
        self.assertIsNone(result["models"]["openai:gpt-a"]["mean_utility_role_balanced"])

    def test_provider_failure_is_attributed_only_to_failing_seat(self):
        result = aggregate_model_stats(
            [
                {
                    "status": "technical_failure",
                    "failing_role": "buyer",
                    "failure": {"source": "provider", "failing_role": "buyer"},
                    "seats": [
                        {"role": "buyer", "provider": "openai", "model": "gpt-a"},
                        {"role": "seller", "provider": "qwen", "model": "qwen-b"},
                    ],
                    "turns": [],
                }
            ]
        )
        openai = result["models"]["openai:gpt-a"]
        qwen = result["models"]["qwen:qwen-b"]
        self.assertEqual(result["technical_failure_runs"], 1)
        self.assertEqual(result["negotiation_outcome_run_count"], 0)
        self.assertEqual(openai["provider_failures"], 1)
        self.assertEqual(qwen["provider_failures"], 0)
        self.assertEqual(openai["outcome_runs"], 0)
        self.assertEqual(qwen["outcome_runs"], 0)
        self.assertIsNone(openai["agreement_rate"])
        self.assertIsNone(qwen["agreement_rate"])

    def test_technical_failure_counts_recorded_and_attempted_turn_telemetry(self):
        result = aggregate_model_stats(
            [
                {
                    "status": "technical_failure",
                    "failing_role": "buyer",
                    "failure": {"source": "provider", "failing_role": "buyer"},
                    "seats": [
                        {"role": "buyer", "provider": "openai", "model": "gpt-a"},
                        {"role": "seller", "provider": "qwen", "model": "qwen-b"},
                    ],
                    "turns": [
                        {
                            "step": 1,
                            "role": "seller",
                            "provider": "qwen",
                            "model": "qwen-b",
                            "latency_ms": 100,
                            "usage": {"total_tokens": 10},
                        },
                        {
                            "step": 2,
                            "role": "buyer",
                            "provider": "openai",
                            "model": "gpt-a",
                            "latency_ms": 200,
                            "usage": {"input_tokens": 12, "output_tokens": 8},
                        },
                    ],
                    "attempted_turn": {
                        "step": 3,
                        "role": "buyer",
                        "provider": "openai",
                        "model": "gpt-a",
                        "latency_ms": 400,
                        "usage": {"total_tokens": 40},
                    },
                }
            ]
        )

        openai = result["models"]["openai:gpt-a"]
        qwen = result["models"]["qwen:qwen-b"]
        self.assertEqual(result["technical_failure_runs"], 1)
        self.assertEqual(result["negotiation_outcome_run_count"], 0)
        self.assertEqual(openai["provider_failures"], 1)
        self.assertEqual(qwen["provider_failures"], 0)
        self.assertEqual(openai["outcome_runs"], 0)
        self.assertEqual(qwen["outcome_runs"], 0)
        self.assertEqual(openai["turns"], 2)
        self.assertEqual(openai["total_tokens"], 60.0)
        self.assertEqual(openai["mean_turn_latency_ms"], 300.0)
        self.assertEqual(qwen["turns"], 1)
        self.assertEqual(qwen["total_tokens"], 10.0)
        self.assertEqual(qwen["mean_turn_latency_ms"], 100.0)

    def test_attempted_turn_already_in_turns_is_not_counted_twice(self):
        attempted = {
            "step": 1,
            "role": "buyer",
            "provider": "openai",
            "model": "gpt-a",
            "latency_ms": 25,
            "usage": {"total_tokens": 7},
        }
        result = aggregate_model_stats(
            [
                {
                    "status": "technical_failure",
                    "failing_role": "buyer",
                    "failure": {"source": "provider", "failing_role": "buyer"},
                    "seats": [
                        {"role": "buyer", "provider": "openai", "model": "gpt-a"},
                        {"role": "seller", "provider": "qwen", "model": "qwen-b"},
                    ],
                    "turns": [dict(attempted)],
                    "attempted_turn": attempted,
                }
            ]
        )

        openai = result["models"]["openai:gpt-a"]
        self.assertEqual(openai["turns"], 1)
        self.assertEqual(openai["total_tokens"], 7.0)
        self.assertEqual(openai["mean_turn_latency_ms"], 25.0)


if __name__ == "__main__":
    unittest.main()
