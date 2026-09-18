"""Bounded public artifacts for the dialogue smoke harness.

The caller must authenticate and select the public Admin Inspector detail first.
This module does not turn private session state into a public projection.
It applies an additional field allowlist before a harness writes an artifact.
"""

from __future__ import annotations

import math
import re
from typing import Any

from backend.app.dialogue import NPC_SPEECH_ACTS, redact_untrusted_credentials
from backend.app.dialogue_quality import (
    FAILURE_REASONS,
    VALIDATION_FAILURES,
    build_dialogue_quality,
)


_PUBLIC_EVENTS = frozenset(
    {
        "session.created",
        "session.aborted",
        "session.expired",
        "session.walked_away",
        "offer.created",
        "offer.countered",
        "agreement.reached",
        "participant.question",
        "participant.inform",
        "participant.reject",
        "participant.withdraw",
        "participant.offer",
        "participant.counter_offer",
        "participant.accept",
        "clarification.required",
        "domain_transition.failed",
        "acceptance.confirmation_required",
        "acceptance.cancelled",
        "npc.intent.committed",
        "npc.utterance.delivered",
        "npc.opening_utterance.delivered",
    }
)
_REASON_CODES = frozenset(
    {
        "ambiguous_message",
        "ambiguous_numeric_reference",
        "numeric_answer_requires_unit",
        "numeric_answer_requires_term",
        "relative_change_requires_baseline",
        "ambiguous_relative_change",
        "currency_mismatch",
        "multiple_offer_candidates",
        "unscored_proposal",
        "conditional_confirmation",
        "ambiguous_confirmation",
        "ambiguous_agreement_scope",
        "conflicting_topic_directives",
        "clarification_limit_reached",
        "protocol_control_limit_reached",
        "offer_not_active",
        "offer_not_bindable",
        "max_rounds_reached",
        "hard_constraint_violation",
    }
)
_ACTIONS = frozenset(
    {
        "inform",
        "question",
        "offer",
        "counter_offer",
        "accept",
        "reject",
        "withdraw",
        "walk_away",
        "acceptance_intent",
        "confirm_acceptance",
        "cancel_acceptance",
    }
)
_STATUSES = frozenset(
    {
        "active",
        "agreement_reached",
        "aborted",
        "expired",
        "walked_away",
        "accepted",
        "rejected",
        "withdrawn",
        "superseded",
        "closed_by_termination",
    }
)
_PRIVATE_TERM_KEY = re.compile(
    r"(?:api_?key|token|password|credential|private|hidden|brief|review|state|internal|"
    r"request|prompt|raw|utility|batna|reservation|constraint)",
    re.IGNORECASE,
)
_TERM_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,99}")
_METADATA_TEXT = {
    "suite": 100,
    "case_id": 160,
    "provider": 100,
    "model": 200,
    "target_provider": 100,
    "target_model": 200,
    "configuration_id": 200,
    "prompt_version": 200,
}


def _text(value: Any, secrets: tuple[str, ...], limit: int = 200) -> str | None:
    if not isinstance(value, str):
        return None
    # A credential may straddle the truncation boundary. Redact it first.
    return redact_untrusted_credentials(value, *secrets)[:limit]


def _texts(source: dict, fields: dict[str, int], secrets: tuple[str, ...]) -> dict:
    result = {}
    for field, limit in fields.items():
        text = _text(source.get(field), secrets, limit)
        if text is not None:
            result[field] = text
    return result


def _integers(source: dict, fields: tuple[str, ...]) -> dict:
    return {
        field: source[field]
        for field in fields
        if type(source.get(field)) is int and 0 <= source[field] <= 2**63 - 1
    }


def _enum(source: dict, field: str, values: frozenset | set) -> dict:
    value = source.get(field)
    return {field: value} if isinstance(value, str) and value in values else {}


def _rows(source: dict, field: str, maximum: int) -> list[dict]:
    rows = source.get(field, [])
    if (
        not isinstance(rows, list)
        or len(rows) > maximum
        or not all(isinstance(row, dict) for row in rows)
    ):
        raise ValueError(f"Invalid or oversized public {field} array.")
    return rows


