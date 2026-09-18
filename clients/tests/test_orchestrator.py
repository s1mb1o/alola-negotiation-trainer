from __future__ import annotations

import unittest
from typing import ClassVar
from unittest.mock import patch

from clients.api import ApiError, NegotiationApiClient
from clients.orchestrator import AgentSeat, run_self_play
from clients.providers import AgentModelConfig, Generation, ProviderError


class CapturingProvider:
    def __init__(
        self,
        model: str,
        *,
        seed: int | None = None,
        model_reported: str | None = None,
        retry_count: int = 0,
    ) -> None:
        self.config = AgentModelConfig(provider="mock", model=model, seed=seed)
        self.prompts: list[str] = []
        self.model_reported = model_reported
        self.retry_count = retry_count

    def generate(self, messages, *, instructions=None):
        self.prompts.append((instructions or "") + "\n" + messages[0]["content"])
        return Generation(
            "I propose a price of 1100000.",
            "mock",
            self.config.model,
            1.0,
            {"total_tokens": 5},
            model_reported=self.model_reported,
            retry_count=self.retry_count,
        )


class FailingProvider:
    def __init__(self, model: str, error: ProviderError | None = None) -> None:
        self.config = AgentModelConfig(provider="mock", model=model)
        self.error = error or ProviderError("provider unavailable")

    def generate(self, messages, *, instructions=None):
        raise self.error


class ScopedApi:
    def __init__(self, owner=None, shared=None) -> None:
        self.owner = owner
        self.shared = shared or {
            "revision": 0,
            "next": "opaque-buyer",
            "status": "active",
            "buyer_submits": 0,
            "fail_history_role": None,
            "create_owners": [],
        }
        self.last_retry_count = 0

    def create_session(self, **kwargs):
        self.shared.setdefault("create_owners", []).append(self.owner)
        return {
            "session_id": "sess_1",
            "revision": 0,
            "status": "active",
            "next_actor": "opaque-buyer",
            "participants": [
                {"participant_id": "opaque-buyer", "role": "buyer"},
                {"participant_id": "opaque-seller", "role": "seller"},
            ],
            "participant_credentials": {"buyer": "buyer-token", "seller": "seller-token"},
            "observation": {"role_brief": "CREATOR_ONLY"},
        }

    def with_participant_token(self, token):
        role = {"buyer-token": "buyer", "seller-token": "seller"}.get(token, "admin")
        return ScopedApi(role, self.shared)

    def get_session(self, session_id):
        role_secret = "BUYER_SECRET" if self.owner == "buyer" else "SELLER_SECRET"
        return {
            "session_id": session_id,
            "revision": self.shared["revision"],
            "status": self.shared["status"],
            "next_actor": self.shared["next"],
            "observation": {"role_brief": role_secret},
        }

    def history(self, session_id):
        if self.shared.get("fail_history_role") == self.owner:
            raise ApiError(
                "history failed",
                status=503,
                code="HISTORY_DOWN",
                error="service_unavailable",
            )
        return {
            "revision": self.shared["revision"],
            "conversation": [],
            "visible_to": self.owner,
        }

    def submit_message(self, session_id, message, *, expected_revision, idempotency_key=None):
        self.assert_revision(expected_revision)
        if self.owner == "buyer":
            self.shared["buyer_submits"] += 1
            if self.shared["buyer_submits"] == 1:
                self.shared.update(revision=1, next="opaque-buyer", status="active")
                return {
                    "result": "confirmation_required",
                    "revision": 1,
                    "status": "active",
                    "next_actor": "opaque-buyer",
                    "pending_confirmation": {"marker": "PENDING_BUYER_ONLY"},
                    "observation": {"role_brief": "BUYER_RESPONSE_SECRET"},
                }
            self.shared.update(revision=2, next="opaque-seller", status="active")
            return {
                "result": "turn_committed",
                "revision": 2,
                "status": "active",
                "next_actor": "opaque-seller",
                "observation": {"role_brief": "BUYER_RESPONSE_SECRET"},
            }
        self.shared.update(revision=3, next=None, status="agreement_reached")
        return {"revision": 3, "status": "agreement_reached", "next_actor": None, "observation": {}}

    def assert_revision(self, expected):
        if expected != self.shared["revision"]:
            raise AssertionError((expected, self.shared["revision"]))

    def review(self, session_id):
        return {
            "outcome": {"agreement": True, "participant_utilities": {"buyer": 70, "seller": 65}}
        }

    def close_session(
        self, session_id, *, expected_revision, reason, admin_token, idempotency_key=None
    ):
        self.assert_revision(expected_revision)
        if admin_token != "test-admin":
            raise AssertionError("wrong admin token")
        self.shared.update(
            revision=self.shared["revision"] + 1,
            next=None,
            status="aborted",
        )
        return {
            "session_id": session_id,
            "revision": self.shared["revision"],
            "status": "aborted",
            "next_actor": None,
        }


