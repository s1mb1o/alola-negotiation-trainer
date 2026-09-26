from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.dialogue import LlmNpcDialogueRenderer
from backend.app.llm_trace import LlmTraceRecorder, TracedProvider, trace_session
from backend.app.main import create_app
from clients.providers import AgentModelConfig, Generation, ProviderError

from .conftest import bearer, create_payload
from .openapi_support import ResponseContractCheck
from .test_npc_dialogue import FailingProvider


def record_fixture(recorder, session_id="sess_fixture"):
    token = trace_session.set(session_id)
    try:
        trace_id = recorder.begin(SimpleNamespace(config=AgentModelConfig(provider="fixture", model="fixture")),
                                  "npc_dialogue", [{"role": "user", "content": "Учебный запрос"}], "Reply in Russian.")
    finally:
        trace_session.reset(token)
    return trace_id


def test_bounded_records_running_and_completion():
    recorder = LlmTraceRecorder(enabled=True, capacity=2)
    first = record_fixture(recorder)
    assert recorder.get(first)["status"] == "running"
    second = record_fixture(recorder, "sess_second")
    third = record_fixture(recorder)
    assert recorder.get(first) is None
    assert len(recorder.list()["items"]) == 2
    assert recorder.list(session_id="sess_second")["items"][0]["trace_id"] == second
    assert "instructions" not in recorder.list()["items"][0]
    recorder.finish(third, duration_ms=125, generation=Generation(text='{"safe":false}', provider="fixture", model="fixture", latency_ms=125, usage={"input_tokens": 50}))
    assert recorder.get(third)["status"] == "completed"
    assert recorder.get(third)["response"] == '{"safe":false}'
    assert recorder.get(third)["usage"] == {"input_tokens": 50}
    assert not LlmTraceRecorder().list()["enabled"]
    assert record_fixture(LlmTraceRecorder()) is None


def test_redaction_preserves_full_content_and_covers_response_and_errors(monkeypatch):
    secret = "fixture-provider-secret-123456789"
    monkeypatch.setenv("TEST_TRACE_KEY", secret)
    recorder = LlmTraceRecorder(enabled=True, secrets=("private-admin",))
    class Provider:
        config = AgentModelConfig(provider="fixture", model="fixture", api_key_env="TEST_TRACE_KEY")
        def generate(self, messages, *, instructions):
            return Generation(text="private-admin " + secret + " nt_123456789101112", provider="fixture", model="fixture", latency_ms=1)
    wrapped = TracedProvider(Provider(), recorder, "npc_dialogue")
    token = trace_session.set("sess_redact")
    try:
        result = wrapped.generate([{"role": "user", "content": "x" * 63995 + secret}], instructions="private-admin " + secret)
        # Diagnostics must not rewrite provider output or alter the negotiation pipeline.
        assert secret in result.text
    finally:
        trace_session.reset(token)
    trace = recorder.get(recorder.list()["items"][0]["trace_id"])
    serialized = json.dumps(trace)
    assert all(value not in serialized for value in (secret, "private-admin", "nt_123456789101112"))
    assert trace["messages"][0]["content"] == "x" * 63995 + "[REDACTED_CREDENTIAL]"
    assert not trace["request_truncated"]
    recorder.finish(trace["trace_id"], duration_ms=4,
        error=ProviderError(secret, status=429, retry_count=2))
    failed = recorder.get(trace["trace_id"])
    assert failed["error_type"] == "ProviderError" and failed["http_status"] == 429
    assert failed["retry_count"] == 2 and secret not in json.dumps(failed)


def test_provider_error_is_rethrown_without_logging_message():
    recorder = LlmTraceRecorder(enabled=True)
    wrapped = TracedProvider(FailingProvider(), recorder, "npc_dialogue")
    token = trace_session.set("sess_error")
    try:
        with pytest.raises(RuntimeError):
            wrapped.generate([], instructions="Check a proposed NON-BINDING reply.")
    finally:
        trace_session.reset(token)
    item = recorder.list()["items"][0]
    assert item["task"] == "npc_grounding"
    assert item["status"] == "error" and item["error_type"] == "RuntimeError"
    assert "NEVEREXPOSETHIS" not in json.dumps(recorder.get(item["trace_id"]))


def test_opening_instruction_has_its_own_trace_task():
    recorder = LlmTraceRecorder(enabled=True)
    token = trace_session.set("sess_opening")
    try:
        trace_id = recorder.begin(
            SimpleNamespace(config=AgentModelConfig(provider="fixture", model="fixture")),
            "npc_dialogue",
            [],
            "Write the first NPC message in Russian.",
        )
    finally:
        trace_session.reset(token)

    assert recorder.get(trace_id)["task"] == "npc_opening"


