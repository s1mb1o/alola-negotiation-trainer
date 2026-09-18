from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from clients.api import ApiError
from clients.cli import _participant_token, build_parser, main


class CredentialPrecedenceTest(unittest.TestCase):
    def test_fresh_credential_wins_over_the_environment_token(self):
        created = {"participant_credentials": {"buyer": "fresh-token"}}
        with patch.dict(
            os.environ, {"NEGOTIATION_PARTICIPANT_TOKEN": "stale-env-token"}, clear=True
        ):
            token = _participant_token("NEGOTIATION_PARTICIPANT_TOKEN", created, "buyer")
        self.assertEqual(token, "fresh-token")

    def test_environment_token_is_only_a_fallback_and_is_announced(self):
        stderr = io.StringIO()
        with (
            patch.dict(os.environ, {"NEGOTIATION_PARTICIPANT_TOKEN": "env-token"}, clear=True),
            redirect_stderr(stderr),
        ):
            token = _participant_token(
                "NEGOTIATION_PARTICIPANT_TOKEN", {"session_id": "s"}, "buyer"
            )
        self.assertEqual(token, "env-token")
        self.assertIn("NEGOTIATION_PARTICIPANT_TOKEN", stderr.getvalue())
        self.assertNotIn("env-token", stderr.getvalue())

    def test_missing_credential_is_an_api_error(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ApiError):
            _participant_token("NEGOTIATION_PARTICIPANT_TOKEN", {"session_id": "s"}, "buyer")


class ParserTest(unittest.TestCase):
    def test_max_messages_below_one_is_rejected(self):
        for command in ("agent", "self-play"):
            with self.subTest(command=command):
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                    build_parser().parse_args([command, "--scenario", "s", "--max-messages", "0"])
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("--max-messages", stderr.getvalue())
                self.assertIn("at least 1", stderr.getvalue())

    def test_global_options_are_accepted_before_or_after_the_subcommand(self):
        parser = build_parser()
        after = parser.parse_args(
            ["play", "--scenario", "s", "--base-url", "http://after:1", "--api-timeout", "5"]
        )
        self.assertEqual(after.base_url, "http://after:1")
        self.assertEqual(after.api_timeout, 5.0)
        before = parser.parse_args(["--base-url", "http://before:1", "play", "--scenario", "s"])
        self.assertEqual(before.base_url, "http://before:1")
        self.assertEqual(before.api_timeout, 30.0)
        plain = parser.parse_args(["stats"])
        self.assertIsNone(plain.base_url)
        self.assertEqual(plain.api_timeout, 30.0)

    def test_provider_max_attempts_is_configurable(self):
        args = build_parser().parse_args(
            ["self-play", "--scenario", "s", "--provider-max-attempts", "5"]
        )
        self.assertEqual(args.provider_max_attempts, 5)
        self.assertEqual(
            build_parser().parse_args(["agent", "--scenario", "s"]).provider_max_attempts, 3
        )


class PlayLoopApi:
    """Fake client: one created session, then scripted submit outcomes."""

    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple] = []

    def create_session(self, **kwargs):
        self.calls.append(("create_session", kwargs["run_mode"]))
        return {
            "session_id": "sess_play",
            "revision": 0,
            "status": "active",
            "participant_credentials": {"buyer": "fresh-token"},
        }

    def with_participant_token(self, token):
        self.calls.append(("token", token))
        return self

    def submit_message(self, session_id, message, *, expected_revision, idempotency_key=None):
        self.calls.append(("submit", message, expected_revision))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def get_session(self, session_id):
        self.calls.append(("get_session", session_id))
        return {"session_id": session_id, "revision": 5, "status": "active"}

    def review(self, session_id):
        return {"outcome": {"agreement": True}}


class PlayLoopTest(unittest.TestCase):
    def _run(self, api, inputs, env=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch("clients.cli.NegotiationApiClient", return_value=api),
            patch("builtins.input", side_effect=inputs),
            patch.dict(os.environ, env or {}, clear=True),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main(["play", "--scenario", "saas_subscription_ru"])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_domain_error_conflict_and_transport_error_keep_the_loop(self):
        api = PlayLoopApi(
            [
                ApiError(
                    "stale revision", status=409, error="revision_conflict", details={"revision": 5}
                ),
                ApiError("offer is no longer active", status=409, error="offer_not_active"),
                ApiError("Negotiation API request timed out", retryable=True),
                {"revision": 6, "status": "agreement_reached"},
            ]
        )
        code, stdout, stderr = self._run(api, ["first", "second", "third", "fourth"])
        self.assertEqual(code, 0)
        for fragment in ("revision_conflict", "offer_not_active", "timed out"):
            self.assertIn(fragment, stderr)
        submits = [call for call in api.calls if call[0] == "submit"]
        self.assertEqual([call[1] for call in submits], ["first", "second", "third", "fourth"])
        self.assertEqual(submits[0][2], 0)
        self.assertEqual(submits[1][2], 5)
        self.assertIn("agreement_reached", stdout)
        self.assertNotIn("fresh-token", stdout)
        self.assertNotIn("fresh-token", stderr)

    def test_fatal_authentication_error_exits_with_code_2(self):
        api = PlayLoopApi(
            [ApiError("credential rejected", status=401, error="participant_unauthorized")]
        )
        code, _, stderr = self._run(api, ["hello"])
        self.assertEqual(code, 2)
        self.assertIn("participant_unauthorized", stderr)

    def test_new_session_uses_the_fresh_credential_not_the_environment_token(self):
        api = PlayLoopApi([{"revision": 1, "status": "agreement_reached"}])
        code, stdout, _ = self._run(
            api, ["hi"], env={"NEGOTIATION_PARTICIPANT_TOKEN": "stale-env-token"}
        )
        self.assertEqual(code, 0)
        self.assertIn(("token", "fresh-token"), api.calls)
        self.assertNotIn(("token", "stale-env-token"), api.calls)
        self.assertNotIn("fresh-token", stdout)


if __name__ == "__main__":
    unittest.main()