class DomainErrorApi(ScopedApi):
    def __init__(
        self,
        error_code: str,
        owner=None,
        shared=None,
        *,
        error_next_actor: str | None = "opaque-buyer",
    ) -> None:
        if shared is None:
            shared = {
                "revision": 0,
                "next": "opaque-buyer",
                "status": "active",
                "buyer_submits": 0,
                "fail_history_role": None,
                "domain_error_raised": False,
                "domain_error": error_code,
                "error_next_actor": error_next_actor,
                "submitted_revisions": [],
                "create_owners": [],
            }
        super().__init__(owner, shared)

    def with_participant_token(self, token):
        role = {"buyer-token": "buyer", "seller-token": "seller"}.get(token, "admin")
        return DomainErrorApi(self.shared["domain_error"], role, self.shared)

    def submit_message(self, session_id, message, *, expected_revision, idempotency_key=None):
        self.shared["submitted_revisions"].append(expected_revision)
        self.assert_revision(expected_revision)
        if self.owner == "buyer" and not self.shared["domain_error_raised"]:
            self.shared["domain_error_raised"] = True
            self.shared.update(
                revision=1,
                next=self.shared["error_next_actor"],
                status="active",
            )
            error = self.shared["domain_error"]
            raise ApiError(
                "recorded domain transition failed",
                status=409,
                error=error,
                details={
                    "error": error,
                    "revision": 1,
                    "status": "active",
                    "next_actor": self.shared["error_next_actor"],
                    "observation": {"role_brief": "ERROR_PAYLOAD_SECRET"},
                    "participant_token": "leak-token",
                },
            )
        if self.owner == "buyer":
            self.shared.update(revision=2, next="opaque-seller", status="active")
            return {
                "result": "turn_committed",
                "revision": 2,
                "status": "active",
                "next_actor": "opaque-seller",
                "observation": {"role_brief": "BUYER_RESPONSE_SECRET"},
            }
        self.shared.update(revision=3, next=None, status="agreement_reached")
        return {
            "revision": 3,
            "status": "agreement_reached",
            "next_actor": None,
            "observation": {},
        }


