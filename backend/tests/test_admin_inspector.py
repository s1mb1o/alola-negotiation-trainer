from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app

from .conftest import PROJECT_ROOT, bearer, create_payload, credentials


ADMIN_HEADERS = bearer("test-admin")


def _walk_away(client: TestClient, created: dict, token: str, key: str) -> None:
    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(token),
        json={
            "message": "Прекращаю переговоры.",
            "idempotency_key": key,
            "expected_revision": created["revision"],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "walked_away"


def _benchmark_payload(key: str, trial_id: str) -> dict:
    payload = create_payload(key, both_external=True, hints_enabled=False)
    payload.update(
        {
            "run_mode": "benchmark",
            "benchmark_run_id": "admin-inspector-run",
            "trial_id": trial_id,
            "benchmark_expected_trials": 2,
            "seed": 100 + int(trial_id[-1]),
        }
    )
    return payload


def test_admin_inspector_requires_configured_administrator_token(
    client: TestClient, tmp_path: Path
) -> None:
    created = client.post(
        "/api/v1/sessions", headers=bearer("test-admin"), json=create_payload("admin-auth")
    ).json()
    endpoint = "/api/v1/admin/sessions"

    assert client.get(endpoint).status_code == 401
    participant_attempt = client.get(endpoint, headers=bearer(created["participant_token"]))
    assert participant_attempt.status_code == 401
    assert participant_attempt.json()["error"] == "administrator_unauthorized"

    disabled_settings = Settings(
        database_path=tmp_path / "disabled-admin.sqlite3",
        scenario_directories=(PROJECT_ROOT / "examples",),
        scenario_schema_path=PROJECT_ROOT / "schemas" / "scenario-v1.schema.json",
        admin_token="",
    )
    with TestClient(create_app(disabled_settings)) as disabled_client:
        disabled = disabled_client.get(endpoint, headers=bearer("any-token"))
    assert disabled.status_code == 503
    assert disabled.json()["error"] == "administrative_access_disabled"


def test_admin_session_list_filters_pages_and_omits_credentials(client: TestClient) -> None:
    ru_payload = create_payload("admin-list-ru")
    ru_payload["participants"][0].update(
        {"provider": "openai", "model": "gpt-test", "prompt_version": "prompt-v1"}
    )
    ru = client.post("/api/v1/sessions", headers=bearer("test-admin"), json=ru_payload).json()

    en_payload = create_payload("admin-list-en", language="en")
    en_payload["scenario_id"] = "freight_contract_en"
    en = client.post("/api/v1/sessions", headers=bearer("test-admin"), json=en_payload).json()

    response = client.get(
        "/api/v1/admin/sessions",
        headers=ADMIN_HEADERS,
        params={
            "status": "active",
            "scenario_id": "freight_contract_en",
            "language": "en",
            "run_mode": "training",
            "limit": 1,
            "offset": 0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert body["items"][0]["session_id"] == en["session_id"]
    assert body["items"][0]["review_state"] == "not_ready"

    all_sessions = client.get("/api/v1/admin/sessions", headers=ADMIN_HEADERS).json()
    ru_item = next(item for item in all_sessions["items"] if item["session_id"] == ru["session_id"])
    buyer = next(item for item in ru_item["participants"] if item["role"] == "buyer")
    assert buyer["provider"] == "openai"
    assert buyer["model"] == "gpt-test"
    assert buyer["prompt_version"] == "prompt-v1"
    serialized = json.dumps(all_sessions)
    assert ru["participant_token"] not in serialized
    assert "token_hash" not in serialized
    assert "state_json" not in serialized
    assert "source_json" not in serialized


def test_admin_session_detail_contains_only_safe_operational_projection(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/sessions", headers=bearer("test-admin"), json=create_payload("admin-detail")
    ).json()
    session_id = created["session_id"]
    database = client.app.state.database
    with database.write_transaction() as connection:
        connection.execute(
            "UPDATE sessions SET state_json = ? WHERE id = ?",
            ('{"hidden_marker":"RAW_STATE_SECRET"}', session_id),
        )
        connection.execute(
            "UPDATE events SET private_payload_json = ? WHERE session_id = ?",
            ('{"hidden_marker":"PRIVATE_EVENT_SECRET"}', session_id),
        )

    response = client.get(f"/api/v1/admin/sessions/{session_id}", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["participants"]
    assert body["events"]
    assert body["offers"]
    assert body["review_state"] == "not_ready"
    assert body["review"] is None
    assert body["benchmark_run"] is None
    serialized = response.text
    assert "RAW_STATE_SECRET" not in serialized
    assert "PRIVATE_EVENT_SECRET" not in serialized
    assert "private_payload" not in serialized
    assert "token_hash" not in serialized
    assert created["participant_token"] not in serialized


def test_admin_review_uses_public_projection_after_training_termination(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/sessions", headers=bearer("test-admin"), json=create_payload("admin-review")
    ).json()
    _walk_away(client, created, created["participant_token"], "admin-review-walk")

    response = client.get(
        f"/api/v1/admin/sessions/{created['session_id']}",
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["review_state"] == "available"
    assert body["review"]["outcome"]["termination_reason"] == "walked_away"
    assert "participant_scores" not in response.text
    assert "reservation_utility" not in response.text


def test_admin_benchmark_review_stays_sealed_until_complete_run_set(
    client: TestClient,
) -> None:
    first = client.post(
        "/api/v1/sessions",
        headers=bearer("test-admin"),
        json=_benchmark_payload("admin-bench-1", "trial-1"),
    ).json()
    first_tokens = credentials(first)
    _walk_away(client, first, first_tokens["buyer"], "admin-bench-walk-1")

    sealed = client.get(
        f"/api/v1/admin/sessions/{first['session_id']}",
        headers=ADMIN_HEADERS,
    )
    assert sealed.status_code == 200
    assert sealed.json()["review_state"] == "sealed"
    assert sealed.json()["review"] is None
    assert sealed.json()["benchmark_run"]["release_ready"] is False
    assert "participant_scores" not in sealed.text

    second = client.post(
        "/api/v1/sessions",
        headers=bearer("test-admin"),
        json=_benchmark_payload("admin-bench-2", "trial-2"),
    ).json()
    second_tokens = credentials(second)
    _walk_away(client, second, second_tokens["buyer"], "admin-bench-walk-2")

    released = client.get(
        f"/api/v1/admin/sessions/{first['session_id']}",
        headers=ADMIN_HEADERS,
    )
    assert released.status_code == 200
    assert released.json()["review_state"] == "available"
    assert released.json()["review"] is not None
    assert released.json()["benchmark_run"]["release_ready"] is True
    assert "participant_scores" not in released.text