def _terms(value: Any, secrets: tuple[str, ...]) -> dict:
    if not isinstance(value, dict):
        return {}
    if len(value) > 32:
        raise ValueError("Public terms exceed the artifact bound.")
    result = {}
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or not _TERM_KEY.fullmatch(key)
            or _PRIVATE_TERM_KEY.search(key)
            or _text(key, secrets, 100) != key
        ):
            continue
        if isinstance(item, str):
            result[key] = _text(item, secrets, 1000)
        elif item is None or type(item) is bool:
            result[key] = item
        elif type(item) in {int, float} and abs(item) <= 10**18 and math.isfinite(item):
            result[key] = item
    return result


def _identifiers(value: Any, secrets: tuple[str, ...]) -> list[str]:
    if not isinstance(value, list) or len(value) > 32:
        return []
    return [safe for item in value if (safe := _text(item, secrets, 160)) is not None]


def _renderer(value: Any, secrets: tuple[str, ...]) -> dict:
    if not isinstance(value, dict):
        return {}
    result = _texts(value, {"provider": 100, "model": 200}, secrets)
    result.update(_enum(value, "mode", {"llm", "template"}))
    for field in ("fallback_used", "attempted_generation"):
        if type(value.get(field)) is bool:
            result[field] = value[field]
    for field, allowed in (
        ("failure_reason", FAILURE_REASONS),
        ("validation_failure", VALIDATION_FAILURES),
    ):
        result.update(_enum(value, field, allowed))
        if field in value and field not in result:
            # Never copy a provider exception or an arbitrary failure string.
            result[field] = (
                "other" if field == "validation_failure" and value[field] is not None else None
            )
    latency = value.get("latency_ms")
    result["latency_ms"] = (
        latency
        if type(latency) in {int, float} and 0 <= latency <= 86_400_000 and math.isfinite(latency)
        else None
    )
    return result


def _event(row: dict, secrets: tuple[str, ...]) -> dict | None:
    event_type = row.get("type")
    if not isinstance(event_type, str) or event_type not in _PUBLIC_EVENTS:
        return None
    result = _texts(row, {"event_id": 160, "participant_id": 160, "created_at": 100}, secrets)
    result.update(_integers(row, ("session_revision",)))
    result["type"] = event_type
    source = row.get("payload")
    source = source if isinstance(source, dict) else {}
    payload = _texts(
        source,
        {
            "offer_id": 160,
            "proposer_participant_id": 160,
            "next_actor": 160,
            "render_id": 160,
            "requested_term_id": 100,
            "role": 100,
            "expected_currency": 3,
            "detected_currency": 3,
        },
        secrets,
    )
    payload.update(_integers(source, ("offer_revision", "max_rounds", "protocol_control_count")))
    payload.update(_enum(source, "status", _STATUSES))
    payload.update(_enum(source, "action", _ACTIONS))
    payload.update(_enum(source, "speech_act", NPC_SPEECH_ACTS))
    payload.update(_enum(source, "opening_kind", {"opening_offer", "opening_position"}))
    payload.update(_enum(source, "reason_code", _REASON_CODES))
    payload.update(_enum(source, "error", _REASON_CODES))
    payload.update(_enum(source, "reason", _REASON_CODES))
    if type(source.get("substantive")) is bool:
        payload["substantive"] = source["substantive"]
    for field in ("terms", "approved_terms"):
        if isinstance(source.get(field), dict):
            payload[field] = _terms(source[field], secrets)
    for field in ("unresolved_required_terms", "disclosed_reason_ids", "provided_currencies"):
        if isinstance(source.get(field), list):
            payload[field] = _identifiers(source[field], secrets)
    if isinstance(source.get("dialogue_renderer"), dict):
        payload["dialogue_renderer"] = _renderer(source["dialogue_renderer"], secrets)
    result["payload"] = payload
    return result