class ScriptedBackend:
    """A tiny backend behind the real client: one buyer turn, then one seller turn."""

    ROLES: ClassVar[dict[str, str]] = {"buyer-token": "buyer", "seller-token": "seller"}

    def __init__(
        self,
        *,
        fail_first_submit: bool = False,
        commit_before_failure: bool = False,
        reject_create: ApiError | None = None,
    ) -> None:
        self.calls: list[tuple[str, str, object, dict[str, str]]] = []
        self.revision = 0
        self.next_actor = "opaque-buyer"
        self.status = "active"
        self.submits = 0
        self.events: list[dict[str, str]] = []
        self.fail_first_submit = fail_first_submit
        self.commit_before_failure = commit_before_failure
        self.reject_create = reject_create

    def __call__(self, method, url, payload, headers, timeout):
        headers = dict(headers)
        self.calls.append((method, url, payload, headers))
        path = url.removeprefix("http://test")
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        if method == "POST" and path == "/api/v1/sessions":
            if self.reject_create is not None:
                raise self.reject_create
            return {
                "session_id": "sess_1",
                "revision": 0,
                "status": "active",
                "next_actor": "opaque-buyer",
                "participants": [
                    {"participant_id": "opaque-buyer", "role": "buyer"},
                    {"participant_id": "opaque-seller", "role": "seller"},
                ],
                "participant_credentials": [
                    {"role": "buyer", "token": "buyer-token"},
                    {"role": "seller", "token": "seller-token"},
                ],
                "observation": {},
            }
        if method == "POST" and path == "/api/v1/sessions/sess_1/messages":
            self.submits += 1
            if self.fail_first_submit and self.submits == 1:
                if self.commit_before_failure:
                    self._commit(token, payload["message"])
                raise ApiError("Negotiation API request timed out", retryable=True)
            if payload["expected_revision"] != self.revision:
                raise ApiError(
                    "expected_revision does not match the session revision",
                    status=409,
                    error="revision_conflict",
                    details={"error": "revision_conflict", "revision": self.revision},
                )
            return self._commit(token, payload["message"])
        if method == "POST" and path == "/api/v1/sessions/sess_1/close":
            self.revision += 1
            self.status = "aborted"
            self.next_actor = None
            return {"session_id": "sess_1", "revision": self.revision, "status": "aborted"}
        if method == "GET" and path == "/api/v1/sessions/sess_1":
            return {
                "session_id": "sess_1",
                "revision": self.revision,
                "status": self.status,
                "next_actor": self.next_actor,
                "observation": {"visible_to": self.ROLES.get(token)},
            }
        if method == "GET" and path == "/api/v1/sessions/sess_1/history":
            return {"revision": self.revision, "events": list(self.events)}
        if method == "GET" and path == "/api/v1/sessions/sess_1/review":
            return {"outcome": {"agreement": self.status == "agreement_reached"}}
        raise AssertionError(f"unexpected call {method} {path}")

    def _commit(self, token, message):
        role = self.ROLES[token]
        self.events.append({"role": role, "text": message})
        self.revision += 1
        if role == "buyer":
            self.next_actor = "opaque-seller"
        else:
            self.next_actor = None
            self.status = "agreement_reached"
        return {
            "result": "turn_committed",
            "revision": self.revision,
            "status": self.status,
            "next_actor": self.next_actor,
        }

    def requests(self, method: str, suffix: str) -> list[tuple[str, str, object, dict[str, str]]]:
        return [call for call in self.calls if call[0] == method and call[1].endswith(suffix)]


def _seats() -> list[AgentSeat]:
    return [
        AgentSeat("buyer", CapturingProvider("buyer-model")),
        AgentSeat("seller", CapturingProvider("seller-model")),
    ]


