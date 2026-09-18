from __future__ import annotations

import http.client
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from clients.api import (
    ApiError,
    NegotiationApiClient,
    _error_fields,
    redact_secrets,
    retry_delay_seconds,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, method, url, payload, headers, timeout):
        self.calls.append((method, url, payload, dict(headers), timeout))
        if url.endswith("/history"):
            return {"events": [], "participant_token": "must-not-export"}
        if url.endswith("/review"):
            return {"outcome": {"agreement": True}, "secret": "must-not-export"}
        if url.endswith("/messages"):
            return {"revision": 2, "status": "active"}
        return {"session_id": "sess_1", "revision": 0, "status": "active"}


class FakeHttpResponse:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class ApiClientTest(unittest.TestCase):
    def test_default_port_and_natural_language_message_contract(self):
        transport = RecordingTransport()
        with patch.dict(os.environ, {}, clear=True):
            client = NegotiationApiClient(transport=transport)
        self.assertEqual(client.base_url, "http://127.0.0.1:8170")
        client.submit_message("sess/1", "Согласен только со сроком.", expected_revision=1)
        method, url, payload, _, _ = transport.calls[-1]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "http://127.0.0.1:8170/api/v1/sessions/sess%2F1/messages")
        self.assertEqual(payload["message"], "Согласен только со сроком.")
        self.assertNotIn("actor", payload)
        self.assertNotIn("action", payload)

    def test_benchmark_metadata_has_no_api_keys(self):
        transport = RecordingTransport()
        client = NegotiationApiClient("http://test", transport=transport)
        client.create_session(
            scenario_id="saas_subscription_ru",
            language="ru",
            participants=[
                {
                    "role": "buyer",
                    "controller": "external_agent",
                    "provider": "openai",
                    "model": "gpt-5.6-luna",
                    "prompt_version": "v1",
                },
                {
                    "role": "seller",
                    "controller": "external_agent",
                    "provider": "qwen",
                    "model": "qwen3.7-plus",
                    "prompt_version": "v1",
                },
            ],
            run_mode="benchmark",
            benchmark_run_id="bench_1",
            trial_id="trial_1",
            benchmark_expected_trials=2,
            seed=42,
        )
        payload = transport.calls[-1][2]
        self.assertEqual(payload["benchmark_run_id"], "bench_1")
        self.assertEqual(payload["trial_id"], "trial_1")
        self.assertEqual(payload["benchmark_expected_trials"], 2)
        self.assertEqual(payload["seed"], 42)
        self.assertNotIn("api_key", json.dumps(payload))

    def test_export_redacts_credential_fields_and_values(self):
        transport = RecordingTransport()
        client = NegotiationApiClient(
            "http://test", participant_token="must-not-export", transport=transport
        )
        with tempfile.TemporaryDirectory() as directory:
            path = client.export_session("sess_1", Path(directory) / "session.json")
            content = path.read_text(encoding="utf-8")
        self.assertNotIn("must-not-export", content)
        self.assertIn("[REDACTED]", content)

    def test_redaction_preserves_usage_metrics(self):
        value = redact_secrets(
            {
                "participant_token": "secret-value",
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 4,
                    "total_tokens": 16,
                },
            }
        )
        self.assertEqual(value["participant_token"], "[REDACTED]")
        self.assertEqual(value["usage"]["total_tokens"], 16)

    def test_backend_error_and_code_remain_distinct(self):
        message, code, error = _error_fields(
            {
                "error": "revision_conflict",
                "code": "SESSION_409",
                "message": "The revision is stale.",
            },
            "fallback",
        )
        exc = ApiError(message, status=409, code=code, error=error)
        self.assertEqual(exc.error, "revision_conflict")
        self.assertEqual(exc.code, "SESSION_409")
        self.assertIn("revision_conflict / SESSION_409", str(exc))


