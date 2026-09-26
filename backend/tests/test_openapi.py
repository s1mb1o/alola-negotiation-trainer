import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from openapi_spec_validator import OpenAPIV31SpecValidator

from backend.app.main import create_app

from .conftest import SCENARIO_ID, bearer, create_payload
from .openapi_support import ResponseContractCheck, schema_validator

EXPECTED_OPERATION_IDS = {
    "getHealth",
    "listScenarios",
    "getScenario",
    "getScenarioVersion",
    "createSession",
    "getSession",
    "getObservation",
    "submitMessage",
    "getMessages",
    "getEvents",
    "getHistory",
    "requestHint",
    "getReview",
    "requestCoaching",
    "listCheckpoints",
    "forkSession",
    "rewindSession",
    "requestPlayerAssist",
    "compareTraining",
    "closeSession",
    "listAdminSessions",
    "getAdminSession",
    "getStats",
    "listLlmTraces",
    "getLlmTrace",
}


class PlayerAssistFixtureProvider:
    config = SimpleNamespace(provider="fixture", model="fixture-player-assist")

    @staticmethod
    def generate(messages, *, instructions):
        assert messages and instructions
        return SimpleNamespace(
            text=json.dumps(
                {"message": "Какие условия для вас наиболее важны?"},
                ensure_ascii=False,
            )
        )


def operations(document):
    for path, methods in document["paths"].items():
        for method, operation in methods.items():
            yield path, method, operation


def registered_routes(app):
    for route in app.routes:
        # FastAPI supports both eager APIRoute entries and lazy included routers.
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "effective_route_contexts"):
            yield from route.effective_route_contexts()


def test_document_validity_route_coverage_and_stable_ids(settings):
    app = create_app(settings)
    document = app.openapi()
    assert document["openapi"] == "3.1.0"
    OpenAPIV31SpecValidator(document).validate()
    actual = {(path, method.upper()) for path, method, _ in operations(document)}
    expected = {
        (route.path, method)
        for route in registered_routes(app)
        if route.path.startswith("/api/v1/")
        for method in route.methods
    }
    assert actual == expected
    ids = [operation["operationId"] for _, _, operation in operations(document)]
    assert set(ids) == EXPECTED_OPERATION_IDS
    assert len(ids) == len(set(ids))
    for path, _, operation in operations(document):
        assert path.startswith("/api/v1/")
        assert operation["summary"] and operation["description"]
        for response in operation["responses"].values():
            schema = response["content"]["application/json"]["schema"]
            assert schema and ("$ref" in schema or "anyOf" in schema)


def test_bearer_security_and_conditional_benchmark_access(settings):
    document = create_app(settings).openapi()
    schemes = document["components"]["securitySchemes"]
    assert set(schemes) == {"ParticipantBearer", "AdministratorBearer"}
    assert all(item["type"] == "http" and item["scheme"] == "bearer" for item in schemes.values())
    for path, method, operation in operations(document):
        security = operation.get("security", [])
        if path == "/api/v1/sessions" and method == "post":
            assert security == [{"AdministratorBearer": []}, {}]
            assert "benchmark" in operation["description"].lower()
        elif path.startswith("/api/v1/admin/llm-traces"):
            assert security == [{"AdministratorBearer": []}, {}]
            assert "loopback" in operation["description"]
        elif path.startswith("/api/v1/admin/") or path.endswith("/close"):
            assert security == [{"AdministratorBearer": []}]
        elif path.startswith("/api/v1/sessions/"):
            assert security == [{"ParticipantBearer": []}]
        else:
            assert not security
        assert all(p["name"].lower() != "authorization" for p in operation.get("parameters", []))


def test_synthetic_examples_conform_to_schemas(settings):
    document = create_app(settings).openapi()
    request_examples = response_examples = 0
    for name, schema in document["components"]["schemas"].items():
        for example in schema.get("examples", []):
            schema_validator(document, {"$ref": f"#/components/schemas/{name}"}).validate(example)
            request_examples += 1
    for _, _, operation in operations(document):
        for response in operation["responses"].values():
            media = response["content"]["application/json"]
            if "example" in media:
                schema_validator(document, media["schema"]).validate(media["example"])
                response_examples += 1
    assert request_examples >= 5 and response_examples >= 10