def test_admin_only_no_cache_typed_contracts_and_static_page(client):
    recorder = client.app.state.llm_traces
    recorder.enabled = True
    trace_id = record_fixture(recorder)
    session = client.post("/api/v1/sessions", json=create_payload("trace-auth")).json()
    base = "/api/v1/admin/llm-traces"
    for path in (base, base + "/" + trace_id):
        for credential in (None, session["participant_token"], "wrong-admin"):
            response = client.get(path, headers=bearer(credential) if credential else {})
            assert response.status_code == 401
            assert "Учебный запрос" not in response.text
        response = client.get(path, headers=bearer("test-admin"))
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
    assert client.get(base + "/missing", headers=bearer("test-admin")).status_code == 404
    assert client.get(base + "?limit=201", headers=bearer("test-admin")).status_code == 422
    assert client.get(base + "?session_id=sess_missing", headers=bearer("test-admin")).json()["items"] == []
    page = client.get("/llm-debug")
    assert page.status_code == 200
    assert "test-admin" not in page.text and "Учебный запрос" not in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    script = client.get("/llm-debug/llm-debug.js")
    assert script.status_code == 200
    assert "innerHTML" not in script.text and "localStorage" not in script.text
    assert client.get("/llm-debug/unknown").status_code == 404


def test_disabled_admin_keeps_recording_but_denies_nonlocal_access(settings):
    with TestClient(create_app(replace(settings, llm_trace_enabled=True, admin_token=""))) as client:
        assert client.app.state.llm_traces.enabled
        assert client.get("/api/v1/admin/llm-traces").status_code == 503


@pytest.mark.parametrize("base_url,host", [
    ("http://127.0.0.1:8172", "127.0.0.1"),
    ("http://localhost:8172", "127.0.0.1"),
    ("http://localhost:8172", "::1"),
])
def test_local_window_needs_no_credential_and_preserves_other_admin_gates(settings, base_url, host):
    with TestClient(create_app(replace(settings, llm_trace_enabled=True, admin_token="")),
                    base_url=base_url, client=(host, 50000)) as client:
        client.event_hooks["response"].append(ResponseContractCheck(client.app))
        trace_id = record_fixture(client.app.state.llm_traces)
        for path in ("/api/v1/admin/llm-traces", "/api/v1/admin/llm-traces/" + trace_id):
            for headers in ({}, {"Origin": base_url}):
                response = client.get(path, headers=headers)
                assert response.status_code == 200, response.text
                assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/v1/admin/sessions").status_code == 503
        assert client.get("/llm-debug").status_code == 200


@pytest.mark.parametrize("base_url,host,headers", [
    ("http://127.0.0.1:8172", "192.0.2.10", {}),
    ("http://foreign.example:8172", "127.0.0.1", {}),
    ("http://127.0.0.1:8172", "127.0.0.1", {"Origin": "https://foreign.example"}),
    ("http://127.0.0.1:8172", "127.0.0.1", {"Origin": "http://127.0.0.1:9999"}),
    ("http://127.0.0.1:8172", "127.0.0.1", {"Origin": "null"}),
])
def test_local_exemption_requires_local_client_host_and_origin(settings, base_url, host, headers):
    with TestClient(create_app(replace(settings, llm_trace_enabled=True)),
                    base_url=base_url, client=(host, 50000)) as client:
        trace_id = record_fixture(client.app.state.llm_traces)
        for path in ("/api/v1/admin/llm-traces", "/api/v1/admin/llm-traces/" + trace_id):
            assert client.get(path, headers=headers).status_code == 401
            assert client.get(path, headers={**headers, **bearer("test-admin")}).status_code == 200


