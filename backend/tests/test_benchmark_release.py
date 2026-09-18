from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import bearer, create_payload, credentials


def _create_terminal_trial(client: TestClient, key: str, trial_id: str) -> tuple[dict, str]:
    payload = create_payload(key, both_external=True, hints_enabled=False)
    payload.update(
        {
            "run_mode": "benchmark",
            "benchmark_run_id": "bench_release_gate",
            "trial_id": trial_id,
            "benchmark_expected_trials": 2,
            "seed": 40 + int(trial_id[-1]),
        }
    )
    created_response = client.post("/api/v1/sessions", headers=bearer("test-admin"), json=payload)
    assert created_response.status_code == 201
    created = created_response.json()
    token = credentials(created)["buyer"]
    closed = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(token),
        json={
            "message": "Прекращаю переговоры.",
            "idempotency_key": f"close-{trial_id}",
            "expected_revision": created["revision"],
        },
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "walked_away"
    return created, token


def test_benchmark_reviews_and_scores_wait_for_complete_run_set(client: TestClient) -> None:
    first, first_token = _create_terminal_trial(client, "bench-create-1", "trial-1")

    sealed = client.get(
        f"/api/v1/sessions/{first['session_id']}/review", headers=bearer(first_token)
    )
    assert sealed.status_code == 409
    assert sealed.json()["error"] == "benchmark_review_sealed"
    assert sealed.json()["benchmark_run"]["release_ready"] is False

    incomplete_stats = client.get("/api/v1/stats").json()
    assert incomplete_stats["benchmark_runs"][0]["release_ready"] is False
    incomplete_model = next(
        row for row in incomplete_stats["by_model"] if row["model"] == "unspecified"
    )
    assert incomplete_model["avg_outcome_score"] is None
    assert incomplete_model["avg_skill_score"] is None

    _second, _second_token = _create_terminal_trial(client, "bench-create-2", "trial-2")

    released = client.get(
        f"/api/v1/sessions/{first['session_id']}/review", headers=bearer(first_token)
    )
    assert released.status_code == 200
    assert isinstance(released.json()["outcome_score"], (int, float))

    complete_stats = client.get("/api/v1/stats").json()
    run = complete_stats["benchmark_runs"][0]
    assert run["expected_trials"] == 2
    assert run["trial_count"] == 2
    assert run["release_ready"] is True
    complete_model = next(
        row for row in complete_stats["by_model"] if row["model"] == "unspecified"
    )
    assert isinstance(complete_model["avg_outcome_score"], (int, float))
    assert isinstance(complete_model["avg_skill_score"], (int, float))
