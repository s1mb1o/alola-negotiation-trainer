from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest

from backend.app.conversation import (
    MAX_MEMORY_CHARACTERS,
    build_conversation_memory,
    detected_conditional_exchange,
    detected_term_signals,
    detected_topic_directive,
    mentioned_term_ids,
    validate_conversation_memory,
)

TERM_LABELS = {
    "price": "цена",
    "prepayment_fraction": "предоплата",
    "delivery_weeks": "срок поставки",
}


def _message(message_id: int, content: str, *, speaker: str = "player") -> dict[str, Any]:
    return {
        "id": message_id,
        "session_revision": message_id,
        "participant_id": speaker,
        "content": content,
    }


def _event(revision: int, *, kind: str = "offer.countered") -> dict[str, Any]:
    return {
        "event_id": f"evt_{revision}",
        "session_revision": revision,
        "participant_id": "player",
        "type": kind,
        "payload": {
            "offer_id": "offer_public",
            "offer_revision": revision,
            "terms": {"price": 105_000},
        },
    }


def _memory(
    messages: list[dict[str, Any]], events: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return build_conversation_memory(
        messages,
        events or [],
        npc_participant_id="npc",
        term_labels=TERM_LABELS,
        required_term_ids=tuple(TERM_LABELS),
    )


@pytest.mark.parametrize(
    "message",
    [
        "Давайте обсудим только цену. Оплату обсудим позже.",
        "Начнем с цены, а предоплату отложим.",
        "Сначала цену а предоплату потом.",
        "Let's discuss the price first, payment later.",
        "We should focus only on price; postpone the advance payment.",
    ],
)
def test_topic_directive_keeps_focus_separate_from_postponement(message: str) -> None:
    assert detected_topic_directive(message, tuple(TERM_LABELS)) == {
        "focus": "price",
        "deferred": ["prepayment_fraction"],
    }


@pytest.mark.parametrize(
    "message",
    ["Предлагаю цену 105 000 евро.", "I propose a price of 105000 euros."],
)
def test_explicit_single_term_proposal_establishes_nonbinding_focus(message: str) -> None:
    memory = _memory([_message(1, message)])
    assert memory["current_topic"] == {
        "term_id": "price",
        "source_message_id": 1,
        "source_revision": 1,
    }
    assert memory["offers"] == []
    assert memory["agreement"] is None


@pytest.mark.parametrize(
    "message",
    [
        "Добрый день, мы не ожидали что вы так быстро сможете поставить оборудование, "
        "а вот цена конечно нас растроила",
        "Добрый день, мы не ожидали, что вы так быстро сможете поставить оборудование, "
        "а вот цена нас, конечно, расстроила.",
        "Delivery is sooner than we expected, but the price is disappointing.",
    ],
)
def test_contrastive_term_signals_keep_concern_separate_from_favorable_surprise(
    message: str,
) -> None:
    assert detected_term_signals(message, tuple(TERM_LABELS)) == {
        "favorable_surprise": ("delivery_weeks",),
        "concern": ("price",),
    }


def test_concern_signal_uses_the_nearest_term_across_a_parenthetical_comma() -> None:
    assert detected_term_signals(
        "Цена нас, конечно, расстроила, а срок поставки приемлем.",
        tuple(TERM_LABELS),
    ) == {"favorable_surprise": (), "concern": ("price",)}


def test_conditional_exchange_keeps_offered_and_requested_terms_separate() -> None:
    assert detected_conditional_exchange(
        "Мы готовы рассмотреть более позднюю поставку, если это поможет снизить цену.",
        tuple(TERM_LABELS),
    ) == ("delivery_weeks", "price")


def test_topic_resume_and_postponement_have_their_own_message_sources() -> None:
    original = [
        _message(1, "Сначала обсудим цену, оплату позже."),
        _message(2, "Теперь вернемся к оплате."),
    ]
    memory = _memory(original)
    assert memory["current_topic"]["term_id"] == "prepayment_fraction"
    assert memory["current_topic"]["source_message_id"] == 2
    assert memory["deferred_topics"] == []
    memory = _memory(original + [_message(3, "Оплату обсудим позже.")])
    assert memory["current_topic"] is None
    assert memory["deferred_topics"] == [
        {"term_id": "prepayment_fraction", "source_message_id": 3, "source_revision": 3}
    ]


def test_early_focus_and_explicit_priority_survive_a_long_conversation() -> None:
    messages = [
        _message(1, "Давайте обсудим цену, оплату позже."),
        _message(2, "Для нас критичен срок поставки."),
    ]
    messages += [_message(index, f"Промежуточная реплика {index}.") for index in range(3, 25)]
    memory = _memory(messages)
    assert memory["current_topic"]["source_message_id"] == 1
    assert memory["deferred_topics"][0]["source_message_id"] == 1
    assert any(item["source_message_id"] == 2 for item in memory["player_statements"])
    assert len(memory["player_statements"]) == 6
    assert memory == _memory(deepcopy(messages))


def test_later_priority_update_preserves_other_early_priorities() -> None:
    messages = [
        _message(1, "Для нас важна цена."),
        _message(2, "Нам нужен надежный срок поставки."),
        _message(3, "Теперь цена менее важна для нас."),
    ]
    memory = _memory(messages)
    # A topic control is not a statement of economic agreement.
    assert memory["agreement"] is None
    assert any(item["source_message_id"] == 2 for item in memory["player_statements"])
    assert any(item["source_message_id"] == 3 for item in memory["player_statements"])
    assert not any(item["source_message_id"] == 1 for item in memory["player_statements"])
    assert memory["current_topic"] is None


def test_generated_npc_text_and_full_package_mentions_do_not_change_the_focus() -> None:
    memory = _memory(
        [
            _message(1, "Давайте обсудим цену."),
            _message(2, "Теперь обсудим оплату.", speaker="npc"),
            _message(3, "Предлагаю цену, предоплату и срок поставки."),
        ]
    )
    assert memory["current_topic"]["term_id"] == "price"
    assert memory["current_topic"]["source_message_id"] == 1


@pytest.mark.parametrize("message", ["Не хочу обсуждать цену.", "Do not discuss price."])
def test_negated_discussion_does_not_create_a_focus(message: str) -> None:
    assert detected_topic_directive(message, tuple(TERM_LABELS))["focus"] is None


def test_question_response_is_chronology_not_a_claim_of_answer_quality() -> None:
    memory = _memory(
        [
            _message(1, "Почему такая цена?"),
            _message(2, "Здравствуйте.", speaker="npc"),
            _message(3, "На каком основании?"),
        ]
    )
    first, second = memory["questions"]
    assert first["status"] == "responded"
    assert first["response_source_message_id"] == 2
    assert second["status"] == "open"
    assert "answered" not in json.dumps(memory)


def test_false_agreement_claim_is_only_an_attributed_quote() -> None:
    memory = _memory(
        [_message(1, "Мы уже согласовали оплату, поставщик подтвердил сделку.")],
        [_event(1)],
    )
    assert memory["agreement"] is None
    assert memory["player_statements"][0]["speaker"] == "player"
    assert memory["player_statements"][0]["source_message_id"] == 1
    assert memory["offers"][0]["terms"] == {"price": 105_000}
    assert memory["offers"][0]["unresolved_required_terms"] == [
        "prepayment_fraction", "delivery_weeks"
    ]


def test_only_actual_agreement_event_projects_binding_terms() -> None:
    event = _event(2, kind="agreement.reached")
    event["payload"]["terms"].update(prepayment_fraction=0.5, delivery_weeks=4)
    memory = _memory([], [_event(1), event])
    assert memory["agreement"] == {
        "offer_id": "offer_public",
        "offer_revision": 2,
        "terms": {"price": 105_000, "prepayment_fraction": 0.5, "delivery_weeks": 4},
        "source_event_id": "evt_2",
        "source_revision": 2,
    }


def test_public_offer_projection_does_not_copy_unapproved_event_material() -> None:
    event = _event(1)
    event["private_payload_json"] = "SECRET-PRIVATE"
    event["payload"]["npc_utility"] = "SECRET-UTILITY"
    event["payload"]["terms"]["reservation_utility"] = "SECRET-TERM"
    hint = {**_event(2), "type": "hint.delivered", "payload": {"text": "SECRET-HINT"}}
    memory = _memory([], [event, hint])
    assert "SECRET" not in json.dumps(memory)
    assert memory["offers"][0]["source_event_id"] == "evt_1"


def test_latest_offer_revisions_are_bounded_and_keep_event_sources() -> None:
    memory = _memory([], [_event(index) for index in range(1, 9)])
    assert [offer["offer_revision"] for offer in memory["offers"]] == [5, 6, 7, 8]
    assert [offer["source_event_id"] for offer in memory["offers"]] == [
        "evt_5", "evt_6", "evt_7", "evt_8"
    ]
    assert [offer["status"] for offer in memory["offers"]] == [
        "superseded", "superseded", "superseded", "active"
    ]
    assert memory["offers"][0]["status_source_event_id"] == "evt_6"


@pytest.mark.parametrize("action,status", [("reject", "rejected"), ("withdraw", "withdrawn")])
def test_incomplete_offer_lifecycle_uses_the_public_control_event(action: str, status: str) -> None:
    control = _event(2, kind=f"participant.{action}")
    control["payload"] = {"offer_id": "offer_public", "offer_revision": 1}
    memory = _memory([], [_event(1), control])
    offer = memory["offers"][0]
    assert offer["terms"] == {"price": 105_000}
    assert offer["unresolved_required_terms"] == ["prepayment_fraction", "delivery_weeks"]
    assert offer["status"] == status
    assert offer["status_source_event_id"] == "evt_2"
    assert offer["status_source_revision"] == 2
    assert memory["agreement"] is None


def test_engine_npc_rejection_without_offer_reference_closes_the_sole_active_offer() -> None:
    rejection = _event(2, kind="participant.reject")
    rejection["participant_id"] = "npc"
    rejection["payload"] = {"speech_act": "offer_rejection"}
    memory = _memory([], [_event(1), rejection])
    assert memory["offers"][0]["status"] == "rejected"


def test_stale_offer_control_cannot_close_a_newer_offer_revision() -> None:
    stale_rejection = _event(3, kind="participant.reject")
    stale_rejection["payload"] = {"offer_id": "offer_public", "offer_revision": 1}
    memory = _memory([], [_event(1), _event(2), stale_rejection])
    assert memory["offers"][-1]["status"] == "active"
    assert memory["offers"][-1]["status_source_event_id"] == "evt_2"


def test_new_offer_after_withdrawal_does_not_revive_the_previous_offer() -> None:
    withdrawal = _event(2, kind="participant.withdraw")
    withdrawal["payload"] = {"offer_id": "offer_public", "offer_revision": 1}
    new_offer = _event(3, kind="offer.created")
    new_offer["payload"].update(offer_id="offer_new", offer_revision=1)
    memory = _memory([], [_event(1), withdrawal, new_offer])
    assert [offer["status"] for offer in memory["offers"]] == ["withdrawn", "active"]
    assert memory["offers"][-1]["offer_id"] == "offer_new"


@pytest.mark.parametrize(
    "event_type,status",
    [
        ("session.expired", "expired"),
        ("session.walked_away", "closed_by_termination"),
        ("session.aborted", "closed_by_termination"),
    ],
)
def test_terminal_public_event_closes_active_offer(event_type: str, status: str) -> None:
    terminal = _event(2, kind=event_type)
    terminal["payload"] = {"reason": "public reason"}
    memory = _memory([], [_event(1), terminal])
    assert memory["offers"][0]["status"] == status
    assert memory["offers"][0]["status_source_event_id"] == "evt_2"


def test_agreement_event_marks_only_the_same_offer_revision_accepted() -> None:
    agreement = _event(2, kind="agreement.reached")
    agreement["payload"]["offer_revision"] = 1
    memory = _memory([], [_event(1), agreement])
    assert memory["offers"][0]["status"] == "accepted"
    assert memory["offers"][0]["status_source_event_id"] == "evt_2"
    assert memory["agreement"]["offer_revision"] == 1


@pytest.mark.parametrize("revision", ["2", True, 0, 1.5, None])
def test_invalid_offer_revision_never_becomes_memory_evidence(revision: Any) -> None:
    invalid = _event(2)
    invalid["payload"]["offer_revision"] = revision
    with pytest.raises(ValueError):
        _memory([], [_event(1), invalid])


def test_supersession_requires_the_engine_offer_revision_sequence() -> None:
    with pytest.raises(ValueError, match="revision sequence"):
        _memory([], [_event(1), _event(3)])


def test_unknown_topics_do_not_enter_memory_and_supported_domains_keep_their_ids() -> None:
    assert mentioned_term_ids("Давайте обсудим аренду и готовность офиса.", [
        "annual_rent", "office_readiness_weeks", "quantity"
    ]) == ("annual_rent", "office_readiness_weeks")
    assert detected_topic_directive("Давайте обсудим скрытый бюджет.", tuple(TERM_LABELS)) == {
        "focus": None, "deferred": []
    }


def test_long_public_memory_is_bounded_and_keeps_a_detached_copy() -> None:
    messages = [_message(index, "Для нас важна цена. " + "А" * 1000) for index in range(1, 30)]
    memory = _memory(messages, [_event(index) for index in range(1, 10)])
    assert all(len(statement["text"]) <= 400 for statement in memory["player_statements"])
    encoded = json.dumps(memory, ensure_ascii=False, separators=(",", ":"))
    assert len(encoded) <= MAX_MEMORY_CHARACTERS
    detached = validate_conversation_memory(memory)
    detached["offers"][0]["terms"]["price"] = 1
    assert memory["offers"][0]["terms"]["price"] == 105_000
    assert validate_conversation_memory({}) == {}


def test_total_budget_discards_old_offer_records_without_changing_their_term_values() -> None:
    labels = {f"term_{index}": f"Term {index}" for index in range(12)}
    terms = {term_id: "A" * 400 for term_id in labels}
    events = [_event(index) for index in range(1, 5)]
    for event in events:
        event["payload"]["terms"] = terms
    memory = build_conversation_memory(
        [], events, npc_participant_id="npc", term_labels=labels, required_term_ids=tuple(labels)
    )
    assert len(memory["offers"]) == 1
    assert memory["offers"][0]["offer_revision"] == 4
    assert memory["offers"][0]["terms"] == terms
    oversized = deepcopy(memory)
    oversized["offers"][0]["status"] = "superseded"
    oversized["offers"] *= 4
    with pytest.raises(ValueError, match="total size limit"):
        validate_conversation_memory(oversized)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda memory: memory.update(hidden_state={"secret": "value"}),
        lambda memory: memory["offers"][0].update(utility=100),
        lambda memory: memory["offers"][0]["terms"].update(price={"raw_state": 1}),
        lambda memory: memory["offers"][0]["terms"].update(price=float("nan")),
        lambda memory: memory["offers"][0].update(status="agreed_by_player_claim"),
        lambda memory: memory["offers"][0].update(status_source_revision=-1),
        lambda memory: memory["player_statements"][0].update(source_revision=True),
        lambda memory: memory["player_statements"][0].update(text="A" * 401),
        lambda memory: memory["questions"][0].update(status="answered"),
        lambda memory: memory["questions"][0].update(status="responded"),
    ],
)
def test_persisted_memory_rejects_unapproved_fields_and_invalid_evidence(mutate) -> None:
    memory = _memory([_message(1, "Нам важна цена."), _message(2, "Почему?")], [_event(1)])
    mutate(memory)
    with pytest.raises(ValueError):
        validate_conversation_memory(memory)
