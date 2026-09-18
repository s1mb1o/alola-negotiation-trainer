from __future__ import annotations

from copy import deepcopy
import json

import pytest

from backend.dialogue_smoke_artifacts import build_public_artifact_session
from benchmarks.dialogue_quality import analyze, export_scorecard


def public_detail() -> dict:
    return {
        "session_id": "sess_artifact",
        "scenario_id": "office_rent_ru",
        "scenario_version": 4,
        "scenario_title": "Годовая аренда офиса",
        "language": "ru",
        "currency": "RUB",
        "difficulty": "easy",
        "run_mode": "training",
        "hints_enabled": False,
        "status": "active",
        "revision": 2,
        "participants": [
            {"participant_id": "player", "role": "tenant", "controller": "human"},
            {
                "participant_id": "npc",
                "role": "landlord",
                "controller": "built_in_npc",
                "provider": "configured-live-target",
                "model": "configured-live-model",
            },
        ],
        "messages": [
            {
                "message_id": "m_player",
                "session_revision": 1,
                "participant_id": "player",
                "role": "tenant",
                "language": "ru",
                "content": "Как вы обоснуете цену?",
            },
            {
                "session_revision": 2,
                "participant_id": "npc",
                "role": "landlord",
                "language": "ru",
                "content": "Какой бюджет вы рассматриваете?",
            },
        ],
        "events": [
            {
                "event_id": "evt_offer",
                "type": "offer.created",
                "participant_id": "npc",
                "session_revision": 0,
                "payload": {
                    "offer_id": "offer_current",
                    "offer_revision": 1,
                    "terms": {"price": 2500000},
                    "unresolved_required_terms": ["prepayment_fraction"],
                },
            },
            {
                "event_id": "evt_reply",
                "type": "npc.utterance.delivered",
                "participant_id": "npc",
                "session_revision": 2,
                "payload": {
                    "speech_act": "focused_discussion",
                    "requested_term_id": "price",
                    "dialogue_renderer": {
                        "mode": "llm",
                        "provider": "offline-fixture",
                        "model": "fixture-v1",
                        "attempted_generation": True,
                        "fallback_used": False,
                        "latency_ms": 1.5,
                    },
                },
            },
        ],
        "offers": [
            {
                "offer_id": "offer_current",
                "offer_revision": 1,
                "proposer_participant_id": "npc",
                "terms": {"price": 2500000, "prepayment_fraction": 0},
                "status": "active",
                "created_session_revision": 0,
            }
        ],
    }


def run_metadata() -> dict:
    return {
        "execution_mode": "offline",
        "suite": "dr28-v1",
        "case_id": "numeric-question",
        "provider": "offline-fixture",
        "model": "fixture-v1",
        "target_provider": "qwen",
        "target_model": "qwen3.8-max",
        "configuration_id": "test-config-v1",
        "prompt_version": "dr28-smoke-v1",
        "seed": 17,
        "max_turns": 8,
    }


def test_public_envelope_preserves_provenance_sources_and_evaluator_compatibility():
    record = build_public_artifact_session(public_detail(), metadata=run_metadata())
    artifact = {"version": 1, "sessions": [record]}
    assert record["participants"][1]["provider"] == "offline-fixture"
    assert record["participants"][1]["model"] == "fixture-v1"
    assert record["run_metadata"]["target_model"] == "qwen3.8-max"
    assert record["run_metadata"]["configuration_id"] == "test-config-v1"
    assert "target_model" not in record["participants"][1]
    assert record["offers"][0]["terms"]["prepayment_fraction"] == 0
    scorecard = export_scorecard(artifact)
    source = scorecard["sessions"][0]
    assert source["context"][0]["source_message_id"] == "m_player"
    assert source["context"][1]["source_message_id"] == "msg:npc:2:1"
    assert source["public_offer_events"][0]["source_event_id"] == "evt_offer"
    assert all(value is None for value in source["ratings"][0]["dimensions"].values())
    evaluation = analyze(artifact, scorecard)
    result = evaluation["sessions"][0]
    assert result["metadata"]["provider"] == "offline-fixture"
    assert result["metadata"]["model"] == "fixture-v1"
    assert result["metadata"]["scenario_version"] == 4
    assert result["dialogue_quality"]["rendering"]["latency_ms"]["average"] == 1.5
    assert result["dialogue_quality"]["human_review"]["status"] == "unrated"
    source["ratings"][0].update(
        reviewer_id="local-reviewer", evidence_source_ids=["m_player", "evt_offer"]
    )
    source["ratings"][0]["dimensions"]["relevance"] = 3
    assert (
        analyze(artifact, scorecard)["sessions"][0]["dialogue_quality"]["human_review"][
            "dimensions"
        ]["relevance"]
        == 3
    )


