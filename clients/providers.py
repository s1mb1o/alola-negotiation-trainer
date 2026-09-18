"""LLM provider adapters for external negotiation agents."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import time
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .api import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    TRANSPORT_FAILURES,
    http_error_body,
    redact_secrets,
    retry_delay_seconds,
    transport_failure_reason,
)


ProviderRequest = Callable[
    [str, Mapping[str, Any], Mapping[str, str], float],
    Mapping[str, Any],
]

# Tests replace this hook to avoid real delays.
_sleep = time.sleep

_ERROR_MESSAGE_LIMIT = 300


class ProviderError(RuntimeError):
    """A provider failure that never includes an API key."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
        failure_diagnostics: Mapping[str, Any] | None = None,
        retry_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.failure_diagnostics = (
            dict(failure_diagnostics) if failure_diagnostics is not None else None
        )
        self.retry_count = retry_count


@dataclass(frozen=True, slots=True)
class AgentModelConfig:
    """Configuration for one external negotiation-agent model."""

    provider: str
    model: str
    api_key_env: str | None = None
    base_url: str | None = None
    max_output_tokens: int = 500
    temperature: float | None = None
    seed: int | None = None
    timeout: float = 60.0
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS


@dataclass(frozen=True, slots=True)
class Generation:
    """A provider-neutral generated message and safe telemetry."""

    text: str
    provider: str
    model: str
    latency_ms: float
    usage: Mapping[str, int | float] = field(default_factory=dict)
    request_id: str | None = None
    model_reported: str | None = None
    retry_count: int = 0


class TextProvider(Protocol):
    config: AgentModelConfig
    SEED_PARAMETER_SUPPORTED: bool

    def generate(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        instructions: str | None = None,
    ) -> Generation: ...


def provider_seed_metadata(provider: TextProvider) -> dict[str, Any]:
    """Describe seed handling without claiming deterministic reproduction."""

    requested = provider.config.seed
    supported = bool(getattr(provider, "SEED_PARAMETER_SUPPORTED", False))
    if requested is None:
        handling = "not_requested"
    elif supported:
        handling = "passed_to_provider"
    else:
        handling = "unsupported_not_sent"
    return {
        "requested_seed": requested,
        "provider_support": "supported" if supported else "unsupported",
        "handling": handling,
        "reproducibility_guaranteed": False,
    }


def _provider_error_payload(payload: Any, fallback: str, secret: str) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
        else:
            message = error or payload.get("message")
        if message:
            return str(redact_secrets(str(message), (secret,)))[:_ERROR_MESSAGE_LIMIT]
    return fallback


def _retryable_status(status: int) -> bool:
    return status == 429 or 500 <= status < 600


def _post_json(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout: float,
) -> Mapping[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers=dict(headers), method="POST")
    secret = headers.get("Authorization", "").removeprefix("Bearer ")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        error_body = http_error_body(exc).decode("utf-8", errors="replace")
        try:
            parsed_error: Any = json.loads(error_body)
        except json.JSONDecodeError:
            parsed_error = None
        # A non-JSON error body (for example a gateway HTML page) is never copied into the message.
        message = _provider_error_payload(
            parsed_error, str(exc.reason or "Provider request failed"), secret
        )
        raise ProviderError(
            f"Provider returned HTTP {exc.code}: {message}",
            status=exc.code,
            retryable=_retryable_status(exc.code),
        ) from None
    except TimeoutError:
        raise ProviderError("Provider request timed out", retryable=True) from None
    except URLError as exc:
        raise ProviderError(
            f"Cannot reach provider API: {transport_failure_reason(exc.reason)}",
            retryable=True,
        ) from None
    except TRANSPORT_FAILURES as exc:
        raise ProviderError(
            f"Provider connection failed: {transport_failure_reason(exc)}",
            retryable=True,
        ) from None
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise ProviderError("Provider returned a response that is not valid UTF-8") from None
    except json.JSONDecodeError:
        raise ProviderError("Provider returned invalid JSON") from None
    if not isinstance(parsed, dict):
        raise ProviderError("Provider returned a non-object response")
    return parsed