class OrchestratorActorSafetyTest(unittest.TestCase):
    def test_each_provider_receives_only_its_actor_scoped_observation(self):
        buyer = CapturingProvider("buyer-model")
        seller = CapturingProvider("seller-model")
        with patch.dict("os.environ", {}, clear=True):
            result = run_self_play(
                ScopedApi(),
                scenario_id="saas_subscription_en",
                scenario_version=1,
                language="en",
                seats=[AgentSeat("buyer", buyer), AgentSeat("seller", seller)],
                max_messages=4,
                benchmark_run_id="bench_1",
                trial_id="trial_1",
                seed=1,
            )
        self.assertEqual(result["status"], "agreement_reached")
        self.assertEqual(set(result["reviews_by_role"]), {"buyer", "seller"})
        self.assertEqual(set(result["history_by_role"]), {"buyer", "seller"})
        self.assertIn("BUYER_SECRET", buyer.prompts[0])
        self.assertEqual(buyer.prompts[0].count("BUYER_SECRET"), 1)
        self.assertEqual(len(buyer.prompts), 2)
        self.assertIn("confirmation_required", buyer.prompts[1])
        self.assertIn("PENDING_BUYER_ONLY", buyer.prompts[1])
        self.assertNotIn("SELLER_SECRET", buyer.prompts[0])
        self.assertIn("SELLER_SECRET", seller.prompts[0])
        self.assertNotIn("BUYER_SECRET", seller.prompts[0])
        self.assertNotIn("BUYER_RESPONSE_SECRET", seller.prompts[0])
        self.assertNotIn("PENDING_BUYER_ONLY", seller.prompts[0])
        self.assertNotIn("buyer-token", repr(result))
        self.assertNotIn("seller-token", repr(result))

    def test_provider_failure_preserves_partial_run_and_closes_session(self):
        api = ScopedApi()
        with patch.dict("os.environ", {"NEGOTIATION_ADMIN_TOKEN": "test-admin"}, clear=True):
            result = run_self_play(
                api,
                scenario_id="saas_subscription_en",
                scenario_version=1,
                language="en",
                seats=[
                    AgentSeat("buyer", CapturingProvider("buyer-model")),
                    AgentSeat("seller", FailingProvider("seller-model")),
                ],
                max_messages=4,
                benchmark_run_id="bench_failure",
                trial_id="trial_failure",
                seed=7,
            )
        self.assertEqual(result["status"], "technical_failure")
        self.assertEqual(result["session_status"], "aborted")
        self.assertEqual(result["session_id"], "sess_1")
        self.assertEqual(result["failing_role"], "seller")
        self.assertEqual(result["failure"]["source"], "provider")
        self.assertEqual(result["failure"]["retry_count"], 0)
        self.assertEqual(len(result["turns"]), 2)
        self.assertEqual(set(result["history_by_role"]), {"buyer", "seller"})
        self.assertTrue(result["administrative_close"]["closed"])
        self.assertEqual(api.shared["create_owners"], ["admin"])
        self.assertNotIn("test-admin", repr(result))

    def test_api_and_max_message_failures_keep_role_and_history(self):
        api = ScopedApi()
        api.shared["fail_history_role"] = "buyer"
        with patch.dict("os.environ", {}, clear=True):
            api_failure = run_self_play(
                api,
                scenario_id="saas_subscription_en",
                scenario_version=1,
                language="en",
                seats=_seats(),
                max_messages=4,
                benchmark_run_id="bench_api_failure",
                trial_id="trial_api_failure",
                seed=8,
            )
        self.assertEqual(api_failure["failing_role"], "buyer")
        self.assertEqual(api_failure["failure"]["source"], "api")
        self.assertEqual(api_failure["failure"]["backend_error"], "service_unavailable")
        self.assertIn("buyer", api_failure["history_by_role"])

        with patch.dict("os.environ", {}, clear=True):
            limit_failure = run_self_play(
                ScopedApi(),
                scenario_id="saas_subscription_en",
                scenario_version=1,
                language="en",
                seats=_seats(),
                max_messages=1,
                benchmark_run_id="bench_limit",
                trial_id="trial_limit",
                seed=9,
            )
        self.assertEqual(limit_failure["failing_role"], "buyer")
        self.assertEqual(limit_failure["failure"]["source"], "orchestrator_limit")
        self.assertEqual(len(limit_failure["turns"]), 1)
        self.assertFalse(limit_failure["administrative_close"]["attempted"])

    def test_recorded_offer_errors_give_the_same_actor_a_clarification_turn(self):
        for error in ("offer_not_bindable", "offer_not_active", "offer_not_owned"):
            with self.subTest(error=error):
                api = DomainErrorApi(error)
                buyer = CapturingProvider("buyer-model")
                seller = CapturingProvider("seller-model")
                with patch.dict("os.environ", {}, clear=True):
                    result = run_self_play(
                        api,
                        scenario_id="saas_subscription_en",
                        scenario_version=1,
                        language="en",
                        seats=[AgentSeat("buyer", buyer), AgentSeat("seller", seller)],
                        max_messages=3,
                        benchmark_run_id=f"bench_{error}",
                        trial_id=f"trial_{error}",
                    )

                self.assertEqual(result["status"], "agreement_reached")
                self.assertEqual(api.shared["submitted_revisions"], [0, 1, 2])
                self.assertEqual(
                    [turn["role"] for turn in result["turns"]], ["buyer", "buyer", "seller"]
                )
                marker = result["turns"][0]["api_result"]
                self.assertEqual(
                    set(marker),
                    {
                        "recorded",
                        "result",
                        "error",
                        "revision",
                        "status",
                        "next_actor",
                        "same_actor_retry",
                    },
                )
                self.assertTrue(marker["recorded"])
                self.assertEqual(marker["error"], error)
                self.assertEqual(marker["revision"], 1)
                self.assertEqual(len(buyer.prompts), 2)
                self.assertIn("clarification_required", buyer.prompts[1])
                self.assertIn(error, buyer.prompts[1])
                self.assertNotIn("ERROR_PAYLOAD_SECRET", buyer.prompts[1])
                self.assertNotIn("leak-token", repr(result))

    def test_nonrecoverable_api_errors_still_abort(self):
        for error in (
            "revision_conflict",
            "not_your_turn",
            "authentication_required",
            "service_unavailable",
        ):
            with self.subTest(error=error):
                api = DomainErrorApi(error)
                buyer = CapturingProvider("buyer-model")
                with patch.dict("os.environ", {}, clear=True):
                    result = run_self_play(
                        api,
                        scenario_id="saas_subscription_en",
                        scenario_version=1,
                        language="en",
                        seats=[
                            AgentSeat("buyer", buyer),
                            AgentSeat("seller", CapturingProvider("seller-model")),
                        ],
                        max_messages=3,
                        benchmark_run_id=f"bench_{error}",
                        trial_id=f"trial_{error}",
                    )

                self.assertEqual(result["status"], "technical_failure")
                self.assertEqual(result["failing_role"], "buyer")
                self.assertEqual(result["failure"]["backend_error"], error)
                self.assertEqual(result["turns"], [])
                self.assertIsNotNone(result["attempted_turn"])
                self.assertEqual(result["attempted_turn"]["api_retry_count"], 0)
                self.assertEqual(len(buyer.prompts), 1)


