from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.dialogue_quality import analyze, export_scorecard, main


FIXTURE = Path(__file__).parents[1] / "fixtures" / "dialogue_quality_cases.json"


@pytest.fixture
def artifact():
    return json.loads(FIXTURE.read_text())


def test_connected_bilingual_corpus_has_typical_and_adversarial_cases(artifact):
    assert {session["language"] for session in artifact["sessions"]} == {"ru", "en"}
    for language in ("ru", "en"):
        sessions = [session for session in artifact["sessions"] if session["language"] == language]
        tags = {tag for session in sessions for tag in session["tags"]}
        assert {"numeric_question", "relative_change", "short_reply", "correction", "repetition", "false_claim"} <= tags
        assert all(len(session["messages"]) >= 8 for session in sessions)
    report = analyze(artifact)
    assert report["offline"] is True
    assert len(report["groups"]) == 2
    assert all(group["fallback_rate"] is None for group in report["groups"])
    assert all(all(value is None for value in group["human_dimensions"].values()) for group in report["groups"])


def test_scorecard_requires_explicit_human_ratings_and_keeps_missing_dimensions_unrated(artifact):
    scorecard = export_scorecard(artifact)
    rating = scorecard["sessions"][0]["ratings"][0]
    assert all(value is None for value in rating["dimensions"].values())
    rating.update(reviewer_id="human-reviewer", evidence_source_ids=[rating["source_message_id"]])
    rating["dimensions"]["relevance"] = 3
    report = analyze(artifact, scorecard)
    review = report["sessions"][0]["dialogue_quality"]["human_review"]
    assert review["dimensions"]["relevance"] == 3
    assert review["dimensions"]["continuity"] is None
    assert review["coverage"] == {"rated_turns": 1, "eligible_turns": 6}
    assert review["dimension_samples"]["relevance"] == 1


@pytest.mark.parametrize("value", [-1, 5, True, 2.5, "3"])
def test_scorecard_rejects_invalid_ratings(artifact, value):
    card = export_scorecard(artifact)
    card["sessions"][0]["ratings"][0]["dimensions"]["relevance"] = value
    with pytest.raises(ValueError):
        analyze(artifact, card)


@pytest.mark.parametrize("mutation", ["reviewer", "evidence", "unknown_source", "duplicate", "version", "source_changed", "card_context_changed"])
def test_scorecard_checks_provenance_and_coverage(artifact, mutation):
    card = export_scorecard(artifact)
    rating = card["sessions"][0]["ratings"][0]
    rating.update(reviewer_id="reviewer", evidence_source_ids=[rating["source_message_id"]])
    rating["dimensions"]["relevance"] = 4
    if mutation == "reviewer":
        rating["reviewer_id"] = None
    elif mutation == "evidence":
        rating["evidence_source_ids"] = []
    elif mutation == "unknown_source":
        rating["evidence_source_ids"] = ["unknown-message"]
    elif mutation == "duplicate":
        card["sessions"][0]["ratings"].append(copy.deepcopy(rating))
    elif mutation == "version":
        card["rubric_version"] = "unsupported-rubric"
    elif mutation == "card_context_changed":
        card["sessions"][0]["context"][0]["content"] = "Altered review context"
    else:
        artifact["sessions"][0]["messages"][0]["content"] = "Changed source"
    with pytest.raises(ValueError):
        analyze(artifact, card)


def test_different_scenario_versions_and_providers_do_not_merge(artifact):
    artifact["sessions"][1]["scenario_version"] = 2
    artifact["sessions"][2]["participants"][1]["provider"] = "other"
    assert len(analyze(artifact)["groups"]) == 4


def test_different_participant_prompt_versions_do_not_merge(artifact):
    artifact["sessions"][0]["participants"][1]["prompt_version"] = "new-prompt"
    assert len(analyze(artifact)["groups"]) == 3


def test_exports_do_not_copy_private_fields_tokens_or_raw_failures(artifact, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-private-key")
    session = artifact["sessions"][0]
    session.update(participant_token="fixture-private-key", hidden_state={"secret": "hidden-canary"})
    session["messages"][0]["content"] += " fixture-private-key"
    session["events"][0]["payload"]["private_payload"] = {"secret": "hidden-canary"}
    encoded = json.dumps(export_scorecard(artifact)) + json.dumps(analyze(artifact))
    assert "fixture-private-key" not in encoded
    assert "hidden-canary" not in encoded
    assert "[REDACTED" in encoded


def test_cli_is_offline_and_reports_input_errors_without_echoing_data(capsys, tmp_path):
    assert main(["analyze", str(FIXTURE)]) == 0
    assert json.loads(capsys.readouterr().out)["offline"] is True
    missing = tmp_path / "sensitive-file-name"
    assert main(["analyze", str(missing)]) == 2
    assert "sensitive-file-name" not in capsys.readouterr().err