def _request_with_retry(
    requester: ProviderRequest,
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    config: AgentModelConfig,
) -> tuple[Mapping[str, Any], int]:
    """Call the provider; retry rate limits, 5xx, timeouts, and connection failures."""

    attempts = max(1, int(config.max_attempts))
    attempt = 0
    while True:
        attempt += 1
        try:
            return requester(url, payload, headers, config.timeout), attempt - 1
        except ProviderError as exc:
            exc.retry_count = attempt - 1
            if not exc.retryable or attempt >= attempts:
                raise
            _sleep(retry_delay_seconds(attempt, config.retry_backoff_seconds))


def _required_key(config: AgentModelConfig, default_env: str) -> tuple[str, str]:
    env_name = config.api_key_env or default_env
    key = os.getenv(env_name)
    if not key:
        raise ProviderError(f"Required environment variable {env_name} is not set")
    return env_name, key


def _usage_numbers(payload: Any) -> dict[str, int | float]:
    if not isinstance(payload, dict):
        return {}
    result: dict[str, int | float] = {}
    for key, value in payload.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[str(key)] = value
        elif isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, (int, float)) and not isinstance(nested_value, bool):
                    result[f"{key}.{nested_key}"] = nested_value
    return result


def _safe_diagnostic_value(value: Any, secret: str) -> str:
    """Return one bounded provider metadata value for an error message."""

    if not isinstance(value, str):
        return "unknown"
    redacted = str(redact_secrets(value.strip(), (secret,)))
    safe = "".join(
        character if character.isalnum() or character in "._:-" else "_" for character in redacted
    )
    return safe[:80] or "unknown"


def _reported_model(response: Mapping[str, Any], secret: str) -> str | None:
    """Return the provider-reported model id, when the response names one."""

    value = response.get("model")
    if not isinstance(value, str) or not value.strip():
        return None
    return _safe_diagnostic_value(value, secret)