class OrchestratorTelemetryTest(unittest.TestCase):
    def test_turns_record_reported_model_retry_counts_and_seat_seeds(self):
        buyer = CapturingProvider("buyer-model", seed=11, model_reported="buyer-model-2026")
        seller = CapturingProvider("seller-model", seed=12, retry_count=2)
        with patch.dict("os.environ", {}, clear=True):
            result = run_self_play(
                ScopedApi(),
                scenario_id="saas_subscription_en",
                scenario_version=1,
                language="en",
                seats=[AgentSeat("buyer", buyer), AgentSeat("seller", seller)],
                max_messages=4,
                benchmark_run_id="bench_telemetry",
                trial_id="trial_telemetry",
                seed=11,
            )
        self.assertEqual(result["seed"], 11)
        self.assertEqual(result["seat_seeds"], {"buyer": 11, "seller": 12})
        buyer_turn, seller_turn = result["turns"][0], result["turns"][-1]
        self.assertEqual(buyer_turn["model"], "buyer-model")
        self.assertEqual(buyer_turn["model_reported"], "buyer-model-2026")
        self.assertEqual(buyer_turn["retry_count"], 0)
        self.assertEqual(buyer_turn["api_retry_count"], 0)
        self.assertIsNone(seller_turn["model_reported"])
        self.assertEqual(seller_turn["retry_count"], 2)

    def test_provider_failure_record_keeps_diagnostics_and_retry_count(self):
        error = ProviderError(
            "Qwen response did not contain message content (finish_reason=length, ...)",
            failure_diagnostics={
                "finish_reason": "length",
                "has_reasoning_content": True,
                "reasoning_tokens": 500,
                "completion_tokens": 500,
            },
            retry_count=0,
        )
        rate_limited = ProviderError(
            "Provider returned HTTP 429: Provider rate limit reached",
            status=429,
            retryable=True,
            retry_count=2,
        )
        for exc, expected in (
            (error, {"retry_count": 0, "provider_http_status": None}),
            (rate_limited, {"retry_count": 2, "provider_http_status": 429}),
        ):
            with self.subTest(message=str(exc)), patch.dict("os.environ", {}, clear=True):
                result = run_self_play(
                    ScopedApi(),
                    scenario_id="saas_subscription_en",
                    scenario_version=1,
                    language="en",
                    seats=[
                        AgentSeat("buyer", FailingProvider("buyer-model", exc)),
                        AgentSeat("seller", CapturingProvider("seller-model")),
                    ],
                    max_messages=4,
                    benchmark_run_id="bench_diag",
                    trial_id="trial_diag",
                )
            failure = result["failure"]
            self.assertEqual(failure["source"], "provider")
            self.assertEqual(failure["failing_role"], "buyer")
            self.assertEqual(failure["retry_count"], expected["retry_count"])
            self.assertEqual(failure["provider_http_status"], expected["provider_http_status"])
            if exc is error:
                self.assertEqual(failure["failure_diagnostics"], exc.failure_diagnostics)
            else:
                self.assertNotIn("failure_diagnostics", failure)


