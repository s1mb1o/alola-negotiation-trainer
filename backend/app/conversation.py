"""Bounded, replayable memory of public conversation evidence.

Callers must select one session and redact credentials before calling this module.
Participant quotes remain untrusted. Only typed public events supply offer facts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import math
import re
from typing import Any


MAX_MEMORY_CHARACTERS = 8_000
MAX_MEMORY_TEXT_CHARACTERS = 400
MAX_MEMORY_TOPICS = 12
MAX_MEMORY_STATEMENTS = 6
MAX_MEMORY_QUESTIONS = 4
MAX_MEMORY_OFFERS = 4
_OFFER_STATUSES = (
    "active", "superseded", "withdrawn", "rejected", "accepted", "expired",
    "closed_by_termination",
)

_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
_TERM_ID = re.compile(r"[a-z][a-z0-9_]{0,99}\Z")
_TOPIC_PATTERNS = {
    "price": r"\b(?:цен(?:а|ы|е|у|ой|ами|ах)?|стоимост\w*|price|pricing|cost)\b",
    "annual_rent": r"\b(?:аренд\w*|ставк\w*|rent|rental|price|цен(?:а|ы|е|у|ой)?)\b",
    "prepayment_fraction": (
        r"\b(?:предоплат\w*|аванс\w*|оплат\w*|платеж\w*|prepayment|payment|advance)\b"
    ),
    "delivery_weeks": (
        r"\b(?:поставк\w*|доставк\w*|запуск\w*|срок\w*|delivery|launch|timeline|lead time)\b"
    ),
    "office_readiness_weeks": (
        r"\b(?:готовност\w*|въезд\w*|переезд\w*|срок\w*|readiness|ready|move.in|timeline)\b"
    ),
    "quantity": r"\b(?:количеств\w*|объем\w*|quantity|volume)\b",
}
_FOCUS = re.compile(
    r"\b(?:обсуд\w*|обсужд\w*|начнем|начните|перейдем|вернемся|сосредоточ\w*|"
    r"discuss|start|focus|return|resume)\b"
)
_FOCUS_ORDER = re.compile(
    r"^(?:давайте\s+)?(?:сначала|только|сейчас|теперь|first|only|now)\b"
    r"|\b(?:сначала|первым|first|only)\s*$"
)
_PROPOSAL = re.compile(r"\b(?:предлагаю|предлагаем|propose)\b|\b(?:i|we)\s+offer\b")
_DEFER = re.compile(r"\b(?:позже|потом|затем|отлож\w*|later|postpone|defer|afterwards)\b")
_NEGATED_FOCUS = re.compile(
    r"\bне\s+(?:(?:будем|хочу|нужно|надо|хотим)\s+)?(?:обсуд\w*|обсужд\w*|начин\w*)"
    r"|\b(?:don't|do not)\s+(?:discuss|focus|start|want)\b"
)
_QUESTION = re.compile(
    r"^(?:что|как|когда|почему|зачем|какой|какая|какие|можете|на чем|на какой|"
    r"what|how|when|why|which|can you|could you)\b"
)
_PRIORITY = re.compile(
    r"\b(?:важ\w*|нуж\w*|приоритет\w*|критич\w*|бюджет\w*|рис\w*|"
    r"предпоч\w*|important|need|priority|critical|budget|risk|prefer|avoid)\b"
)


def _normalized(message: str) -> str:
    return " ".join(message.casefold().replace("ё", "е").replace("’", "'").split())


def mentioned_term_ids(message: str, term_ids: Sequence[str]) -> tuple[str, ...]:
    """Identify authored topic names, without extracting or accepting term values."""

    normalized = _normalized(message)
    return tuple(
        term_id
        for term_id in dict.fromkeys(term_ids)
        if re.search(
            _TOPIC_PATTERNS.get(term_id, r"\b" + re.escape(term_id.replace("_", " ")) + r"\b"),
            normalized,
        )
    )


def detected_topic_directive(message: str, term_ids: Sequence[str]) -> dict[str, Any]:
    """Project explicit participant focus and postponement requests.

    Ambiguous multi-topic clauses do not select a focus. A deferred topic does not
    become an agreed term. Callers must not apply this function to generated prose.
    """

    focus = None
    deferred: list[str] = []
    normalized = _normalized(message)
    single_term_proposal = len(mentioned_term_ids(normalized, term_ids)) == 1
    for clause in re.split(r"[,.!?;\n]+|\s+(?:а|но|but)\s+", normalized):
        clause = clause.strip()
        topics = mentioned_term_ids(clause, term_ids)
        if not topics:
            continue
        if _DEFER.search(clause):
            for topic in topics:
                if topic not in deferred:
                    deferred.append(topic)
            if focus in topics:
                focus = None
        elif (
            len(topics) == 1
            and (
                _FOCUS.search(clause)
                or (_FOCUS_ORDER.search(clause) and not _PRIORITY.search(clause))
                or (single_term_proposal and _PROPOSAL.search(clause))
            )
            and not _NEGATED_FOCUS.search(clause)
        ):
            focus = topics[0]
            if focus in deferred:
                deferred.remove(focus)
    return {"focus": focus, "deferred": deferred[:MAX_MEMORY_TOPICS]}


def _message_source(message: Mapping[str, Any]) -> dict[str, int]:
    return {
        "source_message_id": message["id"],
        "source_revision": message["session_revision"],
    }


def _event_offer(event: Mapping[str, Any], term_ids: Sequence[str]) -> dict[str, Any]:
    payload = event["payload"]
    terms = {key: value for key, value in payload["terms"].items() if key in term_ids}
    return {
        "offer_id": payload["offer_id"],
        "offer_revision": payload["offer_revision"],
        "terms": terms,
        "source_event_id": event["event_id"],
        "source_revision": event["session_revision"],
    }


def build_conversation_memory(
    messages: Sequence[Mapping[str, Any]],
    public_events: Sequence[Mapping[str, Any]],
    *,
    npc_participant_id: str,
    term_labels: Mapping[str, str],
    required_term_ids: Sequence[str],
) -> dict[str, Any]:
    """Rebuild an allowlisted memory from redacted public records in one session."""

    term_ids = tuple(term_labels)[:MAX_MEMORY_TOPICS]
    memory: dict[str, Any] = {
        "version": 1,
        "current_topic": None,
        "deferred_topics": [],
        "player_statements": [],
        "questions": [],
        "offers": [],
        "agreement": None,
    }
    postponed: dict[str, dict[str, Any]] = {}
    statements: list[tuple[bool, dict[str, Any]]] = []
    for message in sorted(messages, key=lambda item: (item["session_revision"], item["id"])):
        text = str(message["content"])
        speaker = "npc" if message["participant_id"] == npc_participant_id else "player"
        source = _message_source(message)
        topics = mentioned_term_ids(text, term_ids)
        for question in memory["questions"]:
            if question["status"] == "open" and question["speaker"] != speaker:
                question.update(
                    status="responded",
                    response_source_message_id=message["id"],
                    response_source_revision=message["session_revision"],
                )
        is_question = "?" in text or bool(_QUESTION.search(_normalized(text)))
        if is_question:
            memory["questions"].append(
                {
                    "speaker": speaker,
                    "text": text[:MAX_MEMORY_TEXT_CHARACTERS],
                    "term_ids": list(topics),
                    **source,
                    "status": "open",
                }
            )
            memory["questions"] = memory["questions"][-MAX_MEMORY_QUESTIONS:]
        if speaker != "player":
            continue
        directive = detected_topic_directive(text, term_ids)
        for topic in directive["deferred"]:
            postponed[topic] = {"term_id": topic, **source}
            if memory["current_topic"] and memory["current_topic"]["term_id"] == topic:
                memory["current_topic"] = None
        if directive["focus"]:
            topic = directive["focus"]
            memory["current_topic"] = {"term_id": topic, **source}
            postponed.pop(topic, None)
        is_priority = bool(_PRIORITY.search(_normalized(text)))
        if (
            not text.strip()
            or is_question
            or ((directive["focus"] or directive["deferred"]) and not is_priority)
        ):
            continue
        statement = {
            "speaker": "player",
            "text": text[:MAX_MEMORY_TEXT_CHARACTERS],
            "term_ids": list(topics),
            **source,
        }
        if is_priority:
            statements = [
                (priority, previous)
                for priority, previous in statements
                if not (priority and previous["term_ids"] == statement["term_ids"])
            ]
        statements.append((is_priority, statement))
        if len(statements) > MAX_MEMORY_STATEMENTS:
            evicted = next(
                (index for index, (priority, _) in enumerate(statements) if not priority), 0
            )
            statements.pop(evicted)
    memory["deferred_topics"] = list(postponed.values())[:MAX_MEMORY_TOPICS]
    memory["player_statements"] = [statement for _, statement in statements]
    active_offer: dict[str, Any] | None = None
    for event in sorted(public_events, key=lambda item: item["session_revision"]):
        event_type = event["type"]
        closed_status = {
            "participant.reject": "rejected",
            "participant.withdraw": "withdrawn",
            "session.expired": "expired",
            "session.walked_away": "closed_by_termination",
            "session.aborted": "closed_by_termination",
        }.get(event_type)
        if closed_status:
            payload = event["payload"]
            # Human controls identify the target. NPC rejection targets the sole
            # active offer and supplies only the engine-selected speech act.
            target_matches = active_offer is not None and (
                "offer_id" not in payload
                or (
                    payload["offer_id"] == active_offer["offer_id"]
                    and payload.get("offer_revision") == active_offer["offer_revision"]
                )
            )
            if target_matches:
                _set_offer_status(active_offer, closed_status, event)
                active_offer = None
            continue
        if event_type not in {"offer.created", "offer.countered", "agreement.reached"}:
            continue
        offer = _event_offer(event, term_ids)
        _integer(offer["offer_revision"], minimum=1)
        if event_type == "agreement.reached":
            memory["agreement"] = offer
            if active_offer and (
                offer["offer_id"], offer["offer_revision"]
            ) == (active_offer["offer_id"], active_offer["offer_revision"]):
                _set_offer_status(active_offer, "accepted", event)
                active_offer = None
        else:
            if active_offer:
                # The engine counters the same offer ID at the next revision.
                # Do not derive supersession from a mention in participant prose.
                if (
                    event_type != "offer.countered"
                    or offer["offer_id"] != active_offer["offer_id"]
                    or type(offer["offer_revision"]) is not int
                    or offer["offer_revision"] != active_offer["offer_revision"] + 1
                ):
                    raise ValueError("Public offer events do not follow the revision sequence")
                _set_offer_status(active_offer, "superseded", event)
            offer["speaker"] = "npc" if event["participant_id"] == npc_participant_id else "player"
            offer["unresolved_required_terms"] = [
                term_id
                for term_id in required_term_ids
                if term_id in term_ids and term_id not in offer["terms"]
            ]
            _set_offer_status(offer, "active", event)
            memory["offers"].append(offer)
            memory["offers"] = memory["offers"][-MAX_MEMORY_OFFERS:]
            active_offer = offer
    # The serialized envelope has a second bound in addition to all field limits.
    while len(_encoded(memory)) > MAX_MEMORY_CHARACTERS:
        for field in ("offers", "questions", "player_statements", "deferred_topics"):
            if memory[field]:
                memory[field].pop(0)
                break
        else:
            raise ValueError("Conversation memory evidence exceeds the total size limit")
    return validate_conversation_memory(memory)


def _set_offer_status(offer: dict[str, Any], status: str, event: Mapping[str, Any]) -> None:
    offer.update(
        status=status,
        status_source_event_id=event["event_id"],
        status_source_revision=event["session_revision"],
    )


def _encoded(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _keys(value: Any, required: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not required.issubset(value):
        raise ValueError("Conversation memory fields are missing")
    if set(value) - required - (optional or set()):
        raise ValueError("Conversation memory contains an unsupported field")
    return dict(value)


def _integer(value: Any, *, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError("Conversation memory reference must be a nonnegative integer")


def _text(value: Any, *, identifier: bool = False, term: bool = False) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_MEMORY_TEXT_CHARACTERS:
        raise ValueError("Conversation memory text is invalid")
    if identifier and not _IDENTIFIER.fullmatch(value):
        raise ValueError("Conversation memory identifier is invalid")
    if term and not _TERM_ID.fullmatch(value):
        raise ValueError("Conversation memory term identifier is invalid")


def _list(value: Any, maximum: int) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("Conversation memory list exceeds its limit")
    return value


def _source(value: Mapping[str, Any], *, event: bool = False) -> None:
    _integer(value["source_revision"])
    if event:
        _text(value["source_event_id"], identifier=True)
    else:
        _integer(value["source_message_id"], minimum=1)


def _topics(value: Any) -> None:
    topics = _list(value, MAX_MEMORY_TOPICS)
    for topic in topics:
        _text(topic, term=True)
    if len(set(topics)) != len(topics):
        raise ValueError("Conversation memory topics must be unique")


def _validate_offer(value: Any, *, agreement: bool = False) -> None:
    keys = {"offer_id", "offer_revision", "terms", "source_event_id", "source_revision"}
    item = _keys(value, keys if agreement else keys | {
        "speaker", "unresolved_required_terms", "status", "status_source_event_id",
        "status_source_revision",
    })
    _source(item, event=True)
    _text(item["offer_id"], identifier=True)
    _integer(item["offer_revision"], minimum=1)
    if not isinstance(item["terms"], Mapping) or len(item["terms"]) > MAX_MEMORY_TOPICS:
        raise ValueError("Conversation memory offer terms exceed the limit")
    for term_id, scalar in item["terms"].items():
        _text(term_id, term=True)
        if isinstance(scalar, str):
            _text(scalar)
        elif type(scalar) not in {int, float, bool} or (
            type(scalar) is float and not math.isfinite(scalar)
        ):
            raise ValueError("Conversation memory terms must be finite scalar values")
    if not agreement:
        if item["speaker"] not in ("player", "npc"):
            raise ValueError("Conversation memory offer speaker is invalid")
        if item["status"] not in _OFFER_STATUSES:
            raise ValueError("Conversation memory offer status is invalid")
        _text(item["status_source_event_id"], identifier=True)
        _integer(item["status_source_revision"], minimum=item["source_revision"])
        _topics(item["unresolved_required_terms"])
        if set(item["terms"]) & set(item["unresolved_required_terms"]):
            raise ValueError("An offered term cannot also be unresolved")


def validate_conversation_memory(payload: Any) -> dict[str, Any]:
    """Validate an exact public envelope and return a detached JSON-safe copy."""

    if isinstance(payload, Mapping) and not payload:
        return {}
    memory = _keys(
        payload,
        {
            "version", "current_topic", "deferred_topics", "player_statements", "questions",
            "offers", "agreement",
        },
    )
    if type(memory["version"]) is not int or memory["version"] != 1:
        raise ValueError("Conversation memory version is unsupported")
    source_keys = {"source_message_id", "source_revision"}
    deferred = _list(memory["deferred_topics"], MAX_MEMORY_TOPICS)
    focused_topics = [memory["current_topic"]] if memory["current_topic"] is not None else []
    for topic in focused_topics + deferred:
        _keys(topic, {"term_id"} | source_keys)
        _source(topic)
        _text(topic["term_id"], term=True)
    if len({item["term_id"] for item in deferred}) != len(deferred):
        raise ValueError("Deferred conversation topics must be unique")
    if memory["current_topic"] and memory["current_topic"]["term_id"] in {
        item["term_id"] for item in deferred
    }:
        raise ValueError("The current conversation topic cannot be deferred")
    statement_keys = {"speaker", "text", "term_ids"} | source_keys
    for statement in _list(memory["player_statements"], MAX_MEMORY_STATEMENTS):
        _keys(statement, statement_keys)
        _source(statement)
        _text(statement["text"])
        _topics(statement["term_ids"])
        if statement["speaker"] != "player":
            raise ValueError("Conversation statements must remain attributed to the player")
    for question in _list(memory["questions"], MAX_MEMORY_QUESTIONS):
        _keys(
            question,
            statement_keys | {"status"},
            {"response_source_message_id", "response_source_revision"},
        )
        _source(question)
        _text(question["text"])
        _topics(question["term_ids"])
        if question["speaker"] not in ("player", "npc") or question["status"] not in (
            "open", "responded"
        ):
            raise ValueError("Conversation question attribution is invalid")
        response_keys = {"response_source_message_id", "response_source_revision"}
        if question["status"] == "responded":
            if not response_keys.issubset(question):
                raise ValueError("A responded question requires its response source")
            _integer(
                question["response_source_message_id"], minimum=question["source_message_id"] + 1
            )
            _integer(question["response_source_revision"], minimum=question["source_revision"])
        elif response_keys & question.keys():
            raise ValueError("An open question cannot contain a response source")
    for offer in _list(memory["offers"], MAX_MEMORY_OFFERS):
        _validate_offer(offer)
    if sum(offer["status"] == "active" for offer in memory["offers"]) > 1:
        raise ValueError("Conversation memory cannot contain multiple active offers")
    if memory["agreement"] is not None:
        _validate_offer(memory["agreement"], agreement=True)
    encoded = _encoded(memory)
    if len(encoded) > MAX_MEMORY_CHARACTERS:
        raise ValueError("Conversation memory exceeds the total size limit")
    return json.loads(encoded)
