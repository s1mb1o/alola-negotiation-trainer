from __future__ import annotations

import http.client
import json
import os
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from clients.providers import (
    AgentModelConfig,
    OpenAIResponsesProvider,
    ProviderError,
    QwenCloudProvider,
    provider_seed_metadata,
    provider_request_observer,
)


class FakeHttpResponse:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _qwen_response(content: str = "Ready.") -> dict:
    return {
        "id": "chat_ok",
        "model": "qwen3.8-max-2026-01-01",
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": content}}
        ],
        "usage": {"prompt_tokens": 9, "completion_tokens": 5, "total_tokens": 14},
    }


class ProviderTest(unittest.TestCase):
    def test_request_observer_cannot_change_payload_or_interrupt_transport(self):
        sent = []
        def observer(url, body, headers, timeout, attempt):
            body["messages"][0]["content"] = "mutated"
            headers["Authorization"] = "mutated"
            raise RuntimeError("Observer failed")
        def requester(url, body, headers, timeout):
            sent.append((body, headers))
            return _qwen_response()
        token = provider_request_observer.set(observer)
        try:
            with patch.dict(os.environ, {"QWEN_API_KEY": "fixture-key"}):
                result = QwenCloudProvider(requester=requester).generate(
                    [{"role": "user", "content": "original"}])
        finally:
            provider_request_observer.reset(token)
        self.assertEqual(result.text, "Ready.")
        self.assertEqual(sent[0][0]["messages"][0]["content"], "original")
        self.assertEqual(sent[0][1]["Authorization"], "Bearer fixture-key")

    def test_openai_responses_payload_and_output(self):
        captured = {}

        def requester(url, payload, headers, timeout):
            captured.update(url=url, payload=payload, headers=headers, timeout=timeout)
            return {
                "id": "resp_1",
                "model": "gpt-test-2026-02-01",
                "output": [{"content": [{"type": "output_text", "text": "Добрый день."}]}],
                "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
            }

        config = AgentModelConfig(
            provider="openai", model="gpt-test", max_output_tokens=123, seed=42
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-secret"}):
            result = OpenAIResponsesProvider(config, requester=requester).generate(
                [{"role": "user", "content": "Начинайте."}], instructions="Speak naturally."
            )
        self.assertEqual(result.text, "Добрый день.")
        self.assertEqual(result.model, "gpt-test")
        self.assertEqual(result.model_reported, "gpt-test-2026-02-01")
        self.assertEqual(result.retry_count, 0)
        self.assertEqual(captured["url"], "https://api.openai.com/v1/responses")
        self.assertFalse(captured["payload"]["store"])
        self.assertEqual(captured["payload"]["max_output_tokens"], 123)
        self.assertNotIn("temperature", captured["payload"])
        self.assertNotIn("seed", captured["payload"])
        self.assertEqual(
            provider_seed_metadata(OpenAIResponsesProvider(config))["handling"],
            "unsupported_not_sent",
        )
        self.assertNotIn("openai-secret", repr(result))

    def test_openai_empty_output_reports_safe_incomplete_metadata_once(self):
        request_count = 0

        def requester(url, payload, headers, timeout):
            nonlocal request_count
            request_count += 1
            return {
                "id": "resp_empty",
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [],
                "raw_private_detail": "must-not-appear",
            }

        config = AgentModelConfig(provider="openai", model="gpt-test")
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "openai-secret"}, clear=True),
            self.assertRaises(ProviderError) as raised,
        ):
            OpenAIResponsesProvider(config, requester=requester).generate(
                [{"role": "user", "content": "Начинайте."}]
            )

        message = str(raised.exception)
        self.assertIn("status=incomplete", message)
        self.assertIn("incomplete_reason=max_output_tokens", message)
        self.assertNotIn("must-not-appear", message)
        self.assertNotIn("resp_empty", message)
        self.assertNotIn("openai-secret", message)
        self.assertEqual(request_count, 1)
        self.assertEqual(
            raised.exception.failure_diagnostics,
            {"status": "incomplete", "incomplete_reason": "max_output_tokens"},
        )

    def test_qwen_chat_completions_uses_requested_alias(self):
        captured = {}

        def requester(url, payload, headers, timeout):
            captured.update(url=url, payload=payload, headers=headers)
            return {
                "id": "chat_1",
                "choices": [{"message": {"role": "assistant", "content": "I propose a price."}}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 5, "total_tokens": 14},
            }

        config = AgentModelConfig(
            provider="qwen",
            model="qwen3.7-plus",
            seed=42,
            enable_thinking=False,
        )
        with patch.dict(os.environ, {"QWEN_API_KEY": "qwen-secret"}, clear=True):
            result = QwenCloudProvider(config, requester=requester).generate(
                [{"role": "user", "content": "Start."}], instructions="Speak naturally."
            )
        self.assertEqual(result.text, "I propose a price.")
        self.assertIsNone(result.model_reported)
        self.assertEqual(
            captured["url"],
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
        self.assertEqual(captured["payload"]["messages"][0]["role"], "system")
        self.assertEqual(captured["payload"]["seed"], 42)
        self.assertIs(captured["payload"]["enable_thinking"], False)
        metadata = provider_seed_metadata(QwenCloudProvider(config))
        self.assertEqual(metadata["handling"], "passed_to_provider")
        self.assertFalse(metadata["reproducibility_guaranteed"])
        self.assertNotIn("qwen-secret", repr(result))

    def test_qwen_token_plan_key_uses_matching_plan_endpoint(self):
        captured = {}

        def requester(url, payload, headers, timeout):
            captured["url"] = url
            return {
                "id": "chat_plan_1",
                "choices": [{"message": {"role": "assistant", "content": "Ready."}}],
            }

        config = AgentModelConfig(provider="qwen", model="qwen3.7-plus")
        with patch.dict(os.environ, {"QWEN_API_KEY": "sk-sp-test-value"}, clear=True):
            QwenCloudProvider(config, requester=requester).generate(
                [{"role": "user", "content": "Start."}]
            )
        self.assertEqual(
            captured["url"],
            "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/"
            "chat/completions",
        )

    def test_socket_timeout_becomes_safe_provider_error_after_bounded_retries(self):
        config = AgentModelConfig(provider="qwen", model="qwen3.8-flash")
        delays: list[float] = []
        with (
            patch.dict(os.environ, {"QWEN_API_KEY": "qwen-secret"}, clear=True),
            patch(
                "clients.providers.urlopen",
                side_effect=TimeoutError("raw socket detail must not appear"),
            ) as urlopen,
            patch("clients.providers._sleep", side_effect=delays.append),
            self.assertRaises(ProviderError) as raised,
        ):
            QwenCloudProvider(config).generate([{"role": "user", "content": "Start."}])

        self.assertEqual(str(raised.exception), "Provider request timed out")
        self.assertNotIn("raw socket detail", str(raised.exception))
        self.assertNotIn("qwen-secret", str(raised.exception))
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(raised.exception.retry_count, 2)
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(delays, [1.0, 2.0])


class ProviderTransportTest(unittest.TestCase):
    """Every failure below the HTTP layer becomes a safe, typed ProviderError."""

    def _failure(self, **urlopen_patch) -> ProviderError:
        config = AgentModelConfig(provider="qwen", model="qwen-test", max_attempts=1)
        with (
            patch.dict(os.environ, {"QWEN_API_KEY": "qwen-secret"}, clear=True),
            patch("clients.providers.urlopen", **urlopen_patch),
            self.assertRaises(ProviderError) as raised,
        ):
            QwenCloudProvider(config).generate([{"role": "user", "content": "Start."}])
        return raised.exception

    def test_transport_exceptions_become_retryable_provider_errors(self):
        cases = [
            ConnectionResetError(54, "Connection reset by peer"),
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            TimeoutError("The read operation timed out"),
            URLError(OSError(60, "Operation timed out")),
            http.client.IncompleteRead(b"partial-body-must-not-appear"),
            OSError("tls handshake failure"),
        ]
        for exc in cases:
            with self.subTest(exc=type(exc).__name__):
                error = self._failure(side_effect=exc)
                self.assertTrue(error.retryable)
                self.assertIsNone(error.status)
                self.assertNotIn("qwen-secret", str(error))
                self.assertNotIn("partial-body", str(error))
                self.assertNotIn("dashscope", str(error))

    def test_invalid_utf8_and_invalid_json_bodies_become_provider_errors(self):
        for raw, fragment in (
            (b"\xff\xfe\xfd", "not valid UTF-8"),
            (b"<html>x</html>", "invalid JSON"),
        ):
            with self.subTest(fragment=fragment):
                error = self._failure(return_value=FakeHttpResponse(raw))
                self.assertIn(fragment, str(error))
                self.assertFalse(error.retryable)
                self.assertNotIn("<html>", str(error))

    def test_http_statuses_classify_retryability_and_redact_the_key(self):
        cases = [
            (429, json.dumps({"error": {"message": "Rate limit for qwen-secret"}}), True),
            (503, "<html>upstream gateway page</html>", True),
            (400, json.dumps({"error": {"message": "bad request"}}), False),
        ]
        for status, body, retryable in cases:
            with self.subTest(status=status):
                error = self._failure(
                    side_effect=HTTPError(
                        "https://dashscope-intl.aliyuncs.com/x",
                        status,
                        "Reason",
                        {},
                        BytesIO(body.encode("utf-8")),
                    )
                )
                self.assertEqual(error.status, status)
                self.assertEqual(error.retryable, retryable)
                self.assertIn(f"HTTP {status}", str(error))
                self.assertNotIn("qwen-secret", str(error))
                self.assertNotIn("gateway page", str(error))


class ProviderRetryTest(unittest.TestCase):
    def _config(self, **overrides) -> AgentModelConfig:
        values = {
            "provider": "qwen",
            "model": "qwen3.8-max",
            "max_attempts": 3,
            "retry_backoff_seconds": 1.0,
        }
        values.update(overrides)
        return AgentModelConfig(**values)

    def test_rate_limits_are_retried_with_backoff_and_counted(self):
        attempts = 0

        def requester(url, payload, headers, timeout):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ProviderError(
                    "Provider returned HTTP 429: Provider rate limit reached",
                    status=429,
                    retryable=True,
                )
            return _qwen_response()

        delays: list[float] = []
        with (
            patch.dict(os.environ, {"QWEN_API_KEY": "qwen-secret"}, clear=True),
            patch("clients.providers._sleep", side_effect=delays.append),
        ):
            result = QwenCloudProvider(self._config(), requester=requester).generate(
                [{"role": "user", "content": "Start."}]
            )
        self.assertEqual(result.text, "Ready.")
        self.assertEqual(result.retry_count, 2)
        self.assertEqual(result.model_reported, "qwen3.8-max-2026-01-01")
        self.assertEqual(delays, [1.0, 2.0])

    def test_exhausted_retries_raise_with_retry_count(self):
        def requester(url, payload, headers, timeout):
            raise ProviderError("Provider returned HTTP 503: Reason", status=503, retryable=True)

        delays: list[float] = []
        with (
            patch.dict(os.environ, {"QWEN_API_KEY": "qwen-secret"}, clear=True),
            patch("clients.providers._sleep", side_effect=delays.append),
            self.assertRaises(ProviderError) as raised,
        ):
            QwenCloudProvider(self._config(), requester=requester).generate(
                [{"role": "user", "content": "Start."}]
            )
        self.assertEqual(raised.exception.retry_count, 2)
        self.assertEqual(raised.exception.status, 503)
        self.assertEqual(delays, [1.0, 2.0])

    def test_non_retryable_failures_are_not_retried(self):
        attempts = 0

        def requester(url, payload, headers, timeout):
            nonlocal attempts
            attempts += 1
            raise ProviderError("Provider returned HTTP 400: bad request", status=400)

        with (
            patch.dict(os.environ, {"QWEN_API_KEY": "qwen-secret"}, clear=True),
            patch("clients.providers._sleep") as sleep,
            self.assertRaises(ProviderError),
        ):
            QwenCloudProvider(self._config(), requester=requester).generate(
                [{"role": "user", "content": "Start."}]
            )
        self.assertEqual(attempts, 1)
        sleep.assert_not_called()

    def test_max_attempts_one_disables_retries(self):
        attempts = 0

        def requester(url, payload, headers, timeout):
            nonlocal attempts
            attempts += 1
            raise ProviderError("Provider request timed out", retryable=True)

        with (
            patch.dict(os.environ, {"QWEN_API_KEY": "qwen-secret"}, clear=True),
            patch("clients.providers._sleep") as sleep,
            self.assertRaises(ProviderError),
        ):
            QwenCloudProvider(self._config(max_attempts=1), requester=requester).generate(
                [{"role": "user", "content": "Start."}]
            )
        self.assertEqual(attempts, 1)
        sleep.assert_not_called()


class QwenDiagnosticsTest(unittest.TestCase):
    def _empty(self, response: dict) -> tuple[ProviderError, int]:
        request_count = 0

        def requester(url, payload, headers, timeout):
            nonlocal request_count
            request_count += 1
            return response

        config = AgentModelConfig(provider="qwen", model="qwen3.8-max")
        with (
            patch.dict(os.environ, {"QWEN_API_KEY": "qwen-secret"}, clear=True),
            patch("clients.providers._sleep") as sleep,
            self.assertRaises(ProviderError) as raised,
        ):
            QwenCloudProvider(config, requester=requester).generate(
                [{"role": "user", "content": "Start."}]
            )
        sleep.assert_not_called()
        return raised.exception, request_count

    def test_empty_content_reports_finish_reason_and_reasoning_usage(self):
        error, request_count = self._empty(
            {
                "id": "chat_empty",
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "PRIVATE REASONING must not appear",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 500,
                    "completion_tokens_details": {"reasoning_tokens": 500},
                },
            }
        )
        message = str(error)
        self.assertIn("finish_reason=length", message)
        self.assertIn("has_reasoning_content=true", message)
        self.assertIn("reasoning_tokens=500", message)
        self.assertIn("completion_tokens=500", message)
        self.assertNotIn("PRIVATE REASONING", message)
        self.assertNotIn("qwen-secret", message)
        self.assertNotIn("chat_empty", message)
        self.assertEqual(
            error.failure_diagnostics,
            {
                "finish_reason": "length",
                "has_reasoning_content": True,
                "reasoning_tokens": 500,
                "completion_tokens": 500,
            },
        )
        self.assertFalse(error.retryable)
        self.assertEqual(request_count, 1)

    def test_missing_content_without_metadata_reports_unknowns(self):
        error, _ = self._empty(
            {"id": "chat_missing", "choices": [{"message": {"role": "assistant"}}]}
        )
        message = str(error)
        self.assertIn("finish_reason=unknown", message)
        self.assertIn("has_reasoning_content=false", message)
        self.assertIn("reasoning_tokens=unknown", message)
        self.assertIn("completion_tokens=unknown", message)
        self.assertEqual(
            error.failure_diagnostics,
            {
                "finish_reason": "unknown",
                "has_reasoning_content": False,
                "reasoning_tokens": None,
                "completion_tokens": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