def build_public_artifact_session(
    admin_detail: dict,
    *,
    metadata: dict,
    known_secrets: tuple[str, ...] = (),
) -> dict:
    """Export one public session for ``benchmarks.dialogue_quality``.

    ``provider`` and ``model`` in metadata identify the actual renderer.
    ``target_provider`` and ``target_model`` identify the intended live target.
    The two identities remain separate during offline fixture execution.
    Private fields and supplied quality ratings are never copied.
    """
    if not isinstance(admin_detail, dict) or not isinstance(metadata, dict):
        raise ValueError("Public detail and metadata must be objects.")
    if (
        not isinstance(known_secrets, tuple)
        or len(known_secrets) > 100
        or any(not isinstance(secret, str) for secret in known_secrets)
    ):
        raise ValueError("Known secrets must be a bounded tuple of strings.")
    session_id = _text(admin_detail.get("session_id"), known_secrets, 160)
    if not session_id:
        raise ValueError("Public session detail requires session_id.")
    result = _texts(
        admin_detail,
        {
            "scenario_id": 160,
            "scenario_title": 500,
            "language": 10,
            "currency": 3,
            "next_actor": 160,
            "created_at": 100,
            "updated_at": 100,
        },
        known_secrets,
    )
    result["session_id"] = session_id
    result.update(
        _integers(admin_detail, ("scenario_version", "revision", "round", "substantive_turn_count"))
    )
    for field, choices in (
        ("status", _STATUSES),
        ("difficulty", {"guided", "easy", "normal", "expert"}),
        ("run_mode", {"training", "benchmark"}),
    ):
        result.update(_enum(admin_detail, field, choices))
    if type(admin_detail.get("hints_enabled")) is bool:
        result["hints_enabled"] = admin_detail["hints_enabled"]

    run_metadata = _texts(metadata, _METADATA_TEXT, known_secrets)
    run_metadata.update(_integers(metadata, ("seed", "max_turns")))
    if "execution_mode" in metadata:
        if metadata["execution_mode"] not in ("offline", "live"):
            raise ValueError("Artifact execution_mode must be offline or live.")
        run_metadata["execution_mode"] = metadata["execution_mode"]
    result["run_metadata"] = run_metadata
    for field in ("provider", "model"):
        if field in run_metadata:
            result[field] = run_metadata[field]

    participants = []
    for row in _rows(admin_detail, "participants", 8):
        seat = _texts(
            row,
            {
                "participant_id": 160,
                "role": 100,
                "provider": 100,
                "model": 200,
                "prompt_version": 200,
            },
            known_secrets,
        )
        seat.update(
            _enum(
                row, "controller", {"human", "built_in_npc", "external_agent", "scripted", "replay"}
            )
        )
        if seat.get("controller") == "built_in_npc":
            for field in ("provider", "model", "prompt_version"):
                if field in run_metadata:
                    seat[field] = run_metadata[field]
        if not seat.get("participant_id"):
            raise ValueError("Public participants require participant_id.")
        participants.append(seat)
    if len({seat["participant_id"] for seat in participants}) != len(participants):
        raise ValueError("Duplicate public participant_id.")
    result["participants"] = participants

    messages = []
    for row in _rows(admin_detail, "messages", 1000):
        message = _texts(
            row,
            {
                "message_id": 160,
                "participant_id": 160,
                "role": 100,
                "content": 10000,
                "language": 10,
                "created_at": 100,
            },
            known_secrets,
        )
        if type(row.get("id")) is int:
            message.update(_integers(row, ("id",)))
        elif isinstance(row.get("id"), str):
            message["id"] = _text(row["id"], known_secrets, 160)
        message.update(_integers(row, ("session_revision",)))
        messages.append(message)
    result["messages"] = messages
    result["events"] = [
        event
        for row in _rows(admin_detail, "events", 5000)
        if (event := _event(row, known_secrets)) is not None
    ]
    offers = []
    for row in _rows(admin_detail, "offers", 1000):
        offer = _texts(row, {"offer_id": 160, "proposer_participant_id": 160}, known_secrets)
        offer.update(_integers(row, ("offer_revision", "created_session_revision")))
        offer.update(_enum(row, "status", _STATUSES))
        offer["terms"] = _terms(row.get("terms"), known_secrets)
        offers.append(offer)
    result["offers"] = offers
    # Recompute, rather than copying a nested object which may contain private data.
    result["dialogue_quality"] = build_dialogue_quality(
        messages,
        result["events"],
        npc_participant_ids=[
            seat["participant_id"]
            for seat in participants
            if seat.get("controller") == "built_in_npc"
        ],
    )
    return result
