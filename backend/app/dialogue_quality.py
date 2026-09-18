"""Public transcript diagnostics. These heuristics do not measure negotiation success."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from statistics import fmean
from typing import Any


RUBRIC_VERSION = "dialogue-human-v1"
HUMAN_DIMENSIONS = ("relevance", "continuity", "attribution", "unsupported_claims")
FAILURE_REASONS = frozenset({
    "provider_failure", "output_invalid", "renderer_failure", "restart_recovery",
})
VALIDATION_FAILURES = frozenset({
    "format", "speech_act", "unauthorized_claim", "repetition", "grounding", "language", "credential",
    "invalid_json", "invalid_shape", "invalid_text", "invalid_language", "unsafe_structure",
    "credential_leak", "numeric_reference", "numeric_output", "unsupported_commitment",
    "missing_reason", "grounding_rejected", "grounding_invalid", "quote_slot_invalid",
    "quote_slot_unbound", "quote_slot_repeated", "unknown_slot", "invalid_slot",
    "repeated_slot", "unbound_slot", "output_invalid",
})


def message_source_id(message: Mapping[str, Any], ordinal: int) -> str:
    """Provide a stable reference even for historical transcripts without message IDs."""
    for field in ("message_id", "id"):
        value = message.get(field)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            if re.fullmatch(r"[a-zA-Z0-9_:.-]{1,160}", str(value)):
                return str(value)
    participant = str(message.get("participant_id", "unknown"))
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", participant):
        participant = "unknown"
    revision = message.get("session_revision", 0)
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        revision = 0
    return f"msg:{participant}:{revision}:{ordinal}"


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _number(value: Any) -> float | None:
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        numeric = float(value)
        if math.isfinite(numeric) and 0 <= numeric <= 86_400_000:
            return numeric
    return None


def latency_summary(values: Sequence[float]) -> dict[str, int | float | None]:
    """Use the nearest-rank percentile. Never impute missing measurements."""
    return {
        "samples": len(values),
        "average": round(fmean(values), 3) if values else None,
        "p95": round(sorted(values)[math.ceil(len(values) * 0.95) - 1], 3) if values else None,
    }


def build_dialogue_quality(
    messages: Iterable[Mapping[str, Any]],
    events: Iterable[Mapping[str, Any]],
    *,
    npc_participant_ids: Iterable[str],
) -> dict[str, Any]:
    """Inspect already-redacted public rows from exactly one session.

    The caller authenticates the session and selects public payloads. No input text,
    arbitrary payload, provider error, or private event is copied to the result.
    Repetition means case/whitespace-normalized identity per NPC, not semantic identity.
    """
    npc_ids = frozenset(npc_participant_ids)
    rows = list(messages)
    npc_turns = 0
    seen_text: dict[tuple[str, str], str] = {}
    seen_questions: dict[tuple[str, str], str] = {}
    flags: list[dict[str, str]] = []
    exact_repeats = question_repeats = 0
    for index, message in enumerate(rows):
        participant = str(message.get("participant_id", ""))
        if participant not in npc_ids:
            continue
        npc_turns += 1
        source = message_source_id(message, index)
        content = message.get("content", "")
        if not isinstance(content, str):
            continue
        normalized = _normalized(content)
        key = (participant, normalized)
        if normalized and key in seen_text:
            exact_repeats += 1
            flags.append({"kind": "exact_repeat", "source_message_id": source,
                          "repeats_source_message_id": seen_text[key]})
        elif normalized:
            seen_text[key] = source
        # A question needs a question mark. This deliberately avoids language inference.
        for question in re.findall(r"[^.!?]+\?", content):
            question_key = (participant, _normalized(question))
            if question_key in seen_questions:
                question_repeats += 1
                flags.append({"kind": "question_repeat", "source_message_id": source,
                              "repeats_source_message_id": seen_questions[question_key]})
            else:
                seen_questions[question_key] = source

    delivered = telemetry_turns = attempts = fallback_count = fallback_observations = 0
    failures: Counter[str] = Counter()
    validation: Counter[str] = Counter()
    latencies: list[float] = []
    seen_events: set[str] = set()
    for event in events:
        if event.get("type") != "npc.utterance.delivered" or event.get("participant_id") not in npc_ids:
            continue
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            if event_id in seen_events:
                continue
            seen_events.add(event_id)
        delivered += 1
        payload = event.get("payload")
        metadata = payload.get("dialogue_renderer") if isinstance(payload, Mapping) else None
        if not isinstance(metadata, Mapping):
            continue
        telemetry_turns += 1
        fallback = metadata.get("fallback_used")
        attempted = metadata.get("attempted_generation")
        if not isinstance(attempted, bool):
            attempted = metadata.get("mode") == "llm" or fallback is True
        if attempted:
            attempts += 1
            if isinstance(fallback, bool):
                fallback_observations += 1
                fallback_count += int(fallback)
            latency = _number(metadata.get("latency_ms"))
            if latency is not None:
                latencies.append(latency)
        failure = metadata.get("failure_reason")
        if isinstance(failure, str) and failure in FAILURE_REASONS:
            failures[failure] += 1
        code = metadata.get("validation_failure")
        if isinstance(code, str) and code in VALIDATION_FAILURES:
            validation[code] += 1
        elif code is not None:
            validation["other"] += 1

    return {
        "version": 1,
        "heuristic_only": True,
        "turns": {"total": len(rows), "player": len(rows) - npc_turns, "npc": npc_turns},
        "repetition": {
            "exact_repeat_count": exact_repeats,
            "question_repeat_count": question_repeats,
            "flags": flags[:100],
            "flags_truncated": len(flags) > 100,
        },
        "rendering": {
            "delivered_turns": delivered,
            "telemetry_turns": telemetry_turns,
            "generation_attempts": attempts,
            "fallback_observations": fallback_observations,
            "fallback_count": fallback_count if fallback_observations else None,
            "fallback_rate": round(fallback_count / fallback_observations, 4) if fallback_observations else None,
            "failure_counts": dict(sorted(failures.items())),
            "validation_failures": dict(sorted(validation.items())),
            "latency_ms": latency_summary(latencies),
        },
        "human_review": {
            "rubric_version": RUBRIC_VERSION,
            "status": "unrated",
            "dimensions": dict.fromkeys(HUMAN_DIMENSIONS),
            "coverage": {"rated_turns": 0, "eligible_turns": npc_turns},
        },
    }
