from __future__ import annotations

import json

import pytest

from backend.app.dialogue_quality import build_dialogue_quality, message_source_id


def message(identifier, text, participant="npc"):
    return {"id": identifier, "participant_id": participant, "session_revision": 1, "content": text}


def event(identifier, metadata=None, participant="npc", event_type="npc.utterance.delivered"):
    return {"event_id": identifier, "participant_id": participant, "type": event_type,
            "payload": {"dialogue_renderer": metadata} if metadata is not None else {}}


def quality(messages=(), events=()):
    return build_dialogue_quality(messages, events, npc_participant_ids=["npc"])


def test_empty_and_historical_data_stay_unavailable():
    result = quality()
    assert result["rendering"]["fallback_count"] is None
    assert result["rendering"]["fallback_rate"] is None
    assert result["rendering"]["latency_ms"] == {"samples": 0, "average": None, "p95": None}
    historical = quality([message("m1", "Hello")], [event("e1")])
    assert historical["rendering"]["delivered_turns"] == 1
    assert historical["rendering"]["telemetry_turns"] == 0
    assert historical["human_review"]["dimensions"] == dict.fromkeys(("relevance", "continuity", "attribution", "unsupported_claims"))


@pytest.mark.parametrize("question", ["Какой вариант вы предлагаете?", "What would you propose?"])
def test_repetition_is_per_npc_source_attributed_and_not_a_quality_score(question):
    result = quality([message("m1", question), message("m2", question, "player"),
                      message("m3", "  " + question.upper()), message("m4", "Понятно. " + question)])
    assert result["turns"] == {"total": 4, "player": 1, "npc": 3}
    assert result["repetition"]["exact_repeat_count"] == 1
    assert result["repetition"]["question_repeat_count"] == 2
    assert result["repetition"]["flags"][0] == {"kind": "exact_repeat", "source_message_id": "m3", "repeats_source_message_id": "m1"}
    assert result["heuristic_only"] is True
    assert "score" not in result


def test_latency_and_fallback_use_generation_attempts_not_canonical_answers():
    result = quality(events=[
        event("e0", {"mode": "template", "fallback_used": False, "attempted_generation": False, "latency_ms": 0}),
        event("e1", {"mode": "llm", "fallback_used": False, "latency_ms": 100}),
        event("e2", {"mode": "template", "fallback_used": True, "latency_ms": 300, "failure_reason": "output_invalid", "validation_failure": "numeric_reference"}),
        event("e3", {"mode": "llm", "fallback_used": False}),
        event("e3", {"mode": "llm", "fallback_used": False}),
    ])
    rendering = result["rendering"]
    assert rendering["delivered_turns"] == 4
    assert rendering["generation_attempts"] == 3
    assert rendering["fallback_observations"] == 3
    assert rendering["fallback_rate"] == 0.3333
    assert rendering["latency_ms"] == {"samples": 2, "average": 200.0, "p95": 300.0}
    assert rendering["failure_counts"] == {"output_invalid": 1}
    assert rendering["validation_failures"] == {"numeric_reference": 1}


@pytest.mark.parametrize("latency", [True, -1, float("nan"), float("inf"), "100", 86_400_001])
def test_invalid_latency_is_missing(latency):
    assert quality(events=[event("e", {"mode": "llm", "latency_ms": latency})])["rendering"]["latency_ms"]["samples"] == 0


def test_private_events_other_participants_and_arbitrary_metadata_are_not_exposed():
    secret = "private-secret-marker"
    result = quality([message(secret + " !", secret)], [
        event("e0", {"mode": "llm", "latency_ms": 5}, event_type="internal.npc.policy"),
        event("e1", {"mode": "llm", "latency_ms": 5}, participant="other-session-npc"),
        event("e2", {"mode": "template", "fallback_used": True, "failure_reason": secret,
                     "validation_failure": secret, "exception": secret, "api_key": secret}),
    ])
    assert secret not in json.dumps(result)
    assert result["rendering"]["delivered_turns"] == 1
    assert result["rendering"]["validation_failures"] == {"other": 1}


def test_repeat_flags_are_bounded_and_source_id_is_stable():
    rows = [{"participant_id": "npc", "session_revision": revision, "content": "Repeat?"} for revision in range(150)]
    result = quality(rows)
    assert len(result["repetition"]["flags"]) == 100
    assert result["repetition"]["flags_truncated"] is True
    assert result["repetition"]["exact_repeat_count"] == 149
    assert message_source_id(rows[0], 0) == "msg:npc:0:0"
    assert quality(rows) == result
