from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

from fastapi.testclient import TestClient

from backend.app.main import create_app

from .conftest import bearer, create_payload


def test_session_persists_across_app_restart(settings) -> None:
    with TestClient(create_app(settings)) as first_client:
        created = first_client.post(
            "/api/v1/sessions", json=create_payload("persistent-session")
        ).json()
        token = created["participant_token"]
        session_id = created["session_id"]

    with TestClient(create_app(settings)) as second_client:
        response = second_client.get(f"/api/v1/sessions/{session_id}", headers=bearer(token))
        assert response.status_code == 200
        assert response.json()["revision"] == created["revision"]
        assert second_client.get("/api/v1/health").json()["journal_mode"] == "wal"


def test_expected_revision_allows_only_one_concurrent_writer(client: TestClient) -> None:
    created = client.post("/api/v1/sessions", json=create_payload("concurrent-session")).json()
    session_id = created["session_id"]
    headers = bearer(created["participant_token"])

    def submit(index: int):
        return client.post(
            f"/api/v1/sessions/{session_id}/messages",
            headers=headers,
            json={
                "message": "Какие условия для вас важны?",
                "idempotency_key": f"concurrent-{index}",
                "expected_revision": created["revision"],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, (1, 2)))

    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["error"] == "revision_conflict"
    winner = next(response for response in responses if response.status_code == 200)
    current = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert current.json()["revision"] == winner.json()["revision"]


def test_message_idempotency_returns_original_post_npc_response(client: TestClient) -> None:
    created = client.post("/api/v1/sessions", json=create_payload("message-idempotency")).json()
    request = {
        "message": "Какие условия для вас важны?",
        "idempotency_key": "same-message",
        "expected_revision": created["revision"],
    }
    url = f"/api/v1/sessions/{created['session_id']}/messages"
    headers = bearer(created["participant_token"])
    first = client.post(url, headers=headers, json=request)
    second = client.post(url, headers=headers, json=request)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_legacy_plaintext_create_credentials_are_revoked_and_removed(settings) -> None:
    with TestClient(create_app(settings)) as first_client:
        created = first_client.post(
            "/api/v1/sessions", json=create_payload("legacy-credential-row")
        ).json()
        database = first_client.app.state.database
        with database.write_transaction() as connection:
            connection.execute("DELETE FROM schema_migrations WHERE version = 2")
            connection.execute(
                "UPDATE idempotency_results SET response_json = ? "
                "WHERE scope = 'create_session' AND idempotency_key = ?",
                (
                    json.dumps(
                        {
                            "session_id": created["session_id"],
                            "participant_token": created["participant_token"],
                            "participant_credentials": created["participant_credentials"],
                        }
                    ),
                    "legacy-credential-row",
                ),
            )

    with TestClient(create_app(settings)) as second_client:
        database = second_client.app.state.database
        with database.read_connection() as connection:
            legacy_count = connection.execute(
                "SELECT COUNT(*) FROM idempotency_results "
                "WHERE instr(response_json, 'participant_token') > 0"
            ).fetchone()[0]
            token_hashes = connection.execute(
                "SELECT token_hash FROM participants WHERE session_id = ?",
                (created["session_id"],),
            ).fetchall()
        assert legacy_count == 0
        assert all(row["token_hash"] is None for row in token_hashes)
