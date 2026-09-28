from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import bearer, create_payload


def submit(
    client: TestClient,
    session_id: str,
    token: str,
    revision: int,
    message: str,
    key: str,
) -> dict:
    response = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        headers=bearer(token),
        json={
            "message": message,
            "expected_revision": revision,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_pinned_release_journey_compares_two_decisions(client: TestClient) -> None:
    payload = create_payload("release-journey", difficulty="normal")
    payload.update(
        scenario_id="supplier_001",
        scenario_version=6,
        training={"relationship": "successful_history"},
    )
    created_response = client.post("/api/v1/sessions", json=payload)
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    root_id = created["session_id"]
    root_token = created["participant_token"]

    greeted = submit(
        client, root_id, root_token, created["revision"], "Здравствуйте.", "release-greeting"
    )
    assert greeted["revision"] == 2
    checkpoints = client.get(
        f"/api/v1/sessions/{root_id}/checkpoints", headers=bearer(root_token)
    ).json()
    assert 2 in [item["source_revision"] for item in checkpoints["checkpoints"]]

    first = submit(
        client,
        root_id,
        root_token,
        greeted["revision"],
        "Предлагаю цену 112 000 EUR, аванс 100% и поставку за 8 недель.",
        "release-first-package",
    )
    assert first["status"] == "agreement_reached"
    first_review = client.get(
        f"/api/v1/sessions/{root_id}/review", headers=bearer(root_token)
    ).json()
    assert first_review["outcome"]["participant_utility"] == 26

    fork_response = client.post(
        f"/api/v1/sessions/{root_id}/fork",
        headers=bearer(root_token),
        json={"source_revision": 2, "idempotency_key": "release-better-branch"},
    )
    assert fork_response.status_code == 201, fork_response.text
    child = fork_response.json()
    child_id = child["session_id"]
    child_token = child["participant_token"]

    interests = submit(
        client,
        child_id,
        child_token,
        child["revision"],
        "Какие ваши приоритеты?",
        "release-interest-question",
    )
    second = submit(
        client,
        child_id,
        child_token,
        interests["revision"],
        "Предлагаю цену 105 000 EUR, аванс 100% и поставку за 2 недели.",
        "release-second-package",
    )
    assert second["status"] == "agreement_reached"
    second_review = client.get(
        f"/api/v1/sessions/{child_id}/review", headers=bearer(child_token)
    ).json()
    assert second_review["outcome"]["participant_utility"] == 70

    comparison = client.get(
        f"/api/v1/sessions/{child_id}/comparison", headers=bearer(child_token)
    ).json()
    assert comparison["utility_delta"] == 44
    assert comparison["same_initial_conditions_at_checkpoint"] is True
    assert comparison["causal_improvement_claim"] is False


def test_pinned_release_exit_path(client: TestClient) -> None:
    payload = create_payload("release-exit", difficulty="normal")
    payload.update(scenario_id="supplier_001", scenario_version=6)
    created = client.post("/api/v1/sessions", json=payload).json()

    ended = submit(
        client,
        created["session_id"],
        created["participant_token"],
        created["revision"],
        "Прекращаю переговоры.",
        "release-explicit-exit",
    )

    assert ended["status"] == "walked_away"
    review = client.get(
        f"/api/v1/sessions/{created['session_id']}/review",
        headers=bearer(created["participant_token"]),
    ).json()
    assert review["outcome"]["termination_reason"] == "walked_away"