class OpenAIResponsesProvider:
    """OpenAI Responses API adapter."""

    DEFAULT_MODEL = "gpt-5.6-luna"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    SEED_PARAMETER_SUPPORTED = False

    def __init__(
        self,
        config: AgentModelConfig | None = None,
        *,
        requester: ProviderRequest | None = None,
    ) -> None:
        self.config = config or AgentModelConfig(provider="openai", model=self.DEFAULT_MODEL)
        self._requester = requester or _post_json

    def generate(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        instructions: str | None = None,
    ) -> Generation:
        _env_name, api_key = _required_key(self.config, "OPENAI_API_KEY")
        payload: dict[str, Any] = {
            "model": self.config.model,
            "input": [dict(message) for message in messages],
            "max_output_tokens": self.config.max_output_tokens,
            "store": False,
        }
        if instructions:
            payload["instructions"] = instructions
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        url = f"{(self.config.base_url or self.DEFAULT_BASE_URL).rstrip('/')}/responses"
        started = time.perf_counter()
        response, retry_count = _request_with_retry(
            self._requester,
            url,
            payload,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            self.config,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        text = response.get("output_text")
        if not isinstance(text, str) or not text.strip():
            fragments: list[str] = []
            output = response.get("output")
            if isinstance(output, list):
                for item in output:
                    if not isinstance(item, dict):
                        continue
                    content = item.get("content")
                    if not isinstance(content, list):
                        continue
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            fragments.append(part["text"])
            text = "".join(fragments)
        if not isinstance(text, str) or not text.strip():
            incomplete_details = response.get("incomplete_details")
            incomplete_reason = (
                incomplete_details.get("reason") if isinstance(incomplete_details, dict) else None
            )
            status = _safe_diagnostic_value(response.get("status"), api_key)
            reason = _safe_diagnostic_value(incomplete_reason, api_key)
            raise ProviderError(
                "OpenAI response did not contain output text "
                f"(status={status}, incomplete_reason={reason})",
                failure_diagnostics={"status": status, "incomplete_reason": reason},
                retry_count=retry_count,
            )
        return Generation(
            text=text.strip(),
            provider="openai",
            model=self.config.model,
            latency_ms=elapsed_ms,
            usage=_usage_numbers(response.get("usage")),
            request_id=str(response["id"]) if response.get("id") is not None else None,
            model_reported=_reported_model(response, api_key),
            retry_count=retry_count,
        )


class QwenCloudProvider:
    """Qwen Cloud OpenAI-compatible Chat Completions adapter."""

    DEFAULT_MODEL = "qwen3.7-plus"
    DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    TOKEN_PLAN_BASE_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    SEED_PARAMETER_SUPPORTED = True

    def __init__(
        self,
        config: AgentModelConfig | None = None,
        *,
        requester: ProviderRequest | None = None,
    ) -> None:
        self.config = config or AgentModelConfig(provider="qwen", model=self.DEFAULT_MODEL)
        self._requester = requester or _post_json

    def generate(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        instructions: str | None = None,
    ) -> Generation:
        _env_name, api_key = _required_key(self.config, "QWEN_API_KEY")
        chat_messages: list[dict[str, str]] = []
        if instructions:
            chat_messages.append({"role": "system", "content": instructions})
        chat_messages.extend(dict(message) for message in messages)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": chat_messages,
            "max_tokens": self.config.max_output_tokens,
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.seed is not None:
            if not 0 <= self.config.seed <= 2**31 - 1:
                raise ProviderError("Qwen seed must be between 0 and 2^31-1")
            payload["seed"] = self.config.seed
        configured_base_url = self.config.base_url or os.getenv("QWEN_BASE_URL")
        if configured_base_url:
            base_url = configured_base_url
        elif api_key.startswith("sk-sp-"):
            base_url = self.TOKEN_PLAN_BASE_URL
        else:
            base_url = self.DEFAULT_BASE_URL
        url = f"{base_url.rstrip('/')}/chat/completions"
        started = time.perf_counter()
        response, retry_count = _request_with_retry(
            self._requester,
            url,
            payload,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            self.config,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        choices = response.get("choices")
        text: Any = None
        finish_reason: Any = None
        reasoning_content: Any = None
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish_reason = choices[0].get("finish_reason")
            message = choices[0].get("message")
            if isinstance(message, dict):
                text = message.get("content")
                reasoning_content = message.get("reasoning_content")
        if not isinstance(text, str) or not text.strip():
            # Thinking-mode models can spend the whole output budget on reasoning and return
            # an empty content field; record the safe metadata that explains it.
            usage = _usage_numbers(response.get("usage"))
            diagnostics: dict[str, Any] = {
                "finish_reason": _safe_diagnostic_value(finish_reason, api_key),
                "has_reasoning_content": isinstance(reasoning_content, str)
                and bool(reasoning_content.strip()),
                "reasoning_tokens": usage.get("completion_tokens_details.reasoning_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            }
            raise ProviderError(
                "Qwen response did not contain message content ("
                f"finish_reason={diagnostics['finish_reason']}, "
                f"has_reasoning_content={str(diagnostics['has_reasoning_content']).lower()}, "
                f"reasoning_tokens={_unknown_if_none(diagnostics['reasoning_tokens'])}, "
                f"completion_tokens={_unknown_if_none(diagnostics['completion_tokens'])})",
                failure_diagnostics=diagnostics,
                retry_count=retry_count,
            )
        return Generation(
            text=text.strip(),
            provider="qwen",
            model=self.config.model,
            latency_ms=elapsed_ms,
            usage=_usage_numbers(response.get("usage")),
            request_id=str(response["id"]) if response.get("id") is not None else None,
            model_reported=_reported_model(response, api_key),
            retry_count=retry_count,
        )


def _unknown_if_none(value: Any) -> Any:
    return "unknown" if value is None else value


def provider_for(
    name: str,
    *,
    model: str | None = None,
    api_key_env: str | None = None,
    base_url: str | None = None,
    max_output_tokens: int = 500,
    temperature: float | None = None,
    seed: int | None = None,
    timeout: float = 60.0,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    requester: ProviderRequest | None = None,
) -> TextProvider:
    normalized = name.strip().lower()
    if normalized in {"openai", "openai_responses", "responses"}:
        config = AgentModelConfig(
            provider="openai",
            model=model or OpenAIResponsesProvider.DEFAULT_MODEL,
            api_key_env=api_key_env,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            seed=seed,
            timeout=timeout,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        return OpenAIResponsesProvider(config, requester=requester)
    if normalized in {"qwen", "qwen_cloud", "dashscope"}:
        config = AgentModelConfig(
            provider="qwen",
            model=model or QwenCloudProvider.DEFAULT_MODEL,
            api_key_env=api_key_env,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            seed=seed,
            timeout=timeout,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        return QwenCloudProvider(config, requester=requester)
    raise ValueError(f"Unsupported provider: {name}")