class TransportErrorTest(unittest.TestCase):
    """Every failure below the HTTP layer becomes a safe, typed ApiError."""

    def _client(self) -> NegotiationApiClient:
        return NegotiationApiClient(
            "http://test", participant_token="participant-secret", max_attempts=1
        )

    def test_transport_exceptions_become_retryable_api_errors(self):
        cases = [
            ConnectionResetError(54, "Connection reset by peer"),
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            TimeoutError("The read operation timed out"),
            URLError(ConnectionRefusedError(61, "Connection refused")),
            http.client.IncompleteRead(b"partial-body-must-not-appear"),
            OSError("tls handshake failure"),
        ]
        for exc in cases:
            with self.subTest(exc=type(exc).__name__):
                with (
                    patch("clients.api.urlopen", side_effect=exc),
                    self.assertRaises(ApiError) as raised,
                ):
                    self._client().get_session("sess_1")
                message = str(raised.exception)
                self.assertTrue(raised.exception.retryable)
                self.assertIsNone(raised.exception.status)
                self.assertNotIn("participant-secret", message)
                self.assertNotIn("partial-body", message)
                self.assertNotIn("http://test", message)

    def test_invalid_utf8_and_non_json_success_bodies_become_api_errors(self):
        cases = [
            (b"\xff\xfe\xfd", "not valid UTF-8"),
            (b"<html>secret page</html>", "not valid JSON"),
        ]
        for raw, fragment in cases:
            with self.subTest(fragment=fragment):
                with (
                    patch("clients.api.urlopen", return_value=FakeHttpResponse(raw)),
                    self.assertRaises(ApiError) as raised,
                ):
                    self._client().get_session("sess_1")
                self.assertIn(fragment, str(raised.exception))
                self.assertNotIn("secret page", str(raised.exception))
                self.assertFalse(raised.exception.retryable)

    def test_http_error_with_non_json_body_keeps_status_without_the_body(self):
        error = HTTPError(
            "http://test/api/v1/sessions/sess_1",
            502,
            "Bad Gateway",
            {},
            BytesIO(b"<html>gateway page</html>"),
        )
        with (
            patch("clients.api.urlopen", side_effect=error),
            self.assertRaises(ApiError) as raised,
        ):
            self._client().get_session("sess_1")
        self.assertEqual(raised.exception.status, 502)
        self.assertEqual(raised.exception.message, "Bad Gateway")
        self.assertFalse(raised.exception.retryable)
        self.assertNotIn("gateway page", str(raised.exception))

    def test_http_error_without_a_body_keeps_status_and_reason(self):
        error = HTTPError("http://test/x", 503, "Service Unavailable", {}, None)
        with (
            patch("clients.api.urlopen", side_effect=error),
            self.assertRaises(ApiError) as raised,
        ):
            self._client().stats()
        self.assertEqual(raised.exception.status, 503)
        self.assertEqual(raised.exception.message, "Service Unavailable")
        self.assertEqual(raised.exception.details, {})

    def test_backend_json_errors_keep_identifiers(self):
        body = json.dumps(
            {"error": "revision_conflict", "message": "stale revision", "revision": 4}
        ).encode("utf-8")
        error = HTTPError("http://test/x", 409, "Conflict", {}, BytesIO(body))
        with (
            patch("clients.api.urlopen", side_effect=error),
            self.assertRaises(ApiError) as raised,
        ):
            self._client().submit_message("sess_1", "hi", expected_revision=3)
        self.assertEqual(raised.exception.error, "revision_conflict")
        self.assertEqual(raised.exception.details["revision"], 4)
        self.assertFalse(raised.exception.retryable)


class RetryTest(unittest.TestCase):
    def test_backoff_schedule_doubles(self):
        self.assertEqual([retry_delay_seconds(n, 1.0) for n in (1, 2, 3)], [1.0, 2.0, 4.0])

    def test_transport_failure_is_retried_with_the_same_idempotency_key(self):
        calls: list[tuple] = []

        def transport(method, url, payload, headers, timeout):
            calls.append((method, url, payload))
            if len(calls) < 3:
                raise ApiError("Negotiation API request timed out", retryable=True)
            return {"revision": 2, "status": "active"}

        delays: list[float] = []
        with patch("clients.api._sleep", side_effect=delays.append):
            client = NegotiationApiClient(
                "http://test", transport=transport, max_attempts=3, retry_backoff_seconds=1.0
            )
            result = client.submit_message("sess_1", "Hello", expected_revision=1)
        self.assertEqual(result["revision"], 2)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len({call[2]["idempotency_key"] for call in calls}), 1)
        self.assertEqual(delays, [1.0, 2.0])
        self.assertEqual(client.last_retry_count, 2)

    def test_retries_stop_after_max_attempts_and_report_the_count(self):
        def transport(method, url, payload, headers, timeout):
            raise ApiError("Cannot reach negotiation API: refused", retryable=True)

        delays: list[float] = []
        with (
            patch("clients.api._sleep", side_effect=delays.append),
            self.assertRaises(ApiError) as raised,
        ):
            NegotiationApiClient("http://test", transport=transport, max_attempts=3).get_session(
                "sess_1"
            )
        self.assertEqual(raised.exception.retry_count, 2)
        self.assertEqual(delays, [1.0, 2.0])

    def test_domain_errors_are_not_retried(self):
        calls = 0

        def transport(method, url, payload, headers, timeout):
            nonlocal calls
            calls += 1
            raise ApiError("stale", status=409, error="revision_conflict")

        with (
            patch("clients.api._sleep") as sleep,
            self.assertRaises(ApiError),
        ):
            NegotiationApiClient("http://test", transport=transport).submit_message(
                "sess_1", "Hello", expected_revision=1
            )
        self.assertEqual(calls, 1)
        sleep.assert_not_called()

    def test_pending_npc_render_is_retried_with_the_same_key(self):
        calls: list[tuple] = []

        def transport(method, url, payload, headers, timeout):
            calls.append((method, url, payload))
            if len(calls) == 1:
                raise ApiError("render pending", status=409, error="npc_render_pending")
            return {"revision": 3, "status": "active"}

        delays: list[float] = []
        with patch("clients.api._sleep", side_effect=delays.append):
            result = NegotiationApiClient("http://test", transport=transport).submit_message(
                "sess_1", "Hello", expected_revision=2, idempotency_key="cmd_fixed"
            )
        self.assertEqual(result["revision"], 3)
        self.assertEqual([call[2]["idempotency_key"] for call in calls], ["cmd_fixed", "cmd_fixed"])
        self.assertEqual(delays, [1.0])


if __name__ == "__main__":
    unittest.main()
