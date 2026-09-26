"""Deterministic search over versioned, non-authoritative reply examples."""

from __future__ import annotations

from difflib import SequenceMatcher
from functools import lru_cache
import json
import logging
from pathlib import Path
import re
from typing import Any

from .dialogue import RetrievedReplyExample


LIBRARY_VERSION = "reply_examples_v2"
LIBRARY_PATH = Path(__file__).resolve().parents[1] / "data" / "reply_examples_v2.json"
MAX_RETRIEVED_EXAMPLES = 4
MAX_QUERY_CHARACTERS = 500
MAX_QUERY_FRAGMENTS = 8
_LOGGER = logging.getLogger(__name__)
_WORD = re.compile(r"[a-zа-яё]+", re.IGNORECASE)
_STOPWORDS = {
    "а", "в", "вы", "да", "для", "и", "как", "можно", "мы", "на", "о", "по", "с",
    "такая", "такой", "что", "это", "я", "can", "do", "i", "is", "let", "me", "the",
    "to", "we", "you", "your",
}


def _tokens(value: str) -> set[str]:
    result: set[str] = set()
    for raw in _WORD.findall(value.casefold().replace("ё", "е")):
        if raw in _STOPWORDS:
            continue
        if raw.startswith(("цен", "стоим", "тариф", "price", "cost", "rate")):
            result.add("price")
        elif raw.startswith(("достав", "постав", "срок", "delivery", "ship", "deadline")):
            result.add("delivery")
        elif raw.startswith(("предоплат", "аванс", "оплат", "prepay", "advance", "payment")):
            result.add("payment")
        else:
            result.add(raw[:6])
    return result


def _similarity(player_message: str, pattern: str) -> float:
    left, right = _tokens(player_message[:500]), _tokens(pattern)
    if not left or not right or not left.intersection(right):
        return 0.0
    overlap = 2 * len(left.intersection(right)) / (len(left) + len(right))
    surface = SequenceMatcher(None, player_message.casefold()[:500], pattern.casefold()).ratio()
    return 0.75 * overlap + 0.25 * surface


def _query_fragments(player_message: str) -> tuple[str, ...]:
    bounded = player_message[:MAX_QUERY_CHARACTERS]
    fragments = re.split(r"[.!?;\n]+", bounded)[:MAX_QUERY_FRAGMENTS]
    return (bounded, *(part.strip() for part in fragments if part.strip()))


@lru_cache(maxsize=1)
def _library() -> tuple[dict[str, Any], ...]:
    try:
        raw = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    if not isinstance(raw, dict) or raw.get("version") != LIBRARY_VERSION:
        raise ValueError("Reply example library version is invalid")
    entries = raw.get("examples")
    if not isinstance(entries, list) or len(entries) > 100:
        raise ValueError("Reply example library exceeds limits")
    seen: set[str] = set()
    checked: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or not {
            "id", "scenario_id", "npc_role", "language", "speech_act", "player_message", "replies"
        }.issubset(entry) or set(entry) - {
            "id", "scenario_id", "npc_role", "language", "speech_act", "player_message",
            "replies", "focused_term_id", "required_reason_id", "supply_action",
            "player_message_variants", "required_reason_ids", "required_training_context",
        }:
            raise ValueError("Reply example entry has invalid fields")
        if any(
            not isinstance(entry[key], str) or not entry[key]
            for key in ("id", "scenario_id", "npc_role", "language", "speech_act", "player_message")
        ) or any(
            not isinstance(entry.get(key), str) or not entry[key]
            for key in ("focused_term_id", "required_reason_id", "supply_action")
            if key in entry
        ):
            raise ValueError("Reply example metadata is invalid")
        if entry["id"] in seen or entry["npc_role"] not in {"buyer", "seller"}:
            raise ValueError("Reply example identity is invalid")
        seen.add(entry["id"])
        if entry["language"] not in {"ru", "en"} or not isinstance(entry["replies"], list) or not 2 <= len(entry["replies"]) <= 4:
            raise ValueError("Reply example variants are invalid")
        variants = entry.get("player_message_variants", [])
        if not isinstance(variants, list) or len(variants) > 4:
            raise ValueError("Reply example query variants are invalid")
        reason_ids = entry.get("required_reason_ids", [])
        if (
            not isinstance(reason_ids, list) or len(reason_ids) > 2
            or any(not isinstance(item, str) or not item for item in reason_ids)
            or len(set(reason_ids)) != len(reason_ids)
            or ("required_reason_ids" in entry and "required_reason_id" in entry)
        ):
            raise ValueError("Reply example reason gates are invalid")
        required_context = entry.get("required_training_context", {})
        if (
            not isinstance(required_context, dict)
            or set(required_context) - {"personal_fact", "relationship"}
            or any(not isinstance(value, str) or not 1 <= len(value) <= 1000
                   for value in required_context.values())
        ):
            raise ValueError("Reply example training gates are invalid")
        for index, reply in enumerate(entry["replies"], 1):
            RetrievedReplyExample(
                LIBRARY_VERSION, f"{entry['id']}_{index}", entry["player_message"], reply
            )
        for pattern in variants:
            RetrievedReplyExample(LIBRARY_VERSION, entry["id"], pattern, entry["replies"][0])
        checked.append(entry)
    return tuple(checked)


def retrieve_reply_examples(
    *,
    scenario_id: str,
    npc_role: str,
    language: str,
    speech_act: str,
    player_message: str,
    focused_term_ids: tuple[str, ...] = (),
    approved_reasons: tuple[tuple[str, str], ...] = (),
    supply_action: str | None = None,
    training_context: dict[str, str] | None = None,
) -> tuple[RetrievedReplyExample, ...]:
    """Return up to four matching wording examples without changing authority."""

    if not player_message.strip():
        return ()
    approved = dict(approved_reasons)
    context = training_context or {}
    fragments = _query_fragments(player_message)
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    try:
        library = _library()
    except (OSError, ValueError, TypeError) as exc:
        _LOGGER.warning("Prepared reply library unavailable: %s", exc)
        return ()
    for entry in library:
        if (
            entry["scenario_id"] != scenario_id
            or entry["npc_role"] != npc_role
            or entry["language"] != language
            or entry["speech_act"] != speech_act
            or entry.get("supply_action") != supply_action
        ):
            continue
        if entry.get("focused_term_id") and entry["focused_term_id"] not in focused_term_ids:
            continue
        reason_ids = entry.get("required_reason_ids", [])
        if entry.get("required_reason_id"):
            reason_ids = [entry["required_reason_id"]]
        if any(
            reason_id not in approved or not approved[reason_id]
            or any(approved[reason_id] not in reply for reply in entry["replies"])
            for reason_id in reason_ids
        ):
            continue
        if any(context.get(key) != value
               for key, value in entry.get("required_training_context", {}).items()):
            continue
        patterns = (entry["player_message"], *entry.get("player_message_variants", []))
        score = max(_similarity(fragment, pattern) for fragment in fragments for pattern in patterns)
        if score >= 0.42:
            ranked.append((score, entry["id"], entry))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected: list[RetrievedReplyExample] = []
    seen_replies: set[str] = set()
    for index in range(4):
        for _score, _id, entry in ranked:
            if index >= len(entry["replies"]):
                continue
            reply = entry["replies"][index]
            if reply in seen_replies:
                continue
            seen_replies.add(reply)
            selected.append(
                RetrievedReplyExample(
                    LIBRARY_VERSION, f"{entry['id']}_{index + 1}", entry["player_message"], reply
                )
            )
            if len(selected) == MAX_RETRIEVED_EXAMPLES:
                return tuple(selected)
    return tuple(selected)
