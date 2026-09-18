"""Offline dialogue diagnostics and source-attributed human scorecards.

Usage: python -m benchmarks.dialogue_quality export-scorecard public-sessions.json
       python -m benchmarks.dialogue_quality analyze public-sessions.json --scorecard ratings.json
No provider, service, or external judge is called.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from backend.app.dialogue import redact_untrusted_credentials
from backend.app.dialogue_quality import (
    HUMAN_DIMENSIONS, RUBRIC_VERSION, build_dialogue_quality, message_source_id,
)


RUBRIC = {
    "relevance": "Does the reply address the player's current intent?",
    "continuity": "Does the reply preserve topic, corrections, and unresolved questions?",
    "attribution": "Does the reply distinguish claims, proposals, quotations, and agreements?",
    "unsupported_claims": "Does the reply avoid commitments and factual claims without a public source?",
}
ANCHORS = {
    "0": "Clear, material failure.", "1": "Several substantial problems.",
    "2": "Mixed or partly adequate.", "3": "Adequate with a minor issue.",
    "4": "No observed issue in this dimension.",
}
META_FIELDS = ("provider", "model", "language", "scenario_id", "scenario_version", "difficulty", "run_mode", "hints_enabled")


def _text(value: Any, limit: int = 1000) -> str:
    return redact_untrusted_credentials(str(value))[:limit] if value is not None else ""


def _revision(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _sessions(artifact: Any) -> list[dict[str, Any]]:
    if not isinstance(artifact, dict):
        raise ValueError("Expected a public session detail or an object with sessions.")
    sessions = artifact.get("sessions", [artifact])
    if not isinstance(sessions, list) or not sessions or len(sessions) > 1000:
        raise ValueError("Expected 1 to 1000 sessions.")
    ids: set[str] = set()
    result = []
    for session in sessions:
        if not isinstance(session, dict) or not isinstance(session.get("session_id"), str):
            raise ValueError("Each session requires session_id.")
        if session["session_id"] in ids:
            raise ValueError("Duplicate session_id.")
        ids.add(session["session_id"])
        if not isinstance(session.get("messages"), list) or not isinstance(session.get("events", []), list):
            raise ValueError("Each session requires public messages and events arrays.")
        if len(session["messages"]) > 10000 or len(session.get("events", [])) > 50000:
            raise ValueError("Session exceeds offline evaluation bounds.")
        if not all(isinstance(row, dict) for row in session["messages"] + session.get("events", [])):
            raise ValueError("Messages and events must be objects.")
        result.append(session)
    return result


def _public_messages(session: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "source_message_id": message_source_id(message, index),
        "participant_id": _text(message.get("participant_id"), 160),
        "role": _text(message.get("role"), 100),
        "session_revision": _revision(message.get("session_revision")),
        "content": _text(message.get("content"), 10000),
    } for index, message in enumerate(session["messages"])]


def _public_offer_events(session: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for event in session.get("events", []):
        if event.get("type") not in {"offer.created", "offer.countered", "agreement.reached", "participant.reject", "participant.withdraw"}:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        safe = {key: payload[key] for key in ("offer_id", "offer_revision", "proposer_participant_id")
                if isinstance(payload.get(key), (str, int)) and not isinstance(payload.get(key), bool)}
        if isinstance(payload.get("terms"), dict):
            safe["terms"] = {key: value for key, value in payload["terms"].items()
                             if isinstance(value, (str, int, float, bool))}
        # Redact public text without ever serializing other event payload fields.
        safe = {key: {_text(term, 100): _text(value, 1000) if isinstance(value, str) else value for term, value in item.items()}
                if isinstance(item, dict) else _text(item, 200) if isinstance(item, str) else item
                for key, item in safe.items()}
        result.append({"source_event_id": _text(event.get("event_id"), 160),
                       "type": event["type"], "session_revision": _revision(event.get("session_revision")), "payload": safe})
    return result


def _seats(session: dict[str, Any]) -> list[dict[str, Any]]:
    participants = session.get("participants", [])
    if not isinstance(participants, list):
        raise ValueError("participants must be an array.")
    seats = [seat for seat in participants if isinstance(seat, dict)
             and seat.get("controller") in {"built_in_npc", "external_agent"}]
    if not all(isinstance(seat.get("participant_id"), str) for seat in seats):
        raise ValueError("Evaluated participants require participant_id.")
    if len({seat["participant_id"] for seat in seats}) != len(seats):
        raise ValueError("Duplicate evaluated participant_id.")
    return seats


def export_scorecard(artifact: Any) -> dict[str, Any]:
    """Export only public conversation context. Empty ratings are deliberately null."""
    result = []
    for session in _sessions(artifact):
        context = _public_messages(session)
        events = _public_offer_events(session)
        seats = {seat["participant_id"] for seat in _seats(session)}
        ratings = [{"source_message_id": row["source_message_id"], "reviewer_id": None,
                    "evidence_source_ids": [], "dimensions": dict.fromkeys(HUMAN_DIMENSIONS), "note": ""}
                   for row in context if row["participant_id"] in seats]
        result.append({"session_id": _text(session["session_id"], 160),
                       "source_digest": _digest({"messages": context, "events": events}),
                       "context": context, "public_offer_events": events, "ratings": ratings})
    return {"version": 1, "rubric_version": RUBRIC_VERSION, "rubric": RUBRIC,
            "anchors": ANCHORS, "direction": "Higher is better for every dimension.",
            "instructions": "Rate only observable public evidence. Use null when evidence is insufficient. Cite source IDs for every rated turn. Do not infer private truth.",
            "sessions": result}


def _validated_ratings(scorecard: Any, expected: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    if scorecard is None:
        return {}
    if not isinstance(scorecard, dict) or scorecard.get("version") != 1 or scorecard.get("rubric_version") != RUBRIC_VERSION:
        raise ValueError("Unknown scorecard or rubric version.")
    source_sessions = {session["session_id"]: session for session in expected["sessions"]}
    supplied = scorecard.get("sessions")
    if not isinstance(supplied, list):
        raise ValueError("Scorecard sessions must be an array.")
    ratings = {}
    seen_sessions = set()
    for session in supplied:
        if not isinstance(session, dict):
            raise ValueError("Invalid scorecard session.")
        session_id = session.get("session_id")
        source = source_sessions.get(session_id)
        if source is None or session_id in seen_sessions or source["source_digest"] != session.get("source_digest"):
            raise ValueError("Unknown, duplicate, or changed scorecard source.")
        supplied_digest = _digest({"messages": session.get("context"), "events": session.get("public_offer_events")})
        if supplied_digest != source["source_digest"]:
            raise ValueError("The scorecard context changed. Export a new scorecard.")
        seen_sessions.add(session_id)
        eligible = {rating["source_message_id"] for rating in source["ratings"]}
        known_sources = {row["source_message_id"] for row in source["context"]}
        known_sources.update(row["source_event_id"] for row in source["public_offer_events"])
        supplied_ratings = session.get("ratings")
        if not isinstance(supplied_ratings, list):
            raise ValueError("Ratings must be an array.")
        for rating in supplied_ratings:
            if not isinstance(rating, dict):
                raise ValueError("Invalid rating.")
            message_id = rating.get("source_message_id")
            key = (session_id, message_id)
            if message_id not in eligible or key in ratings:
                raise ValueError("Unknown or duplicate rating source.")
            dimensions = rating.get("dimensions")
            if not isinstance(dimensions, dict) or set(dimensions) != set(HUMAN_DIMENSIONS):
                raise ValueError("Expected all four human dimensions.")
            if any(value is not None and (type(value) is not int or not 0 <= value <= 4) for value in dimensions.values()):
                raise ValueError("Human ratings must be integers from 0 to 4 or null.")
            evidence = rating.get("evidence_source_ids", [])
            if not isinstance(evidence, list) or any(not isinstance(value, str) or value not in known_sources for value in evidence):
                raise ValueError("Unknown evidence source.")
            if any(value is not None for value in dimensions.values()):
                reviewer = rating.get("reviewer_id")
                if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100 or not evidence:
                    raise ValueError("Each rated turn requires reviewer_id and evidence_source_ids.")
            ratings[key] = rating
    return ratings


def analyze(artifact: Any, scorecard: Any = None) -> dict[str, Any]:
    sessions = _sessions(artifact)
    expected = export_scorecard(artifact)
    ratings = _validated_ratings(scorecard, expected)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = []
    for session in sessions:
        for seat in _seats(session):
            participant_id = seat["participant_id"]
            quality = build_dialogue_quality(session["messages"], session.get("events", []), npc_participant_ids=[participant_id])
            metadata = {key: seat.get(key, session.get(key)) for key in META_FIELDS}
            metadata["role"] = seat.get("role")
            metadata = {key: _text(value, 200) if isinstance(value, str)
                        else value if value is None or type(value) in {bool, int} else None
                        for key, value in metadata.items()}
            run_metadata = session.get("run_metadata")
            run_metadata = run_metadata if isinstance(run_metadata, dict) else {}
            config = {key: seat.get(key, session.get(key, run_metadata.get(key)))
                      for key in ("prompt_version", "seed", "max_turns", "configuration_id")}
            metadata["configuration_digest"] = _digest(config)
            source_ids = [message_source_id(message, index) for index, message in enumerate(session["messages"])
                          if message.get("participant_id") == participant_id]
            values: dict[str, list[int]] = {dimension: [] for dimension in HUMAN_DIMENSIONS}
            rated_turns = 0
            for source_id in source_ids:
                rating = ratings.get((session["session_id"], source_id))
                if rating is None:
                    continue
                dimensions = rating["dimensions"]
                rated_turns += int(any(value is not None for value in dimensions.values()))
                for dimension in HUMAN_DIMENSIONS:
                    if dimensions[dimension] is not None:
                        values[dimension].append(dimensions[dimension])
            quality["human_review"] = {
                "rubric_version": RUBRIC_VERSION, "status": "rated" if rated_turns else "unrated",
                "dimensions": {dimension: round(fmean(scores), 3) if scores else None for dimension, scores in values.items()},
                "dimension_samples": {dimension: len(scores) for dimension, scores in values.items()},
                "coverage": {"rated_turns": rated_turns, "eligible_turns": len(source_ids)},
            }
            row = {"session_id": _text(session["session_id"], 160), "participant_id": _text(participant_id, 160),
                   "metadata": metadata, "dialogue_quality": quality}
            rows.append(row)
            groups[json.dumps(metadata, sort_keys=True)].append(row)
    summaries = []
    for key, members in sorted(groups.items()):
        dimension_totals = Counter()
        dimension_counts: Counter[str] = Counter()
        latency_sum = latency_samples = fallback_count = fallback_observations = 0
        exact_repeats = question_repeats = evaluated_replies = rated_replies = 0
        for member in members:
            quality = member["dialogue_quality"]
            exact_repeats += quality["repetition"]["exact_repeat_count"]
            question_repeats += quality["repetition"]["question_repeat_count"]
            evaluated_replies += quality["turns"]["npc"]
            rendering = quality["rendering"]
            fallback_count += rendering["fallback_count"] or 0
            fallback_observations += rendering["fallback_observations"]
            latency = rendering["latency_ms"]
            latency_samples += latency["samples"]
            latency_sum += (latency["average"] or 0) * latency["samples"]
            human = quality["human_review"]
            rated_replies += human["coverage"]["rated_turns"]
            for dimension, score in human["dimensions"].items():
                count = human["dimension_samples"][dimension]
                dimension_counts[dimension] += count
                dimension_totals[dimension] += (score or 0) * count
        summaries.append({"metadata": json.loads(key), "sessions": len(members),
                          "evaluated_replies": evaluated_replies, "exact_repeat_count": exact_repeats,
                          "question_repeat_count": question_repeats,
                          "human_coverage": {"rated_turns": rated_replies, "eligible_turns": evaluated_replies},
                          "fallback_rate": round(fallback_count / fallback_observations, 4) if fallback_observations else None,
                          "fallback_observations": fallback_observations,
                          "average_latency_ms": round(latency_sum / latency_samples, 3) if latency_samples else None,
                          "latency_samples": latency_samples,
                          "human_dimensions": {dimension: round(dimension_totals[dimension] / dimension_counts[dimension], 3)
                                               if dimension_counts[dimension] else None for dimension in HUMAN_DIMENSIONS},
                          "human_dimension_samples": dict(dimension_counts)})
    return {"version": 1, "rubric_version": RUBRIC_VERSION, "offline": True,
            "limitations": ["Repetition flags are heuristics, not evidence of factual correctness.",
                            "Human ratings use only public context. Unrated dimensions stay null.",
                            "Compare groups only with matching scenario version, role, difficulty, and configuration.",
                            "Missing configuration metadata does not establish benchmark comparability.",
                            "External-agent generation telemetry is unavailable unless delivered renderer events exist."],
            "sessions": rows, "groups": summaries}


def _load(path: str) -> Any:
    source = Path(path)
    if source.stat().st_size > 20_000_000:
        raise ValueError("Input exceeds the 20 MB offline evaluation limit.")
    return json.loads(source.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON number.")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("export-scorecard", "analyze"))
    parser.add_argument("artifact", help="Public Admin Inspector detail JSON, or an object with sessions.")
    parser.add_argument("--scorecard", help="A completed offline human scorecard.")
    args = parser.parse_args(argv)
    try:
        artifact = _load(args.artifact)
        result = export_scorecard(artifact) if args.command == "export-scorecard" else analyze(artifact, _load(args.scorecard) if args.scorecard else None)
    except (ValueError, OSError, TypeError) as error:
        print(f"Dialogue evaluation failed: {type(error).__name__}. Check the input format and source references.", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