class OrchestratorTransportTest(unittest.TestCase):
    """Runs through the real client with a scripted transport."""

    def _run(self, backend: ScriptedBackend, *, run_mode: str = "benchmark", env=None):
        api = NegotiationApiClient("http://test", transport=backend)
        with (
            patch.dict("os.environ", env or {}, clear=True),
            patch("clients.api._sleep") as sleep,
        ):
            result = run_self_play(
                api,
                scenario_id="saas_subscription_en",
                scenario_version=1,
                language="en",
                seats=_seats(),
                max_messages=4,
                run_mode=run_mode,
                benchmark_run_id="bench_transport",
                trial_id="trial_transport",
                seed=3,
            )
        return result, sleep

    def test_benchmark_creation_sends_the_admin_bearer_header(self):
        backend = ScriptedBackend()
        result, _ = self._run(backend, env={"NEGOTIATION_ADMIN_TOKEN": "test-admin"})
        self.assertEqual(result["status"], "agreement_reached")
        (create,) = backend.requests("POST", "/api/v1/sessions")
        self.assertEqual(create[3]["Authorization"], "Bearer test-admin")
        self.assertEqual(create[2]["run_mode"], "benchmark")
        participant_calls = backend.requests("GET", "/api/v1/sessions/sess_1")
        self.assertTrue(participant_calls)
        for call in participant_calls:
            self.assertIn(call[3]["Authorization"], {"Bearer buyer-token", "Bearer seller-token"})
        self.assertNotIn("test-admin", repr(result))

    def test_training_creation_and_missing_admin_token_send_no_admin_header(self):
        for run_mode, env in (
            ("training", {"NEGOTIATION_ADMIN_TOKEN": "test-admin"}),
            ("benchmark", {}),
        ):
            with self.subTest(run_mode=run_mode, env=env):
                backend = ScriptedBackend()
                self._run(backend, run_mode=run_mode, env=env)
                (create,) = backend.requests("POST", "/api/v1/sessions")
                self.assertNotIn("Authorization", create[3])

    def test_creation_401_names_the_admin_token_variable(self):
        backend = ScriptedBackend(
            reject_create=ApiError(
                "A valid administrator Bearer credential is required",
                status=401,
                error="administrator_unauthorized",
            )
        )
        with self.assertRaises(ApiError) as raised:
            self._run(backend, env={"NEGOTIATION_ADMIN_TOKEN": "wrong-admin"})
        self.assertEqual(raised.exception.status, 401)
        self.assertEqual(raised.exception.error, "administrator_unauthorized")
        self.assertIn("NEGOTIATION_ADMIN_TOKEN", str(raised.exception))
        self.assertNotIn("wrong-admin", str(raised.exception))

    def test_transport_failure_on_submit_retries_with_the_same_key(self):
        backend = ScriptedBackend(fail_first_submit=True)
        result, sleep = self._run(backend)
        self.assertEqual(result["status"], "agreement_reached")
        submits = backend.requests("POST", "/messages")
        self.assertEqual(len(submits), 3)
        self.assertEqual(submits[0][2]["idempotency_key"], submits[1][2]["idempotency_key"])
        self.assertNotEqual(submits[1][2]["idempotency_key"], submits[2][2]["idempotency_key"])
        self.assertEqual([turn["api_retry_count"] for turn in result["turns"]], [1, 0])
        self.assertEqual(sleep.call_count, 1)

    def test_conflict_after_an_ambiguous_submit_refetches_the_scoped_state(self):
        backend = ScriptedBackend(fail_first_submit=True, commit_before_failure=True)
        result, _ = self._run(backend)
        self.assertEqual(result["status"], "agreement_reached")
        self.assertEqual([turn["role"] for turn in result["turns"]], ["buyer", "seller"])
        marker = result["turns"][0]["api_result"]
        self.assertEqual(marker["result"], "revision_conflict")
        self.assertTrue(marker["ambiguous_submit"])
        self.assertTrue(marker["recovered_from_scoped_state"])
        self.assertEqual(marker["expected_revision"], 0)
        self.assertEqual(marker["revision"], 1)
        self.assertEqual(marker["next_actor"], "opaque-seller")
        self.assertEqual(result["turns"][0]["api_retry_count"], 1)
        self.assertEqual(len(backend.events), 2)


if __name__ == "__main__":
    unittest.main()
