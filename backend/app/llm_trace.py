"""Bounded administrator diagnostics. Never part of the Player API or replay state."""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from collections import OrderedDict
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from clients.providers import provider_request_observer

from .dialogue import redact_untrusted_credentials

trace_session: ContextVar[str | None] = ContextVar("llm_trace_session", default=None)
_DETAIL_FIELDS = {"instructions", "messages", "response", "parameters", "requests"}
_CREDENTIAL_FIELDS = {
    "authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key",
    "api-key", "api_key", "access_token", "refresh_token", "token", "password", "secret",
}


def _provider_secret(config):
    name = config.api_key_env or {"qwen": "QWEN_API_KEY", "openai": "OPENAI_API_KEY"}.get(config.provider)
    return os.getenv(name, "") if name else ""


class LlmTraceRecorder:
    def __init__(self, *, enabled=False, secrets=(), capacity=200, capacity_bytes=64 * 1024 * 1024):
        self.enabled = enabled
        self.secrets = tuple(secrets)
        self.capacity = capacity
        self.capacity_bytes = capacity_bytes
        self._records = OrderedDict()
        self._sizes = {}
        self._total_bytes = 0
        self._lock = Lock()

    def _clean(self, text, extra_secret=""):
        return redact_untrusted_credentials(str(text), *self.secrets, extra_secret)

    def _clean_data(self, value, extra_secret=""):
        if isinstance(value, dict):
            return {self._clean(key, extra_secret):
                    "[REDACTED]" if str(key).lower() in _CREDENTIAL_FIELDS else self._clean_data(item, extra_secret)
                    for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._clean_data(item, extra_secret) for item in value]
        if isinstance(value, str):
            return self._clean(value, extra_secret)
        return value

    def _put(self, record):
        """Store a redacted record while holding the lock. Evict complete records only."""
        trace_id = record["trace_id"]
        size = len(json.dumps(record, ensure_ascii=False).encode("utf-8"))
        self._total_bytes += size - self._sizes.get(trace_id, 0)
        self._sizes[trace_id] = size
        self._records[trace_id] = record
        while len(self._records) > self.capacity or self._total_bytes > self.capacity_bytes:
            oldest, _ = self._records.popitem(last=False)
            self._total_bytes -= self._sizes.pop(oldest)

    def begin(self, provider, task, messages, instructions):
        session_id = trace_session.get()
        if not self.enabled or session_id is None:
            return None
        config = provider.config
        secret = _provider_secret(config)
        if (instructions or "").startswith("Write the first NPC message"):
            task = "npc_opening"
        elif task == "npc_dialogue" and (instructions or "").startswith("Check "):
            task = "npc_grounding"
        trace_id = "llm_" + uuid.uuid4().hex
        record = {
            "trace_id": trace_id, "session_id": session_id, "task": task,
            "provider": self._clean(config.provider, secret),
            "model": self._clean(config.model, secret),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running", "duration_ms": None, "error_type": None,
            "http_status": None, "retry_count": 0, "usage": {},
            "request_truncated": False, "response_truncated": False,
            "instructions": self._clean(instructions or "", secret),
            "messages": self._clean_data([dict(item) for item in messages], secret),
            "response": None, "requests": [],
            "parameters": {"max_output_tokens": config.max_output_tokens,
                "temperature": config.temperature, "enable_thinking": config.enable_thinking,
                "timeout_seconds": config.timeout,
                "max_attempts": config.max_attempts, "seed": config.seed,
                "retry_backoff_seconds": config.retry_backoff_seconds},
        }
        with self._lock:
            self._put(record)
        return trace_id

    def capture_request(self, trace_id, url, payload, headers, timeout, attempt):
        if trace_id is None:
            return
        secret = next((value.removeprefix("Bearer ") for key, value in headers.items()
                       if key.lower() == "authorization"), "")
        parts = urlsplit(url)
        netloc = "[REDACTED]@" + parts.netloc.rsplit("@", 1)[1] if "@" in parts.netloc else parts.netloc
        query = parts.query
        if any(key.lower() in _CREDENTIAL_FIELDS for key, _ in parse_qsl(query)):
            query = urlencode([(key, "[REDACTED]" if key.lower() in _CREDENTIAL_FIELDS else value)
                               for key, value in parse_qsl(query, keep_blank_values=True)])
        request = {"attempt": attempt, "method": "POST",
                   "url": self._clean(urlunsplit(parts._replace(netloc=netloc, query=query)), secret),
                   "headers": self._clean_data(dict(headers), secret),
                   "body": self._clean_data(dict(payload), secret), "timeout_seconds": timeout}
        with self._lock:
            record = self._records.get(trace_id)
            if record is not None:
                record["requests"].append(request)
                self._put(record)

    def finish(self, trace_id, *, duration_ms, generation=None, error=None, extra_secret=""):
        if trace_id is None:
            return
        response = None
        usage = {}
        if generation is not None:
            response = self._clean(generation.text, extra_secret)
            usage = {self._clean(key, extra_secret): value
                     for key, value in generation.usage.items()
                     if type(value) in (int, float) and math.isfinite(value) and value >= 0}
        # Exception messages can contain provider bodies and credentials. Store only type/status.
        status = getattr(error, "status", None)
        retries = getattr(error if error else generation, "retry_count", 0)
        with self._lock:
            record = self._records.get(trace_id)
            if record is not None:
                record.update(status="error" if error else "completed", duration_ms=round(duration_ms, 2),
                    error_type=type(error).__name__ if error else None,
                    http_status=status if type(status) is int else None,
                    retry_count=retries if type(retries) is int and retries >= 0 else 0,
                    response=response, response_truncated=False, usage=usage)
                self._put(record)

    def list(self, *, session_id=None, limit=100):
        with self._lock:
            items = [{key: deepcopy(value) for key, value in item.items() if key not in _DETAIL_FIELDS}
                     for item in reversed(self._records.values())
                     if session_id is None or item["session_id"] == session_id][:limit]
        return {"enabled": self.enabled, "capacity": self.capacity,
                "capacity_bytes": self.capacity_bytes, "items": items}

    def get(self, trace_id):
        with self._lock:
            return deepcopy(self._records.get(trace_id))


class TracedProvider:
    def __init__(self, provider, recorder, task):
        self._provider = provider
        self._recorder = recorder
        self._task = task
        self.config = provider.config
        self.SEED_PARAMETER_SUPPORTED = getattr(provider, "SEED_PARAMETER_SUPPORTED", False)

    def generate(self, messages, *, instructions=None):
        trace_id = self._recorder.begin(self._provider, self._task, messages, instructions)
        started = time.monotonic()
        secret = _provider_secret(self.config)
        observer_token = provider_request_observer.set(
            (lambda *args: self._recorder.capture_request(trace_id, *args)) if trace_id else None
        )
        try:
            result = self._provider.generate(messages, instructions=instructions)
        except Exception as error:
            self._recorder.finish(trace_id, duration_ms=(time.monotonic() - started) * 1000, error=error)
            raise
        finally:
            provider_request_observer.reset(observer_token)
        self._recorder.finish(trace_id, duration_ms=(time.monotonic() - started) * 1000,
                              generation=result, extra_secret=secret)
        return result
