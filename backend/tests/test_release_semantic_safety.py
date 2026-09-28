from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.engine import ParseContext, classify_npc_speech_act, parse_message

from .conftest import bearer, create_payload


TERMS = {"price": {}, "prepayment_fraction": {}, "delivery_weeks": {}}
BASELINE = ParseContext(
    active_offer_id="offer_public",
    active_offer_revision=3,
    active_offer_terms={"price": 115_000, "prepayment_fraction": 1.0, "delivery_weeks": 8},
    active_offer_currency="EUR",
    focused_term_id="price",
)


def parse(message: str):
    return parse_message(
        message,
        TERMS,
        pending_confirmation=False,
        scenario_currency="EUR",
        context=BASELINE,
    )


@pytest.mark.parametrize(
    "message",
    [
        "Аванс 50% для нас много.",
        "Цена 120 000 евро для нас дорого.",
        "Поставка 8 недель для нас слишком долго.",
        "У нас есть предложение конкурента за 108 000 евро.",
        "Другой поставщик назвал цену 109 000 евро.",
    ],
)
def test_concerns_and_third_party_numbers_are_not_offers(message):
    result = parse(message)
    assert result.action == "inform", result
    assert result.terms_delta == {}


def test_third_party_quote_can_be_followed_by_an_explicit_own_proposal():
    result = parse("Конкурент предлагает 108 000 евро. Мы предлагаем цену 107 000 евро.")
    assert result.action == "counter_offer"
    assert result.terms_delta == {"price": 107_000}


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            "Цена 120 000 евро для нас дорого, зато предлагаем аванс 20%.",
            {"prepayment_fraction": 0.2},
        ),
        (
            "Аванс 50% слишком высокий, но предлагаем срок 4 недели.",
            {"delivery_weeks": 4},
        ),
    ],
)
def test_concern_term_does_not_leak_into_a_distinct_proposal(message, expected):
    result = parse(message)
    assert result.action == "counter_offer", result
    assert result.terms_delta == expected


@pytest.mark.parametrize("phrase", ["без аванса", "без предоплаты", "аванс 0%"])
def test_zero_prepayment_is_explicit(phrase):
    result = parse(f"Предлагаю цену 105 000 евро, {phrase}, поставку за 4 недели.")
    assert result.action == "counter_offer", result
    assert result.terms_delta == {
        "price": 105_000,
        "prepayment_fraction": 0.0,
        "delivery_weeks": 4,
    }


def test_contradictory_prepayment_values_require_clarification():
    result = parse("Предлагаю цену 105 000 евро, без аванса, предоплату 50%, поставку 4 недели.")
    assert result.action == "clarification"
    assert result.reason_code == "multiple_offer_candidates"


def test_unsupported_explicit_delivery_unit_does_not_inherit_old_term():
    result = parse("Цена 110 000 евро, предоплата 50%, поставка за месяц.")
    assert result.action == "clarification"
    assert result.reason_code == "unsupported_term_value"
    assert result.details["term_id"] == "delivery_weeks"


def test_argument_before_complete_package_does_not_trigger_relative_edit():
    result = parse(
        "Мы можем упростить внедрение и сократить ваши затраты. "
        "Предлагаю цену 110 000 евро, предоплату 50% и срок поставки 4 недели."
    )
    assert result.action == "counter_offer", result
    assert result.terms_delta == {
        "price": 110_000,
        "prepayment_fraction": 0.5,
        "delivery_weeks": 4,
    }


def test_absolute_target_and_relative_delta_are_distinct():
    target = parse("Снизьте цену до 110 000 евро.")
    assert target.action == "counter_offer"
    assert target.terms_delta == {"price": 110_000}
    assert target.details["baseline_offer_revision"] == 3

    delta = parse("Снизьте цену на 10 000 евро.")
    assert delta.action == "counter_offer"
    assert delta.terms_delta == {"price": 105_000}


def test_unsupported_conditional_package_fails_safe():
    result = parse("Готовы на цену 110 000 евро, если вы снизите предоплату до 50%.")
    assert result.action == "clarification"
    assert result.terms_delta == {}


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Какова процедура согласования?", "general_answer"),
        ("Вы жулики.", "abusive_language_boundary"),
        ("Какие условия для вас принципиальны?", "qualitative_interest_answer"),
        ("Что для вас самое важное?", "qualitative_interest_answer"),
    ],
)
def test_word_boundaries_and_interest_paraphrases(message, expected):
    assert classify_npc_speech_act(message, "question" if message.endswith("?") else "inform") == expected


@pytest.mark.parametrize("message", ["Прекращаю переговоры.", "Прекращаем переговоры."])
def test_singular_and_plural_exit_phrases(message):
    assert parse(message).action == "walk_away"


@pytest.mark.parametrize(
    ("scenario_id", "version", "first_offer"),
    [
        ("supplier_001", 6, "Цена 107 000 евро, предоплата 0%, срок поставки 8 недель."),
        ("saas_subscription_ru", 3, "Предлагаю цену 900 000 рублей, предоплату 0%, срок внедрения 4 недели."),
        ("freight_contract_ru", 4, "Предлагаю цену 300 000 рублей, предоплату 0%, срок доставки 4 недели."),
    ],
)
def test_complaint_after_npc_counter_never_binds(
    client: TestClient,
    scenario_id: str,
    version: int,
    first_offer: str,
):
    payload = create_payload(f"release-c01-{scenario_id}")
    payload.update(scenario_id=scenario_id, scenario_version=version)
    created = client.post("/api/v1/sessions", json=payload).json()
    headers = bearer(created["participant_token"])
    first = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=headers,
        json={
            "message": first_offer,
            "idempotency_key": f"c01-first-{scenario_id}",
            "expected_revision": created["revision"],
        },
    ).json()
    active_before = first["observation"]["active_offers"]

    complaint = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=headers,
        json={
            "message": "Аванс 50% для нас много.",
            "idempotency_key": f"c01-complaint-{scenario_id}",
            "expected_revision": first["revision"],
        },
    )

    assert complaint.status_code == 200, complaint.text
    body = complaint.json()
    assert body["status"] == "active"
    assert body["result"] == "turn_committed"
    assert body["observation"]["active_offers"] == active_before
    assert not any(action["action"] in {"counter_offer", "accept"} for action in body["committed_actions"])


def test_delivery_concern_after_npc_counter_does_not_open_acceptance(client: TestClient):
    payload = create_payload("release-delivery-concern")
    payload.update(scenario_id="supplier_001", scenario_version=6)
    created = client.post("/api/v1/sessions", json=payload).json()
    headers = bearer(created["participant_token"])
    first = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=headers,
        json={
            "message": "Цена 107 000 евро, предоплата 0%, срок поставки 8 недель.",
            "idempotency_key": "delivery-concern-first",
            "expected_revision": created["revision"],
        },
    ).json()
    active_before = first["observation"]["active_offers"]

    concern = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=headers,
        json={
            "message": "Поставка 8 недель для нас слишком долго.",
            "idempotency_key": "delivery-concern-message",
            "expected_revision": first["revision"],
        },
    )

    assert concern.status_code == 200, concern.text
    body = concern.json()
    assert body["status"] == "active"
    assert body["result"] == "turn_committed"
    assert body.get("pending_confirmation") is None
    assert body["observation"]["active_offers"] == active_before
    assert not any(action["action"] in {"counter_offer", "accept"} for action in body["committed_actions"])