@pytest.mark.parametrize("benchmark", [False, True])
def test_http_context_records_training_calls_only_and_preserves_fallback(settings, benchmark):
    with TestClient(create_app(replace(settings, llm_trace_enabled=True),
            npc_dialogue_renderer=LlmNpcDialogueRenderer(FailingProvider()))) as client:
        client.event_hooks["response"].append(ResponseContractCheck(client.app))
        payload = create_payload("trace-session", hints_enabled=False)
        if benchmark:
            payload.update(run_mode="benchmark", benchmark_run_id="trace-test", trial_id="one", benchmark_expected_trials=1)
        created = client.post("/api/v1/sessions", json=payload, headers=bearer("test-admin"))
        assert created.status_code == 201, created.text
        session = created.json()
        token = session.get("participant_token")
        if token is None:
            token = next(item["token"] for item in session["participant_credentials"] if item["role"] == "buyer")
        response = client.post(f"/api/v1/sessions/{session['session_id']}/messages", headers=bearer(token),
            json={"message": "Как зовут вашу собаку?", "expected_revision": session["revision"], "idempotency_key": "dog"})
        assert response.status_code == 200, response.text
        assert "sk-NEVEREXPOSETHIS" not in response.text
        listing = client.get("/api/v1/admin/llm-traces", headers=bearer("test-admin")).json()
        if benchmark:
            assert listing["items"] == []
        else:
            assert listing["items"]
            assert all(item["session_id"] == session["session_id"] for item in listing["items"])
            for item in listing["items"]:
                detail = client.get("/api/v1/admin/llm-traces/" + item["trace_id"], headers=bearer("test-admin"))
                assert detail.status_code == 200
                assert detail.json()["error_type"] == "RuntimeError"
                assert "NEVEREXPOSETHIS" not in detail.text
        assert trace_session.get() is None


@pytest.mark.parametrize("kind", ["qwen", "openai"])
def test_full_transport_request_matches_sent_body_and_api_contract(client, monkeypatch, kind):
    from clients.providers import (
        OpenAIResponsesProvider,
        QwenCloudProvider,
        provider_request_observer,
    )
    secret = "default-provider-credential-1234"
    monkeypatch.setenv("QWEN_API_KEY" if kind == "qwen" else "OPENAI_API_KEY", secret)
    calls = []

    def requester(url, body, headers, timeout):
        calls.append((url, body, headers, timeout))
        return {"output_text": "Ответ", "choices": [{"message": {"content": "Ответ"}}]}

    config = AgentModelConfig(provider=kind, model="fixture", max_output_tokens=777, seed=42,
                              temperature=0.4, timeout=9, base_url="https://fixture.example/v1")
    adapter = QwenCloudProvider if kind == "qwen" else OpenAIResponsesProvider
    recorder = client.app.state.llm_traces
    recorder.enabled = True
    token = trace_session.set("sess_full_request")
    try:
        result = TracedProvider(adapter(config, requester=requester), recorder, "npc_dialogue").generate(
            [{"role": "user", "content": '{"context":"Гуффи","examples":["пример"]}'}],
            instructions="Reply in Russian.")
    finally:
        trace_session.reset(token)
    assert result.text == "Ответ" and provider_request_observer.get() is None
    trace_id = recorder.list()["items"][0]["trace_id"]
    response = client.get('/api/v1/admin/llm-traces/' + trace_id, headers=bearer("test-admin"))
    assert response.status_code == 200
    trace = response.json()
    request = trace["requests"][0]
    assert request["body"] == calls[0][1]
    assert request["url"] == calls[0][0] and request["timeout_seconds"] == 9
    assert request["headers"] == {"Authorization": "[REDACTED]", "Content-Type": "application/json"}
    assert request["method"] == "POST" and request["attempt"] == 1
    assert secret not in json.dumps(trace)
    assert "requests" not in recorder.list()["items"][0]
    if kind == "qwen":
        assert request["body"]["seed"] == 42
        assert request["body"]["messages"][0] == {"role": "system", "content": "Reply in Russian."}
    else:
        assert "seed" not in request["body"]
        assert request["body"]["store"] is False


def test_no_content_or_message_count_truncation(monkeypatch):
    from clients.providers import QwenCloudProvider
    monkeypatch.setenv("QWEN_API_KEY", "fixture-key")
    instructions = "A" * 17000 + "PROMPT_END"
    messages = [{"role": "user", "content": "Я" * 65000 + "MESSAGE_END", "name": "player"}]
    messages += [{"role": "user", "content": str(i)} for i in range(40)]
    response = "R" * 33000 + "RESPONSE_END"
    provider = QwenCloudProvider(requester=lambda *args: {"choices": [{"message": {"content": response}}]})
    recorder = LlmTraceRecorder(enabled=True)
    token = trace_session.set("sess_long")
    try:
        TracedProvider(provider, recorder, "npc_dialogue").generate(messages, instructions=instructions)
    finally:
        trace_session.reset(token)
    trace = recorder.get(recorder.list()["items"][0]["trace_id"])
    assert trace["instructions"] == instructions
    assert trace["messages"] == messages
    assert trace["requests"][0]["body"]["messages"] == [{"role": "system", "content": instructions}, *messages]
    assert trace["response"] == response
    assert not trace["request_truncated"] and not trace["response_truncated"]