def test_private_and_malicious_extra_fields_are_not_copied_at_any_depth():
    detail = public_detail()
    secret = "DO-NOT-EXPORT-THIS-FIELD"
    for field in (
        "role_brief",
        "review",
        "raw_state",
        "internal_payloads",
        "participant_credentials",
        "provider_request",
        "private_json",
        "token",
        "benchmark_run",
    ):
        detail[field] = {"nested": secret}
    detail["dialogue_quality"] = {
        "private": secret,
        "human_review": {"dimensions": {"relevance": 4}},
    }
    detail["participants"][1].update(
        token=secret, role_brief=secret, provenance={"api_key": secret}
    )
    detail["messages"][0].update(provider_request=secret, private_payload=secret, review=secret)
    detail["events"][0].update(internal_payloads=secret, raw_state=secret)
    detail["events"][0]["payload"].update(private=secret, role_brief=secret, token=secret)
    detail["events"][0]["payload"]["terms"].update(
        api_key=secret,
        role_brief=secret,
        reservation_utility=5,
        malicious_object={"private": secret},
    )
    detail["events"][1]["payload"]["dialogue_renderer"].update(
        raw_error=secret,
        exception=secret,
        provider_request=secret,
        failure_reason=secret,
        validation_failure=secret,
    )
    detail["events"].append(
        {"type": "internal.npc.policy", "payload": {"terms": {"price": 1}, "secret": secret}}
    )
    detail["offers"][0].update(private_payload=secret, utility=secret)
    detail["offers"][0]["terms"].update(token=secret, nested={"private": secret})
    metadata = {**run_metadata(), "api_key": secret, "request": {"private": secret}}
    record = build_public_artifact_session(detail, metadata=metadata)
    encoded = json.dumps(record, ensure_ascii=False, allow_nan=False)
    assert secret not in encoded
    assert len(record["events"]) == 2
    assert record["events"][0]["payload"]["terms"] == {"price": 2500000}
    renderer = record["events"][1]["payload"]["dialogue_renderer"]
    assert renderer["failure_reason"] is None
    assert renderer["validation_failure"] == "other"
    assert record["dialogue_quality"]["human_review"]["status"] == "unrated"
    assert record["dialogue_quality"]["rendering"]["validation_failures"] == {"other": 1}
    for forbidden in (
        "role_brief",
        "raw_state",
        "private_payload",
        "provider_request",
        "api_key",
        "token",
    ):
        assert f'"{forbidden}"' not in encoded


def test_clarification_recovery_reason_and_public_currency_context_survive_export():
    detail = public_detail()
    detail["events"].append(
        {
            "event_id": "evt_clarify",
            "session_revision": 3,
            "participant_id": "player",
            "type": "clarification.required",
            "payload": {
                "reason_code": "numeric_answer_requires_term",
                "expected_currency": "EUR",
                "provided_currencies": ["USD"],
                "private_details": {"secret": "never-export"},
            },
        }
    )
    record = build_public_artifact_session(detail, metadata=run_metadata())
    assert record["events"][-1] == {
        "event_id": "evt_clarify",
        "session_revision": 3,
        "participant_id": "player",
        "type": "clarification.required",
        "payload": {
            "reason_code": "numeric_answer_requires_term",
            "expected_currency": "EUR",
            "provided_currencies": ["USD"],
        },
    }


@pytest.mark.parametrize(
    "path",
    [
        ("scenario_title",),
        ("scenario_id",),
        ("session_id",),
        ("participants", 0, "role"),
        ("participants", 0, "participant_id"),
        ("participants", 0, "provider"),
        ("messages", 0, "content"),
        ("messages", 0, "message_id"),
        ("messages", 0, "created_at"),
        ("events", 0, "event_id"),
        ("events", 0, "payload", "offer_id"),
        ("events", 0, "payload", "terms", "description"),
        ("events", 1, "payload", "dialogue_renderer", "model"),
        ("offers", 0, "offer_id"),
        ("offers", 0, "terms", "description"),
    ],
)
def test_custom_secrets_are_redacted_from_every_exported_text_category(path):
    detail = public_detail()
    secret = "custom-provider-secret-value"
    target = detail
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = f"prefix-{secret}-suffix"
    record = build_public_artifact_session(detail, metadata=run_metadata(), known_secrets=(secret,))
    encoded = json.dumps(record)
    assert secret not in encoded
    assert "[REDACTED_CREDENTIAL]" in encoded


