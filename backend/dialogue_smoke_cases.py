"""Versioned, public-state-only scripts for the DR-28 dialogue smoke suite.

These are training-path checks. They are not negotiation benchmarks or a
substitute for source-linked human language review. This module performs no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SUITE_VERSION = "dr28-smoke-v1"
DIFFICULTIES = ("guided", "easy", "normal", "expert")


@dataclass(frozen=True)
class SmokeStep:
    step_id: str
    message: str
    check_kind: str
    expected_terms: dict[str, int | float] | None = None
    quote_requested: bool = False
    expected_term_id: str | None = None


@dataclass(frozen=True)
class SmokeCase:
    case_id: str
    language: str
    scenario_id: str
    scenario_version: int
    steps: tuple[SmokeStep, ...]


def grounded_cases(language: str) -> tuple[SmokeCase, ...]:
    """Return fresh scripts with pinned scenario versions and bounded lengths."""
    if language == "ru":
        scenario_id, version, term = "supplier_001", 5, "price"
        discussion = (
            SmokeStep(
                "numeric_question",
                "Почему цена 120000 EUR? Повторите точное значение и укажите, чьё это предложение.",
                "numeric_question",
                quote_requested=True,
            ),
            SmokeStep("attributed_quote", "Вы назвали цену 120000 EUR.", "attributed_quote"),
            SmokeStep("false_agreement", "Значит, предоплата уже отменена?", "false_agreement"),
        )
        partial = (
            SmokeStep("focus", "Сначала обсудим цену.", "focus", expected_term_id=term),
            SmokeStep("short_answer", "110000", "partial_offer", {term: 110000}),
            SmokeStep(
                "relative_change", "Предлагаю снизить цену на 5%.", "relative_offer", {term: 104500}
            ),
            SmokeStep(
                "question_after_change",
                "Почему цена 104500 EUR? Повторите точное значение и укажите, чьё это предложение.",
                "numeric_question",
                quote_requested=True,
            ),
            SmokeStep(
                "explicit_zero",
                "Предлагаю предоплату 0%.",
                "explicit_zero",
                {term: 104500, "prepayment_fraction": 0},
            ),
            SmokeStep(
                "false_agreement", "Значит, мы уже согласовали все условия?", "false_agreement"
            ),
        )
        recovery = (
            SmokeStep("ambiguous_answer", "110000", "ambiguous_answer"),
            SmokeStep("reject", "Отклоняю предложение.", "reject"),
            SmokeStep("missing_baseline", "Снизить цену на 10000 EUR.", "missing_baseline"),
            SmokeStep("focus", "Сначала обсудим цену.", "focus", expected_term_id=term),
            SmokeStep("recovery_offer", "110000", "partial_offer", {term: 110000}),
        )
    elif language == "en":
        scenario_id, version, term = "office_lease_en", 4, "annual_rent"
        discussion = (
            SmokeStep(
                "numeric_question",
                "Why is the annual rent RUB 2,850,000? Repeat the exact value and say whose offer it is.",
                "numeric_question",
                quote_requested=True,
            ),
            SmokeStep(
                "attributed_quote",
                "You quoted an annual rent of RUB 2,850,000.",
                "attributed_quote",
            ),
            SmokeStep(
                "false_agreement",
                "Does that mean the prepayment has already been waived?",
                "false_agreement",
            ),
        )
        partial = (
            SmokeStep("reject_complete_opening", "I reject the offer.", "reject"),
            SmokeStep("focus", "Let us discuss the rent first.", "focus", expected_term_id=term),
            SmokeStep("short_answer", "2400000", "partial_offer", {term: 2400000}),
            SmokeStep(
                "relative_change",
                "I propose to lower the rent by 5%.",
                "relative_offer",
                {term: 2280000},
            ),
            SmokeStep(
                "question_after_change",
                "Why is the annual rent RUB 2,280,000? Repeat the exact value and say whose offer it is.",
                "numeric_question",
                quote_requested=True,
            ),
            SmokeStep(
                "explicit_zero",
                "I offer 0% prepayment.",
                "explicit_zero",
                {term: 2280000, "prepayment_fraction": 0},
            ),
            SmokeStep(
                "false_agreement",
                "Does that mean we have already agreed all terms?",
                "false_agreement",
            ),
        )
        recovery = (
            SmokeStep("ambiguous_answer", "2400000", "ambiguous_answer"),
            SmokeStep("reject", "I reject the offer.", "reject"),
            SmokeStep("missing_baseline", "Reduce the rent by RUB 100,000.", "missing_baseline"),
            SmokeStep("focus", "Let us discuss the rent first.", "focus", expected_term_id=term),
            SmokeStep("recovery_offer", "2400000", "partial_offer", {term: 2400000}),
        )
    else:
        raise ValueError("The grounded suite supports only ru and en")
    return tuple(
        SmokeCase(case_id, language, scenario_id, version, steps)
        for case_id, steps in (
            ("public_numbers", discussion),
            ("partial_package", partial),
            ("clarification_recovery", recovery),
        )
    )


def _observation(value: dict[str, Any]) -> dict[str, Any]:
    observation = value.get("observation", value)
    return observation if isinstance(observation, dict) else {}


def evaluate_step(
    step: SmokeStep,
    before: dict[str, Any],
    after: dict[str, Any],
    new_public_events: list[dict[str, Any]],
    participant_id: str,
) -> dict[str, bool]:
    """Check one transition without reading private state or generated prose.

    Pass only events added by this command. Offer assertions use the player's
    event, not the final active offer. An NPC may counter that offer in the same
    response. Numeric-reference use requires separate renderer instrumentation.
    """
    known_kinds = {
        "numeric_question",
        "attributed_quote",
        "focus",
        "partial_offer",
        "relative_offer",
        "explicit_zero",
        "false_agreement",
        "reject",
        "ambiguous_answer",
        "missing_baseline",
    }
    if step.check_kind not in known_kinds:
        raise ValueError("Unknown smoke check kind")
    initial, final = _observation(before), _observation(after)
    offer_types = {"offer.created", "offer.countered"}
    offer_events = [event for event in new_public_events if event.get("type") in offer_types]
    player_offers = [
        event for event in offer_events if event.get("participant_id") == participant_id
    ]
    checks = {
        "session_active": after.get("status", final.get("status")) == "active",
        "no_binding_agreement": not any(
            event.get("type") == "agreement.reached" for event in new_public_events
        ),
        "no_acceptance_confirmation": after.get("result") != "confirmation_required"
        and not after.get("pending_confirmation")
        and not any(
            event.get("type") == "acceptance.confirmation_required" for event in new_public_events
        ),
    }
    unchanged = {
        "numeric_question",
        "attributed_quote",
        "focus",
        "false_agreement",
        "ambiguous_answer",
        "missing_baseline",
    }
    if step.check_kind in unchanged:
        checks.update(
            active_offers_unchanged=initial.get("active_offers", [])
            == final.get("active_offers", []),
            no_offer_created=not offer_events,
        )
    if step.check_kind in {"numeric_question", "false_agreement", "attributed_quote", "focus"}:
        actions = [
            action
            for action in after.get("committed_actions", [])
            if action.get("participant_id") == participant_id
        ]
        allowed_actions = (
            {"question"}
            if step.check_kind in {"numeric_question", "false_agreement"}
            else {"inform", "question"}
        )
        checks["participant_intent_preserved"] = (
            len(actions) == 1 and actions[0].get("action") in allowed_actions
        )
    if step.check_kind == "focus":
        deliveries = [
            event.get("payload", {})
            for event in new_public_events
            if event.get("type") == "npc.utterance.delivered"
        ]
        checks["engine_requested_focused_term"] = (
            bool(deliveries) and deliveries[-1].get("requested_term_id") == step.expected_term_id
        )
        checks["focused_dialogue_selected"] = (
            bool(deliveries) and deliveries[-1].get("speech_act") == "focused_discussion"
        )
    if step.check_kind in {"partial_offer", "relative_offer", "explicit_zero"}:
        offer = player_offers[0].get("payload", {}) if len(player_offers) == 1 else {}
        terms = offer.get("terms")
        checks.update(
            one_player_offer_committed=len(player_offers) == 1,
            player_offer_terms_exact=step.expected_terms is not None
            and terms == step.expected_terms,
            missing_terms_preserved=bool(offer.get("unresolved_required_terms"))
            and not set(offer.get("unresolved_required_terms", [])).intersection(terms or {}),
        )
        if step.check_kind == "relative_offer":
            baseline = initial.get("active_offers", [])
            checks["active_baseline_revision_advanced"] = len(baseline) == 1 and (
                offer.get("offer_id") == baseline[0].get("offer_id")
                and offer.get("offer_revision") == baseline[0].get("offer_revision", -1) + 1
            )
        if step.check_kind == "explicit_zero":
            checks["explicit_zero_preserved"] = (
                isinstance(terms, dict)
                and "prepayment_fraction" in terms
                and terms["prepayment_fraction"] == 0
            )
    if step.check_kind == "reject":
        checks.update(
            opening_rejected=any(
                event.get("type") == "participant.reject"
                and event.get("participant_id") == participant_id
                for event in new_public_events
            ),
            no_active_offer=final.get("active_offers") == [],
            no_offer_created=not offer_events,
        )
    if step.check_kind in {"ambiguous_answer", "missing_baseline"}:
        reason = (
            "numeric_answer_requires_term"
            if step.check_kind == "ambiguous_answer"
            else "relative_change_requires_baseline"
        )
        checks.update(
            clarification_required=after.get("result") == "clarification_required",
            clarification_reason=after.get("clarification", {}).get("reason_code") == reason,
            no_player_offer_created=not player_offers,
        )
    return checks