def test_retry_attempts_and_failure_keep_complete_outgoing_requests(monkeypatch):
    from clients.providers import QwenCloudProvider, provider_request_observer
    monkeypatch.setenv("QWEN_API_KEY", "fixture-key")
    monkeypatch.setattr("clients.providers._sleep", lambda _: None)
    calls = []
    def requester(*args):
        calls.append(args)
        raise ProviderError("private provider body", status=429, retryable=True)
    recorder = LlmTraceRecorder(enabled=True)
    provider = QwenCloudProvider(AgentModelConfig(provider="qwen", model="fixture", max_attempts=2), requester=requester)
    token = trace_session.set("sess_retry")
    try:
        with pytest.raises(ProviderError):
            TracedProvider(provider, recorder, "npc_dialogue").generate([], instructions="Check the reply.")
    finally:
        trace_session.reset(token)
    trace = recorder.get(recorder.list()["items"][0]["trace_id"])
    assert [item["attempt"] for item in trace["requests"]] == [1, 2]
    assert all(item["body"] == calls[index][1] for index, item in enumerate(trace["requests"]))
    assert trace["status"] == "error" and trace["retry_count"] == 1
    assert trace["task"] == "npc_grounding"
    assert "private provider body" not in json.dumps(trace)
    assert provider_request_observer.get() is None


def test_memory_limit_evicts_complete_records_including_oversized_content():
    recorder = LlmTraceRecorder(enabled=True)
    first = record_fixture(recorder)
    size = recorder._total_bytes
    recorder.capacity_bytes = size + 10
    second = record_fixture(recorder)
    assert recorder.get(first) is None
    assert recorder.get(second)["messages"][0]["content"] == "Учебный запрос"
    recorder.finish(second, duration_ms=1, generation=Generation(text="Я" * size, provider="fixture", model="fixture", latency_ms=1))
    assert recorder.get(second) is None
    assert recorder._total_bytes == 0 and recorder._sizes == {}
    third = record_fixture(recorder)
    assert recorder.get(third) is not None


def test_transport_credentials_are_redacted_in_headers_url_and_nested_body():
    recorder = LlmTraceRecorder(enabled=True, secrets=("known-private",))
    trace_id = record_fixture(recorder)
    recorder.capture_request(trace_id, "https://alice:password@example.test/v1?token=private-query&mode=json",
        {"nested": {"api_key": "other-key", "quote": "known-private opaque-bearer"}},
        {"Authorization": "Bearer opaque-bearer", "X-API-Key": "other-key", "Cookie": "session=private-cookie"}, 5, 1)
    request = recorder.get(trace_id)["requests"][0]
    assert request["body"]["nested"]["quote"] == "[REDACTED_CREDENTIAL] [REDACTED_CREDENTIAL]"
    serialized = json.dumps(request)
    assert all(secret not in serialized for secret in ["alice", "password", "private-query", "known-private", "opaque-bearer", "other-key", "private-cookie"])
    assert "mode=json" in request["url"]


def test_concurrent_request_observers_do_not_mix_sessions(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from clients.providers import QwenCloudProvider, provider_request_observer
    monkeypatch.setenv("QWEN_API_KEY", "fixture-key")
    barrier = Barrier(2)
    def requester(*args):
        barrier.wait(timeout=5)
        return {"choices": [{"message": {"content": "Ответ"}}]}
    recorder = LlmTraceRecorder(enabled=True)
    provider = TracedProvider(QwenCloudProvider(requester=requester), recorder, "npc_dialogue")
    def run(session):
        token = trace_session.set(session)
        try:
            provider.generate([{"role": "user", "content": session}])
            assert provider_request_observer.get() is None
        finally:
            trace_session.reset(token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, ["sess_one", "sess_two"]))
    for summary in recorder.list()["items"]:
        request = recorder.get(summary["trace_id"])["requests"][0]
        assert request["body"]["messages"] == [{"role": "user", "content": summary["session_id"]}]


@pytest.mark.parametrize("enabled,session", [(False, "sess_disabled"), (True, None)])
def test_disabled_or_excluded_transport_has_no_observer(monkeypatch, enabled, session):
    from clients.providers import QwenCloudProvider, provider_request_observer
    monkeypatch.setenv("QWEN_API_KEY", "fixture-key")
    def requester(*args):
        assert provider_request_observer.get() is None
        return {"choices": [{"message": {"content": "Ответ"}}]}
    recorder = LlmTraceRecorder(enabled=enabled)
    token = trace_session.set(session)
    try:
        TracedProvider(QwenCloudProvider(requester=requester), recorder, "npc_dialogue").generate([])
    finally:
        trace_session.reset(token)
    assert recorder.list()["items"] == []