def test_request_limits_optional_nullable_fields_and_replay(settings):
    schemas = create_app(settings).openapi()["components"]["schemas"]
    message = schemas["SubmitMessageRequest"]
    assert message["properties"]["message"]["maxLength"] == 10_000
    assert message["properties"]["expected_revision"]["minimum"] == 0
    assert schemas["CreateSessionRequest"]["properties"]["participants"]["maxItems"] == 2
    created = schemas["CreateSessionResponse"]
    assert "participant_token" not in created["required"]
    assert "participant_credentials" not in created["required"]
    assert "next_actor" in created["required"]
    assert {"type": "null"} in created["properties"]["next_actor"]["anyOf"]


def test_schema_generation_does_not_initialize_database_or_provider(settings, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Documentation generation must not initialize runtime services")

    monkeypatch.setattr("backend.app.main.Database.initialize", forbidden)
    monkeypatch.setattr("backend.app.main._configured_dialogue_renderer", forbidden)
    app = create_app(replace(settings, npc_provider="qwen", npc_api_key_env="MISSING_TEST_API_KEY"))
    assert app.openapi()["paths"]


def test_documentation_pages_and_alias_exclusion(client):
    document = client.get("/openapi.json")
    assert document.status_code == 200
    swagger = client.get("/docs")
    assert swagger.status_code == 200
    assert "/openapi.json" in swagger.text
    assert '"persistAuthorization": false' in swagger.text
    assert client.get("/redoc").status_code == 200
    assert "/sessions" not in document.json()["paths"]
    assert client.get("/health").json() == client.get("/api/v1/health").json()


def test_every_operation_returns_a_documented_success(client):
    checker = client.event_hooks["response"][0]
    for path in (
        "health",
        "scenarios",
        f"scenarios/{SCENARIO_ID}",
        f"scenarios/{SCENARIO_ID}/versions/1",
        "stats",
    ):
        assert client.get(f"/api/v1/{path}").status_code == 200
    payload = create_payload("openapi-training")
    payload["training"] = {"relationship": "successful_history"}
    created = client.post("/api/v1/sessions", json=payload).json()
    replay = client.post("/api/v1/sessions", json=payload).json()
    assert replay["credential_delivery"] == "initial_response_only"
    assert "participant_credentials" not in replay
    session_id = created["session_id"]
    headers = bearer(created["participant_token"])
    base = f"/api/v1/sessions/{session_id}"
    client.app.state.service.player_assist_provider = PlayerAssistFixtureProvider()
    for suffix in ("", "/observation", "/messages", "/events", "/history", "/checkpoints"):
        assert client.get(base + suffix, headers=headers).status_code == 200
    assert client.post(
        base + "/player-assist",
        headers=headers,
        json={"idempotency_key": "openapi-assist", "expected_revision": created["revision"]},
    ).status_code == 200
    progressed = client.post(
        base + "/messages",
        headers=headers,
        json={
            "message": "Здравствуйте.",
            "idempotency_key": "openapi-progress",
            "expected_revision": created["revision"],
        },
    ).json()
    assert client.post(
        base + "/rewind",
        headers=headers,
        json={"source_revision": 0, "idempotency_key": "openapi-rewind"},
    ).status_code == 201
    hinted = client.post(
        base + "/hints",
        headers=headers,
        json={"idempotency_key": "openapi-hint", "expected_revision": progressed["revision"]},
    ).json()
    terminal = client.post(
        base + "/messages",
        headers=headers,
        json={
            "message": "Прекращаю переговоры.",
            "idempotency_key": "openapi-stop",
            "expected_revision": hinted["revision"],
        },
    )
    assert terminal.status_code == 200
    assert client.get(base + "/review", headers=headers).status_code == 200
    assert client.post(base + "/coaching", headers=headers).json()["status"] == "unavailable"
    fork_payload = {"source_revision": 0, "idempotency_key": "openapi-fork"}
    child = client.post(base + "/fork", headers=headers, json=fork_payload).json()
    repeated_child = client.post(base + "/fork", headers=headers, json=fork_payload).json()
    assert repeated_child["credential_delivery"] == "initial_response_only"
    assert "participant_token" not in repeated_child
    child_base = f"/api/v1/sessions/{child['session_id']}"
    child_headers = bearer(child["participant_token"])
    assert (
        client.post(
            child_base + "/messages",
            headers=child_headers,
            json={
                "message": "Прекращаю переговоры.",
                "idempotency_key": "openapi-child-stop",
                "expected_revision": child["revision"],
            },
        ).status_code
        == 200
    )
    assert client.get(child_base + "/comparison", headers=child_headers).status_code == 200
    admin = bearer("test-admin")
    from .test_llm_trace import record_fixture
    client.app.state.llm_traces.enabled = True
    trace_id = record_fixture(client.app.state.llm_traces)
    assert client.get("/api/v1/admin/llm-traces", headers=admin).status_code == 200
    assert client.get(f"/api/v1/admin/llm-traces/{trace_id}", headers=admin).status_code == 200
    assert client.get("/api/v1/admin/sessions", headers=admin).status_code == 200
    assert client.get(f"/api/v1/admin/sessions/{session_id}", headers=admin).status_code == 200
    fresh = client.post("/api/v1/sessions", json=create_payload("openapi-close")).json()
    assert (
        client.post(
            f"/api/v1/sessions/{fresh['session_id']}/close",
            headers=admin,
            json={"idempotency_key": "close", "expected_revision": 0, "reason": "test"},
        ).status_code
        == 200
    )
    assert {
        name for name, status in checker.seen if status.startswith("2")
    } == EXPECTED_OPERATION_IDS


@pytest.mark.parametrize("authorization", [None, "Basic test", "Bearer wrong", "Bearer"])
def test_documented_authentication_errors_keep_existing_checks(client, authorization):
    created = client.post("/api/v1/sessions", json=create_payload("openapi-auth")).json()
    headers = {"Authorization": authorization} if authorization is not None else {}
    for path in (f"/api/v1/sessions/{created['session_id']}", "/api/v1/admin/sessions"):
        response = client.get(path, headers=headers)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_documented_error_shapes(client, settings):
    assert client.get("/api/v1/scenarios/missing").status_code == 404
    assert client.post("/api/v1/sessions", json={}).status_code == 422
    invalid = create_payload("openapi-invalid", language="en")
    assert client.post("/api/v1/sessions", json=invalid).status_code == 422
    created = client.post("/api/v1/sessions", json=create_payload("openapi-conflict")).json()
    headers = bearer(created["participant_token"])
    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=headers,
        json={"message": "Здравствуйте.", "idempotency_key": "conflict", "expected_revision": 999},
    )
    assert response.status_code == 409
    assert (
        client.get(f"/api/v1/sessions/{created['session_id']}/review", headers=headers).status_code
        == 409
    )
    with TestClient(create_app(replace(settings, admin_token=""))) as disabled:
        disabled.event_hooks["response"].append(ResponseContractCheck(disabled.app))
        assert disabled.get("/api/v1/admin/sessions").status_code == 503


def test_coaching_pending_response_contract(client):
    payload = create_payload("openapi-pending")
    payload["training"] = {}
    created = client.post("/api/v1/sessions", json=payload).json()
    headers = bearer(created["participant_token"])
    base = f"/api/v1/sessions/{created['session_id']}"
    done = client.post(
        base + "/messages",
        headers=headers,
        json={
            "message": "Прекращаю переговоры.",
            "idempotency_key": "stop",
            "expected_revision": 0,
        },
    ).json()
    with client.app.state.database.write_transaction() as connection:
        connection.execute(
            "INSERT INTO training_reviews(session_id, participant_id, source_revision, status) "
            "VALUES (?, ?, ?, 'pending')",
            (created["session_id"], created["observation"]["participant_id"], done["revision"]),
        )
    response = client.post(base + "/coaching", headers=headers)
    assert response.status_code == 202
    assert response.json() == {"status": "pending"}