@pytest.mark.parametrize(
    "field",
    [
        "suite",
        "case_id",
        "provider",
        "model",
        "target_provider",
        "target_model",
        "configuration_id",
        "prompt_version",
    ],
)
def test_metadata_strings_redact_custom_secrets(field):
    metadata = run_metadata()
    secret = "custom-secret-for-metadata"
    metadata[field] = secret
    record = build_public_artifact_session(
        public_detail(), metadata=metadata, known_secrets=(secret,)
    )
    assert secret not in json.dumps(record)
    assert record["run_metadata"][field] == "[REDACTED_CREDENTIAL]"


def test_key_shapes_configured_custom_environment_and_truncation_are_redacted(monkeypatch):
    key_shaped = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
    environment_secret = "custom-configured-npc-credential"
    crossing_secret = "secret-over-boundary"
    monkeypatch.setenv("NEGOTIATION_NPC_API_KEY_ENV", "SMOKE_TEST_PROVIDER_KEY")
    monkeypatch.setenv("SMOKE_TEST_PROVIDER_KEY", environment_secret)
    detail = public_detail()
    detail["messages"][0]["content"] = (
        key_shaped + environment_secret + "x" * 10000 + crossing_secret
    )
    detail["messages"][1]["content"] = "x" * 9992 + crossing_secret
    record = build_public_artifact_session(
        detail, metadata=run_metadata(), known_secrets=(crossing_secret,)
    )
    encoded = json.dumps(record)
    assert key_shaped not in encoded
    assert environment_secret not in encoded
    assert "secret-o" not in encoded
    assert all(len(row["content"]) <= 10000 for row in record["messages"])


@pytest.mark.parametrize(
    "field,maximum", [("participants", 8), ("messages", 1000), ("events", 5000), ("offers", 1000)]
)
def test_history_bounds_fail_closed_without_truncating_source_history(field, maximum):
    detail = public_detail()
    detail[field] = [{}] * (maximum + 1)
    with pytest.raises(ValueError, match="oversized"):
        build_public_artifact_session(detail, metadata=run_metadata())


@pytest.mark.parametrize("field", ["participants", "messages", "events", "offers"])
@pytest.mark.parametrize("invalid", ["not-an-array", ["not-an-object"]])
def test_malformed_arrays_are_rejected(field, invalid):
    detail = public_detail()
    detail[field] = invalid
    with pytest.raises(ValueError):
        build_public_artifact_session(detail, metadata=run_metadata())


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf"), 10**1000])
def test_nonfinite_or_unbounded_numbers_are_not_serialized(invalid):
    detail = public_detail()
    detail["offers"][0]["terms"]["invalid_amount"] = invalid
    detail["events"][1]["payload"]["dialogue_renderer"]["latency_ms"] = invalid
    record = build_public_artifact_session(detail, metadata=run_metadata())
    assert "invalid_amount" not in record["offers"][0]["terms"]
    assert record["dialogue_quality"]["rendering"]["latency_ms"]["samples"] == 0
    json.dumps(record, allow_nan=False)


def test_record_is_detached_and_cannot_mutate_another_session_or_its_input():
    detail = public_detail()
    before = deepcopy(detail)
    first = build_public_artifact_session(detail, metadata=run_metadata())
    second = build_public_artifact_session(detail, metadata=run_metadata())
    first["offers"][0]["terms"]["price"] = 1
    first["events"][0]["payload"]["unresolved_required_terms"].append("other")
    first["run_metadata"]["model"] = "changed"
    assert detail == before
    assert second["offers"][0]["terms"]["price"] == 2500000
    assert second["events"][0]["payload"]["unresolved_required_terms"] == ["prepayment_fraction"]
    assert second["run_metadata"]["model"] == "fixture-v1"


def test_actual_admin_detail_can_be_exported_and_evaluated(client):
    from backend.tests.conftest import create_payload

    created = client.post("/api/v1/sessions", json=create_payload("artifact-integration")).json()
    session_id = created["session_id"]
    detail_response = client.get(
        f"/api/v1/admin/sessions/{session_id}", headers={"Authorization": "Bearer test-admin"}
    )
    assert detail_response.status_code == 200
    record = build_public_artifact_session(
        detail_response.json(), metadata=run_metadata(), known_secrets=("test-admin",)
    )
    assert record["session_id"] == session_id
    assert "review" not in record
    assert len(analyze({"sessions": [record]})["sessions"]) == 1
    assert "participant_credentials" not in json.dumps(record)
