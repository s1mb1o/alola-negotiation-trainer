"""Replay a Markdown transcript through the public Player API."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Literal, Mapping

from .api import ApiError, NegotiationApiClient, redact_secrets, response_revision, response_status
from .orchestrator import (
    TERMINAL_STATUSES,
    extract_participant_credentials,
    extract_participant_roles,
)


PlaybackMode = Literal["exact", "npc-comparison"]

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_BLOCK_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_SPEAKER_SUFFIXES = (" —", " –", " -", ":")


@dataclass(frozen=True, slots=True)
class TranscriptTurn:
    source_turn: int
    heading: str
    actor: Literal["player", "npc"]
    role: str
    message: str


def _normalized_heading(value: str) -> str:
    return " ".join(value.casefold().split())


def _heading_matches(heading: str, label: str) -> bool:
    normalized = _normalized_heading(heading)
    expected = _normalized_heading(label)
    return normalized == expected or any(
        normalized.startswith(expected + suffix) for suffix in _SPEAKER_SUFFIXES
    )


def _trim_blank_lines(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def parse_markdown_transcript(
    text: str,
    *,
    player_heading: str,
    npc_heading: str,
    player_role: str,
    npc_role: str,
) -> list[TranscriptTurn]:
    """Extract documented speaker sections and their block-quoted messages."""

    if _normalized_heading(player_heading) == _normalized_heading(npc_heading):
        raise ValueError("Player and NPC headings must differ")
    if player_role == npc_role:
        raise ValueError("Player and NPC roles must differ")

    turns: list[TranscriptTurn] = []
    current_heading: str | None = None
    current_actor: Literal["player", "npc"] | None = None
    current_role: str | None = None
    quoted_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_actor, current_role, quoted_lines
        content = _trim_blank_lines(quoted_lines)
        if current_heading is not None and current_actor is not None and content:
            turns.append(
                TranscriptTurn(
                    source_turn=len(turns) + 1,
                    heading=current_heading,
                    actor=current_actor,
                    role=str(current_role),
                    message="\n".join(content),
                )
            )
        current_heading = None
        current_actor = None
        current_role = None
        quoted_lines = []

    for raw_line in text.splitlines():
        heading_match = _HEADING.match(raw_line)
        if heading_match:
            flush()
            if len(heading_match.group(1)) != 3:
                continue
            heading = heading_match.group(2).strip()
            player_match = _heading_matches(heading, player_heading)
            npc_match = _heading_matches(heading, npc_heading)
            if player_match and npc_match:
                raise ValueError(f"Speaker heading {heading!r} matches both configured labels")
            if player_match:
                current_heading = heading
                current_actor = "player"
                current_role = player_role
            elif npc_match:
                current_heading = heading
                current_actor = "npc"
                current_role = npc_role
            continue

        quote_match = _BLOCK_QUOTE.match(raw_line)
        if current_actor is not None and quote_match:
            quoted_lines.append(quote_match.group(1).rstrip())

    flush()
    if not turns:
        raise ValueError("Transcript contains no messages for the configured speaker headings")
    if not any(turn.actor == "player" for turn in turns):
        raise ValueError("Transcript contains no player messages")
    return turns


def load_markdown_transcript(
    path: str | Path,
    *,
    player_heading: str,
    npc_heading: str,
    player_role: str,
    npc_role: str,
) -> list[TranscriptTurn]:
    source = Path(path).expanduser().resolve()
    return parse_markdown_transcript(
        source.read_text(encoding="utf-8"),
        player_heading=player_heading,
        npc_heading=npc_heading,
        player_role=player_role,
        npc_role=npc_role,
    )


def _role_for_actor(
    actor: Any, participant_roles: Mapping[str, str], configured_roles: set[str]
) -> str | None:
    if actor is None:
        return None
    if not isinstance(actor, str):
        raise ApiError("Session returned an invalid next_actor")
    if actor in configured_roles:
        return actor
    mapped = participant_roles.get(actor)
    if mapped in configured_roles:
        return mapped
    for role in configured_roles:
        if actor == f"participant_{role}" or actor.endswith(f"_{role}"):
            return role
    raise ApiError(f"Cannot map next_actor {actor!r} to a configured role")


def _list_from_history(history: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(history, Mapping):
        return []
    value = history.get(key)
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _response_projection(
    response: Mapping[str, Any], participant_roles: Mapping[str, str], roles: set[str]
) -> dict[str, Any]:
    projection_keys = (
        "result",
        "revision",
        "round",
        "substantive_turn_count",
        "status",
        "next_actor",
        "clarification",
        "confirmation_kind",
        "pending_confirmation",
        "pending_offer_publication",
        "committed_actions",
    )
    projected = {key: response[key] for key in projection_keys if key in response}
    projected["next_role"] = _role_for_actor(response.get("next_actor"), participant_roles, roles)
    observation = response.get("observation")
    if isinstance(observation, Mapping):
        public_keys = (
            "current_public_terms",
            "unresolved_required_terms",
            "active_offers",
            "preliminary_proposals",
        )
        projected["public_state"] = {
            key: observation[key] for key in public_keys if key in observation
        }
    return projected


def _error_projection(exc: ApiError) -> dict[str, Any]:
    return redact_secrets(
        {
            "message": exc.message,
            "status": exc.status,
            "code": exc.code,
            "error": exc.error,
            "details": exc.details,
        }
    )


def _comparison(engine_messages: list[dict[str, Any]], recorded_message: str) -> dict[str, Any]:
    texts = [str(item.get("content", "")) for item in engine_messages]
    normalized_recorded = " ".join(recorded_message.split())
    return {
        "engine_messages": engine_messages,
        "exact_text_match": any(" ".join(text.split()) == normalized_recorded for text in texts),
    }


def run_transcript_playback(
    api: NegotiationApiClient,
    *,
    source: str | Path,
    turns: list[TranscriptTurn],
    mode: PlaybackMode,
    scenario_id: str,
    scenario_version: int,
    language: str,
    player_role: str,
    npc_role: str,
    finalize_for_review: bool = False,
    admin_token: str | None = None,
) -> dict[str, Any]:
    """Create a fresh session and process the supplied source turns."""

    if mode not in {"exact", "npc-comparison"}:
        raise ValueError(f"Unsupported transcript playback mode: {mode}")
    if player_role == npc_role:
        raise ValueError("Player and NPC roles must differ")
    if not turns:
        raise ValueError("Transcript playback requires at least one turn")
    if finalize_for_review and not admin_token:
        raise ValueError("Final review requires NEGOTIATION_ADMIN_TOKEN")

    controllers = (
        {player_role: "scripted_bot", npc_role: "scripted_bot"}
        if mode == "exact"
        else {player_role: "human", npc_role: "built_in_npc"}
    )
    created = api.create_session(
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        language=language,
        participants=[
            {"role": player_role, "controller": controllers[player_role]},
            {"role": npc_role, "controller": controllers[npc_role]},
        ],
        difficulty="normal",
        hints_enabled=False,
        run_mode="training",
    )
    session_id = str(created["session_id"])
    credentials = extract_participant_credentials(created)
    required_credentials = {player_role, npc_role} if mode == "exact" else {player_role}
    missing_credentials = sorted(role for role in required_credentials if not credentials.get(role))
    if missing_credentials:
        raise ApiError(
            "Session creation did not deliver credentials for: " + ", ".join(missing_credentials)
        )

    participant_roles = extract_participant_roles(created)
    roles = {player_role, npc_role}
    current: Mapping[str, Any] = created
    report_turns: list[dict[str, Any]] = []
    divergence: dict[str, Any] | None = None
    submitted_count = 0
    opening_reference_consumed = False

    player_api = api.with_participant_token(credentials[player_role])
    initial_history = player_api.history(session_id)
    pending_engine_npc_messages = [
        item
        for item in _list_from_history(initial_history, "messages")
        if item.get("role") == npc_role
    ]

    for turn in turns:
        expected_role = _role_for_actor(current.get("next_actor"), participant_roles, roles)
        base_record: dict[str, Any] = {
            "source_turn": turn.source_turn,
            "heading": turn.heading,
            "actor": turn.actor,
            "role": turn.role,
            "message": turn.message,
        }

        if mode == "npc-comparison" and turn.actor == "npc":
            base_record["action"] = "reference_only"
            base_record["comparison"] = _comparison(pending_engine_npc_messages, turn.message)
            pending_engine_npc_messages = []
            report_turns.append(base_record)
            continue

        if (
            mode == "exact"
            and submitted_count == 0
            and not opening_reference_consumed
            and turn.source_turn == 1
            and turn.actor == "npc"
            and expected_role == player_role
        ):
            base_record["action"] = "opening_reference"
            base_record["reason"] = "scenario_opening_already_initialized"
            base_record["engine"] = _response_projection(current, participant_roles, roles)
            report_turns.append(base_record)
            opening_reference_consumed = True
            continue

        if response_status(current) in TERMINAL_STATUSES:
            divergence = {
                "kind": "session_terminal",
                "source_turn": turn.source_turn,
                "recorded_role": turn.role,
                "session_status": response_status(current),
            }
            base_record["action"] = "not_submitted"
            base_record["divergence"] = divergence
            report_turns.append(base_record)
            break

        if turn.role != expected_role:
            divergence = {
                "kind": "turn_mismatch",
                "source_turn": turn.source_turn,
                "recorded_role": turn.role,
                "expected_role": expected_role,
                "revision": response_revision(current),
            }
            base_record["action"] = "not_submitted"
            base_record["divergence"] = divergence
            report_turns.append(base_record)
            break

        token = credentials.get(turn.role)
        if not token:
            raise ApiError(f"No participant credential is available for role {turn.role!r}")
        participant_api = api.with_participant_token(token)
        before_history = participant_api.history(session_id)
        before_messages = _list_from_history(before_history, "messages")
        before_events = _list_from_history(before_history, "events")
        before_revision = response_revision(current)
        try:
            submitted = participant_api.submit_message(
                session_id,
                turn.message,
                expected_revision=before_revision,
            )
        except ApiError as exc:
            divergence = {
                "kind": "submission_rejected",
                "source_turn": turn.source_turn,
                "recorded_role": turn.role,
                "revision": before_revision,
                "api_error": _error_projection(exc),
            }
            base_record["action"] = "rejected"
            base_record["divergence"] = divergence
            report_turns.append(base_record)
            break

        after_history = participant_api.history(session_id)
        after_messages = _list_from_history(after_history, "messages")
        after_events = _list_from_history(after_history, "events")
        new_messages = after_messages[len(before_messages) :]
        new_events = after_events[len(before_events) :]
        base_record["action"] = "submitted"
        base_record["engine"] = {
            "before_revision": before_revision,
            "after_revision": response_revision(submitted),
            **_response_projection(submitted, participant_roles, roles),
            "new_messages": new_messages,
            "new_events": new_events,
        }
        report_turns.append(base_record)
        submitted_count += 1
        current = submitted

        if mode == "npc-comparison":
            pending_engine_npc_messages.extend(
                item for item in new_messages if item.get("role") == npc_role
            )

    finalization: dict[str, Any] | None = None
    if finalize_for_review and response_status(current) not in TERMINAL_STATUSES:
        finalization = api.close_session(
            session_id,
            expected_revision=response_revision(current),
            reason="Transcript playback source exhausted.",
            admin_token=str(admin_token),
        )
        current = finalization

    final_history = player_api.history(session_id)
    review = (
        player_api.review(session_id) if response_status(current) in TERMINAL_STATUSES else None
    )
    report: dict[str, Any] = {
        "version": 1,
        "mode": mode,
        "source": str(Path(source).expanduser().resolve()),
        "scenario_id": scenario_id,
        "scenario_version": scenario_version,
        "language": language,
        "player_role": player_role,
        "npc_role": npc_role,
        "session_id": session_id,
        "playback_status": "diverged" if divergence is not None else "completed",
        "session_status": response_status(current),
        "revision": response_revision(current),
        "submitted_turns": submitted_count,
        "turns": report_turns,
        "history": final_history,
    }
    if finalization is not None:
        report["finalization"] = finalization
    if review is not None:
        report["review"] = review
    if divergence is not None:
        report["divergence"] = divergence
    if mode == "npc-comparison" and pending_engine_npc_messages:
        report["unmatched_engine_npc_messages"] = pending_engine_npc_messages
    return redact_secrets(report, tuple(credentials.values()))


def _markdown_quote(value: str) -> list[str]:
    lines = value.splitlines() or [""]
    return [">" if not line else f"> {line}" for line in lines]


def _display_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_player_markdown(report: Mapping[str, Any]) -> str:
    """Render the actor-safe transcript and review as a player-facing Markdown report."""

    player_role = str(report.get("player_role", "player"))
    npc_role = str(report.get("npc_role", "npc"))
    lines = [
        "# Сессия глазами игрока",
        "",
        f"- Сессия: `{report.get('session_id', '—')}`",
        f"- Сценарий: `{report.get('scenario_id', '—')}@{report.get('scenario_version', '—')}`",
        f"- Режим: `{report.get('mode', '—')}`",
        f"- Статус воспроизведения: `{report.get('playback_status', '—')}`",
        f"- Статус сессии: `{report.get('session_status', '—')}`",
        "",
        "## Диалог",
        "",
    ]
    history = report.get("history")
    messages = history.get("messages", []) if isinstance(history, Mapping) else []
    if not isinstance(messages, list) or not messages:
        lines.extend(["Сообщений нет.", ""])
    else:
        for message in messages:
            if not isinstance(message, Mapping):
                continue
            role = str(message.get("role", "unknown"))
            speaker = "Игрок" if role == player_role else "NPC" if role == npc_role else "Участник"
            lines.extend(
                [
                    f"### {speaker} — `{role}`",
                    "",
                    *_markdown_quote(str(message.get("content", ""))),
                    "",
                ]
            )

    lines.extend(["## Реакции системы", ""])
    turns = report.get("turns")
    submitted = (
        [item for item in turns if isinstance(item, Mapping) and item.get("action") == "submitted"]
        if isinstance(turns, list)
        else []
    )
    if not submitted:
        lines.extend(["Отправленных исходных реплик нет.", ""])
    for item in submitted:
        engine = item.get("engine") if isinstance(item.get("engine"), Mapping) else {}
        lines.extend(
            [
                f"### Исходная реплика {item.get('source_turn', '—')}",
                "",
                f"- Роль: `{item.get('role', '—')}`",
                f"- Результат: `{engine.get('result', '—')}`",
                f"- Ревизия: `{engine.get('before_revision', '—')} → {engine.get('after_revision', '—')}`",
                f"- Следующая роль: `{engine.get('next_role', '—')}`",
            ]
        )
        clarification = engine.get("clarification")
        if isinstance(clarification, Mapping):
            lines.append(f"- Уточнение: {_display_value(clarification.get('question'))}")
        lines.append("")

    lines.extend(["## Итоговый разбор", ""])
    review = report.get("review")
    if not isinstance(review, Mapping):
        lines.extend(["Разбор недоступен. Сессия не завершена.", ""])
        return "\n".join(lines).rstrip() + "\n"

    outcome = review.get("outcome") if isinstance(review.get("outcome"), Mapping) else {}
    scores = review.get("scores") if isinstance(review.get("scores"), Mapping) else {}
    lines.extend(
        [
            "### Результат",
            "",
            f"- Соглашение: {_display_value(outcome.get('agreement'))}",
            f"- Причина завершения: `{outcome.get('termination_reason', '—')}`",
            f"- Полезность игрока: {_display_value(outcome.get('participant_utility'))}",
            f"- Оценка результата: {_display_value(scores.get('outcome_score', review.get('outcome_score')))}",
            f"- Оценка навыков: {_display_value(scores.get('skill_score', review.get('skill_score')))}",
            "",
        ]
    )
    skills = review.get("skills")
    if isinstance(skills, Mapping) and skills:
        lines.extend(["### Навыки", "", "| Навык | Оценка |", "| --- | ---: |"])
        for skill, score in skills.items():
            lines.append(f"| `{skill}` | {_display_value(score)} |")
        lines.append("")

    moments = review.get("key_moments")
    if isinstance(moments, list) and moments:
        lines.extend(["### Ключевые моменты", ""])
        for moment in moments:
            if not isinstance(moment, Mapping):
                continue
            lines.append(f"- **{moment.get('title', 'Событие')}.** {moment.get('summary', '')}")
            if moment.get("detail"):
                lines.append(f"  {moment['detail']}")
        lines.append("")

    recommendations = review.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        lines.extend(["### Рекомендации", ""])
        for recommendation in recommendations:
            if isinstance(recommendation, Mapping):
                lines.append(
                    f"- **{recommendation.get('skill', 'practice')}:** "
                    f"{recommendation.get('text', '')}"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
