"""Standard-library client for the negotiation trainer public API."""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4


JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None
Transport = Callable[[str, str, JsonValue, Mapping[str, str], float], JsonValue]

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0

# Tests replace this hook to avoid real delays.
_sleep = time.sleep

# Every failure below the HTTP layer: refused or reset connections, socket timeouts,
# TLS errors, and truncated or malformed HTTP exchanges.
TRANSPORT_FAILURES = (TimeoutError, ConnectionError, http.client.HTTPException, OSError)

_ERROR_BODY_TEXT_LIMIT = 500


_SECRET_KEYS = {
    "api_key",
    "authorization",
    "credential",
    "credentials",
    "participant_credentials",
    "participant_token",
    "participant_tokens",
    "access_token",
    "refresh_token",
    "secret",
    "token",
    "token_hash",
}


def _is_secret_key(key: object) -> bool:
    normalized = str(key).casefold().replace("-", "_")
    return (
        normalized in _SECRET_KEYS
        or normalized.endswith("_api_key")
        or normalized.endswith("_credential")
        or normalized.endswith("_credentials")
        or normalized.endswith("_secret")
        or normalized.endswith("_token")
        or normalized.endswith("_token_hash")
    )


def redact_secrets(value: Any, extra_secrets: tuple[str, ...] = ()) -> Any:
    """Return a JSON-compatible copy with credential-like fields removed."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(key):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_secrets(item, extra_secrets)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item, extra_secrets) for item in value]
    if isinstance(value, str):
        result = value
        for secret in extra_secrets:
            if secret:
                result = result.replace(secret, "[REDACTED]")
        return result
    return value


@dataclass(slots=True)
class ApiError(RuntimeError):
    """A sanitized backend error."""

    message: str
    status: int | None = None
    code: str | None = None
    error: str | None = None
    details: Any = None
    retryable: bool = False
    retry_count: int = 0

    def __str__(self) -> str:
        prefix = f"HTTP {self.status}: " if self.status is not None else ""
        identifiers = [value for value in (self.error, self.code) if value]
        suffix = f" [{' / '.join(dict.fromkeys(identifiers))}]" if identifiers else ""
        return f"{prefix}{self.message}{suffix}"


def new_idempotency_key(prefix: str = "cmd") -> str:
    return f"{prefix}_{uuid4().hex}"


def retry_delay_seconds(attempt: int, base_seconds: float) -> float:
    """Return the backoff delay after failed attempt number ``attempt`` (1s, 2s, 4s, ...)."""

    return base_seconds * (2 ** max(attempt - 1, 0))


def transport_failure_reason(reason: object) -> str:
    """Describe a transport failure without response bodies, URLs, or credentials."""

    if isinstance(reason, BaseException):
        text = f"{type(reason).__name__}: {reason}"
    else:
        text = str(reason)
    text = " ".join(text.split())
    return text[:200] or "unknown"


def http_error_body(exc: HTTPError) -> bytes:
    """Read an HTTP error body; a missing body or a transport failure yields no bytes."""

    try:
        raw = exc.read()
    except TRANSPORT_FAILURES:
        return b""
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return raw or b""


def _decode_error_body(raw: bytes) -> JsonValue:
    """Decode an HTTP error body; a non-JSON body is bounded and never fatal."""

    if not raw:
        return {}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text[:_ERROR_BODY_TEXT_LIMIT]}


def _decode_response(raw: bytes) -> JsonValue:
    if not raw:
        return {}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ApiError("Negotiation API returned a response that is not valid UTF-8") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ApiError("Negotiation API returned a response that is not valid JSON") from None


def _error_fields(payload: Any, fallback: str) -> tuple[str, str | None, str | None]:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict):
            message = str(detail.get("message") or detail.get("detail") or fallback)
            code = detail.get("code")
            error = detail.get("error") or payload.get("error")
            return (
                message,
                str(code) if code is not None else None,
                str(error) if error is not None and not isinstance(error, dict) else None,
            )
        message = str(payload.get("message") or detail or payload.get("error") or fallback)
        code = payload.get("code")
        error = payload.get("error")
        return (
            message,
            str(code) if code is not None else None,
            str(error) if error is not None and not isinstance(error, dict) else None,
        )
    return fallback, None, None


def _stdlib_transport(
    method: str,
    url: str,
    payload: JsonValue,
    headers: Mapping[str, str],
    timeout: float,
) -> JsonValue:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        parsed = _decode_error_body(http_error_body(exc))
        message, code, error = _error_fields(parsed, exc.reason or "API request failed")
        raise ApiError(
            message=message,
            status=exc.code,
            code=code,
            error=error,
            details=parsed,
        ) from None
    except TimeoutError:
        raise ApiError(message="Negotiation API request timed out", retryable=True) from None
    except URLError as exc:
        raise ApiError(
            message=f"Cannot reach negotiation API: {transport_failure_reason(exc.reason)}",
            retryable=True,
        ) from None
    except TRANSPORT_FAILURES as exc:
        raise ApiError(
            message=f"Negotiation API connection failed: {transport_failure_reason(exc)}",
            retryable=True,
        ) from None
    return _decode_response(raw)


def _retry_with_same_key(exc: ApiError) -> bool:
    """Transport failures and a pending NPC render are safe to retry with the same key."""

    return exc.retryable or "npc_render_pending" in {exc.error, exc.code}


class NegotiationApiClient:
    """Role-neutral client for humans, external agents, and benchmark runners."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        participant_token: str | None = None,
        timeout: float = 30.0,
        transport: Transport | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("NEGOTIATION_API_URL") or "http://127.0.0.1:8170"
        ).rstrip("/")
        self.participant_token = participant_token
        self.timeout = timeout
        self._transport = transport or _stdlib_transport
        self.max_attempts = max(1, int(max_attempts))
        self.retry_backoff_seconds = retry_backoff_seconds
        # Retries used by the most recent request; the orchestrator records it as telemetry.
        self.last_retry_count = 0

    def with_participant_token(self, token: str | None) -> "NegotiationApiClient":
        return NegotiationApiClient(
            self.base_url,
            participant_token=token,
            timeout=self.timeout,
            transport=self._transport,
            max_attempts=self.max_attempts,
            retry_backoff_seconds=self.retry_backoff_seconds,
        )

    def _redact_error(self, exc: ApiError) -> None:
        secrets = (self.participant_token or "",)
        exc.details = redact_secrets(exc.details, secrets)
        exc.message = str(redact_secrets(exc.message, secrets))
        exc.code = str(redact_secrets(exc.code, secrets)) if exc.code else None
        exc.error = str(redact_secrets(exc.error, secrets)) if exc.error else None

    def _request(
        self,
        method: str,
        path: str,
        payload: JsonValue = None,
        *,
        query: Mapping[str, str | int | float | bool | None] | None = None,
    ) -> JsonValue:
        url = f"{self.base_url}{path}"
        if query:
            filtered = {key: value for key, value in query.items() if value is not None}
            if filtered:
                url = f"{url}?{urlencode(filtered)}"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.participant_token:
            headers["Authorization"] = f"Bearer {self.participant_token}"
        # Every POST carries an idempotency key chosen before the first attempt, so a retry
        # never duplicates a committed command; an ambiguous submit returns the stored result.
        attempt = 0
        while True:
            attempt += 1
            self.last_retry_count = attempt - 1
            try:
                return self._transport(method, url, payload, headers, self.timeout)
            except ApiError as exc:
                self._redact_error(exc)
                exc.retry_count = attempt - 1
                if not _retry_with_same_key(exc) or attempt >= self.max_attempts:
                    raise
                _sleep(retry_delay_seconds(attempt, self.retry_backoff_seconds))

    def list_scenarios(self, *, language: str | None = None) -> JsonValue:
        return self._request("GET", "/api/v1/scenarios", query={"language": language})

    def create_session(
        self,
        *,
        scenario_id: str,
        scenario_version: int = 1,
        language: str,
        participants: list[Mapping[str, Any]],
        difficulty: str = "normal",
        hints_enabled: bool = False,
        run_mode: str = "training",
        idempotency_key: str | None = None,
        benchmark_run_id: str | None = None,
        trial_id: str | None = None,
        benchmark_expected_trials: int | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "idempotency_key": idempotency_key or new_idempotency_key("create"),
            "scenario_id": scenario_id,
            "scenario_version": scenario_version,
            "language": language,
            "participants": [dict(participant) for participant in participants],
            "difficulty": difficulty,
            "hints_enabled": hints_enabled,
            "run_mode": run_mode,
        }
        if benchmark_run_id is not None:
            payload["benchmark_run_id"] = benchmark_run_id
        if trial_id is not None:
            payload["trial_id"] = trial_id
        if benchmark_expected_trials is not None:
            payload["benchmark_expected_trials"] = benchmark_expected_trials
        if seed is not None:
            payload["seed"] = seed
        result = self._request("POST", "/api/v1/sessions", payload)
        if not isinstance(result, dict):
            raise ApiError("Session creation returned a non-object response")
        return result

    def get_session(self, session_id: str) -> dict[str, Any]:
        result = self._request("GET", f"/api/v1/sessions/{quote(session_id, safe='')}")
        if not isinstance(result, dict):
            raise ApiError("Session endpoint returned a non-object response")
        return result

    def submit_message(
        self,
        session_id: str,
        message: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "message": message,
            "idempotency_key": idempotency_key or new_idempotency_key(),
            "expected_revision": expected_revision,
        }
        result = self._request(
            "POST",
            f"/api/v1/sessions/{quote(session_id, safe='')}/messages",
            payload,
        )
        if not isinstance(result, dict):
            raise ApiError("Message endpoint returned a non-object response")
        return result

    def history(self, session_id: str) -> JsonValue:
        return self._request("GET", f"/api/v1/sessions/{quote(session_id, safe='')}/history")

    def review(self, session_id: str) -> JsonValue:
        return self._request("GET", f"/api/v1/sessions/{quote(session_id, safe='')}/review")

    def stats(self) -> JsonValue:
        return self._request("GET", "/api/v1/stats")

    def close_session(
        self,
        session_id: str,
        *,
        expected_revision: int,
        reason: str,
        admin_token: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        client = self.with_participant_token(admin_token)
        result = client._request(
            "POST",
            f"/api/v1/sessions/{quote(session_id, safe='')}/close",
            {
                "idempotency_key": idempotency_key or new_idempotency_key("close"),
                "expected_revision": expected_revision,
                "reason": reason,
            },
        )
        if not isinstance(result, dict):
            raise ApiError("Administrative close returned a non-object response")
        return result

    def export_session(self, session_id: str, destination: str | os.PathLike[str]) -> Path:
        """Export actor-safe history and the final review without credentials."""

        history = self.history(session_id)
        try:
            review: JsonValue = self.review(session_id)
        except ApiError as exc:
            review = {
                "unavailable": True,
                "error": str(exc),
                "status": exc.status,
                "code": exc.code,
                "backend_error": exc.error,
            }
        document = redact_secrets(
            {
                "session_id": session_id,
                "history": history,
                "review": review,
            },
            (self.participant_token or "",),
        )
        path = Path(destination).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        return path


def response_revision(response: Mapping[str, Any]) -> int:
    for key in ("revision", "session_revision", "current_revision"):
        value = response.get(key)
        if isinstance(value, int):
            return value
    raise ApiError("Backend response does not contain a session revision")


def response_status(response: Mapping[str, Any]) -> str:
    value = response.get("status") or response.get("session_status")
    return str(value) if value is not None else "active"
