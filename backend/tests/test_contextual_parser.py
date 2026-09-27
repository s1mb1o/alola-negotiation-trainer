"""DR-28: numbers do not authorize an offer without a grounded input intent."""

from dataclasses import replace

import pytest

from backend.app.engine import ParseContext, parse_message


TERMS = {"price": {}, "prepayment_fraction": {}, "delivery_weeks": {}}
BASELINE = ParseContext(
    active_offer_id="off_public",
    active_offer_revision=7,
    active_offer_terms={"price": 120_000, "prepayment_fraction": 0.3, "delivery_weeks": 8},
    active_offer_currency="EUR",
    focused_term_id="price",
)


def parse(message, context=BASELINE, *, pending=False):
    return parse_message(
        message, TERMS, pending_confirmation=pending, scenario_currency="EUR", context=context
    )


@pytest.mark.parametrize("message", [
    "Почему цена 120000 EUR?", "Why is the price EUR 120,000?",
    "Почему предоплата 30%?", "Why is prepayment 30%?",
    "Можете снизить цену на 10000 EUR?", "Can you reduce the price by EUR 10,000?",
    "Вы предлагаете 120000 EUR?", "Do you propose EUR 120,000?",
    "Почему вы предлагаете 30% предоплаты?", "Why do you propose 30% prepayment?",
    "Правильно ли я понимаю, что цена 120000 EUR?",
    "Is it correct that the price is EUR 120,000?",
    "А 105 тысяч?", "EUR 105,000?", "Почему цена 120000 EUR",
    "Какую скидку вы дадите от 120000 EUR?",
])
def test_numeric_questions_are_not_offers(message):
    result = parse(message)
    assert result.action == "question"
    assert result.terms_delta == {}


@pytest.mark.parametrize("message", [
    'Вы сказали: «цена 120000 EUR, предоплата 30%».',
    'You said: "price EUR 120,000, prepayment 30%".',
    '«Предлагаю цену 105000 EUR».', '"I offer EUR 105,000".',
    "Вы назвали цену 120000 EUR.", "You quoted a price of EUR 120,000.",
    "Цена 120000 EUR — это ваше предложение.", "EUR 120,000 is your offer.",
    "Раньше цена была 120000 EUR.", "The previous price was EUR 120,000.",
    "Я не предлагаю цену 105000 EUR.", "I do not propose EUR 105,000.",
    "Предоплата 30% меня не устраивает.", "30% prepayment is not acceptable.",
])
def test_reported_or_negated_values_do_not_become_offers(message):
    result = parse(message)
    assert result.action in {"inform", "clarification"}
    assert result.terms_delta == {}


@pytest.mark.parametrize("message, expected", [
    ("Почему цена 120000 EUR? Предлагаю предоплату 40%.", {"prepayment_fraction": 0.4}),
    ("Why is price EUR 120,000? I offer 40% prepayment.", {"prepayment_fraction": 0.4}),
    ("Предлагаю цену 105000 EUR. Почему предоплата 30%?", {"price": 105000}),
    ("I offer EUR 105,000. Why is prepayment 30%?", {"price": 105000}),
    ("Почему предоплата 30%, а я предлагаю 105000 EUR.", {"price": 105000}),
    ('Вы сказали «цена 120000 EUR». Предлагаю цену 105000 EUR.', {"price": 105000}),
    ('You said "EUR 120,000". I offer EUR 105,000.', {"price": 105000}),
    ("Цена не 110000 EUR, а 105000 EUR.", {"price": 105000}),
    ("Not EUR 110,000, but EUR 105,000.", {"price": 105000}),
    ("Предлагаю не 110000 EUR, а 105000 EUR.", {"price": 105000}),
    ("I propose not EUR 110,000 but EUR 105,000.", {"price": 105000}),
])
def test_only_asserted_proposal_or_correction_is_extracted(message, expected):
    result = parse(message)
    assert result.action == "counter_offer", result
    assert result.terms_delta == expected


@pytest.mark.parametrize("message, expected", [
    ("Снизить цену на 10000 EUR", {"price": 110000}),
    ("Снизим цену на 10000 EUR.", {"price": 110000}),
    ("Reduce the price by EUR 10,000.", {"price": 110000}),
    ("Предлагаю снизить цену на 5%.", {"price": 114000}),
    ("I propose to lower the price by 5%.", {"price": 114000}),
    ("Увеличить цену на 10000 EUR.", {"price": 130000}),
    ("Increase the price by EUR 10,000.", {"price": 130000}),
    ("Сократить срок поставки на 2 недели.", {"delivery_weeks": 6}),
    ("Reduce delivery by 2 weeks.", {"delivery_weeks": 6}),
    ("Снизить предоплату на 5 процентных пунктов.", {"prepayment_fraction": 0.25}),
    ("Reduce prepayment by 5 percentage points.", {"prepayment_fraction": 0.25}),
])
def test_relative_changes_use_exact_active_public_baseline(message, expected):
    result = parse(message)
    assert result.action == "counter_offer", result
    assert result.terms_delta == expected
    assert result.details["baseline_offer_id"] == "off_public"
    assert result.details["baseline_offer_revision"] == 7


@pytest.mark.parametrize("message, context, reason", [
    ("Снизить цену на 10000 EUR", None, "relative_change_requires_baseline"),
    ("Reduce the price by 5%", ParseContext(), "relative_change_requires_baseline"),
    ("Reduce the price by EUR 10,000", replace(BASELINE, active_offer_revision=None), "relative_change_requires_baseline"),
    ("Reduce the price by EUR 10,000", replace(BASELINE, active_offer_terms={}), "relative_change_requires_baseline"),
    ("Reduce the price by EUR 10,000", replace(BASELINE, ambiguous_offer_reference=True), "ambiguous_numeric_reference"),
    ("Reduce the price by USD 10,000", BASELINE, "currency_mismatch"),
    ("Reduce the price by 5%", replace(BASELINE, active_offer_currency="USD"), "currency_mismatch"),
    ("Снизить предоплату на 5%", BASELINE, "ambiguous_relative_change"),
    ("Reduce prepayment by 5%", BASELINE, "ambiguous_relative_change"),
    ("Снизить цену на 10000 или на 20000 EUR", BASELINE, "ambiguous_numeric_reference"),
    ("Reduce either your price or my price by EUR 10,000", BASELINE, "ambiguous_numeric_reference"),
    ("Reduce the previous price by EUR 10,000", BASELINE, "ambiguous_numeric_reference"),
    ("Снизить цену с 120000 до 100000 EUR", BASELINE, "ambiguous_relative_change"),
    ("Reduce the price by half", BASELINE, "ambiguous_relative_change"),
])
def test_ambiguous_relative_changes_require_clarification(message, context, reason):
    result = parse(message, context)
    assert result.action == "clarification", result
    assert result.reason_code == reason
    assert result.terms_delta == {}


def test_qualitative_trade_willingness_is_discussion_not_a_numeric_edit():
    result = parse_message(
        "Мы готовы рассмотреть более позднюю поставку, если это поможет снизить цену.",
        TERMS,
        pending_confirmation=False,
        scenario_currency="EUR",
        context=BASELINE,
    )

    assert result.action == "inform"
    assert result.terms_delta == {}


@pytest.mark.parametrize("message, context, expected", [
    ("105 тысяч", BASELINE, {"price": 105000}),
    ("105 thousand", BASELINE, {"price": 105000}),
    ("105000", replace(BASELINE, focused_term_id=None, expected_term_id="price"), {"price": 105000}),
    ("30%", replace(BASELINE, focused_term_id="prepayment_fraction"), {"prepayment_fraction": 0.3}),
    ("6 недель", replace(BASELINE, focused_term_id="delivery_weeks"), {"delivery_weeks": 6}),
    ("6", replace(BASELINE, focused_term_id=None, expected_term_id="delivery_weeks"), {"delivery_weeks": 6}),
    ("0 EUR", BASELINE, {"price": 0}),
])
def test_short_answers_use_structured_public_focus(message, context, expected):
    result = parse(message, context)
    assert result.action == "counter_offer", result
    assert result.terms_delta == expected


@pytest.mark.parametrize("message, context, reason", [
    ("105 тысяч", None, "numeric_answer_requires_term"),
    ("105000", ParseContext(), "numeric_answer_requires_term"),
    ("105000", replace(BASELINE, expected_term_id="prepayment_fraction"), "ambiguous_numeric_reference"),
    ("105000 USD", BASELINE, "currency_mismatch"),
    ("30", replace(BASELINE, focused_term_id="prepayment_fraction"), "numeric_answer_requires_unit"),
])
def test_ambiguous_short_answers_do_not_change_terms(message, context, reason):
    result = parse(message, context)
    assert result.action == "clarification", result
    assert result.reason_code == reason
    assert result.terms_delta == {}


@pytest.mark.parametrize("message", [
    "Почему вы думаете, что я принимаю предложение?",
    "Why do you think I accept the offer?",
    'Вы сказали «принимаю предложение».',
    'You said "I accept the offer".',
    "Вы отказываетесь от сделки?",
    "Should I walk away?",
])
def test_questions_or_quotes_cannot_commit_control_actions(message):
    result = parse(message)
    assert result.action in {"question", "inform", "clarification"}


def test_numeric_question_during_confirmation_does_not_propose_or_bind():
    result = parse("Почему цена 120000 EUR?", pending=True)
    assert result.action == "clarification"
    assert result.terms_delta == {}
    assert result.reason_code == "ambiguous_confirmation"


@pytest.mark.parametrize("kwargs", [
    {"active_offer_terms": {"price": True}},
    {"active_offer_terms": {"price": float("nan")}},
    {"active_offer_terms": {"price": float("inf")}},
    {"active_offer_terms": {str(index): index for index in range(13)}},
    {"active_offer_revision": True},
    {"active_offer_revision": -1},
])
def test_parse_context_rejects_nonfinite_or_unbounded_values(kwargs):
    with pytest.raises(ValueError):
        ParseContext(**kwargs)


def test_relative_zero_is_a_real_baseline_not_missing():
    result = parse(
        "Increase the price by EUR 10,000",
        replace(BASELINE, active_offer_terms={"price": 0}),
    )
    assert result.terms_delta == {"price": 10000}


@pytest.mark.parametrize("message", [
    "Не 105000 EUR.", "Not EUR 105,000.",
    "Я не согласен с ценой 105000 EUR.", "I do not agree with EUR 105,000.",
    "Цена 105000 EUR мне не подходит.", "EUR 105,000 does not work for us.",
    "Предоплата не 30%.", "Prepayment is not 30%.",
    "«цена 105000 EUR", '"EUR 105,000',
    "Не снижайте цену на 10000 EUR.", "Do not reduce the price by EUR 10,000.",
    "Вы снизили цену на 10000 EUR.", "You reduced the price by EUR 10,000.",
])
def test_negative_quoted_or_historical_edits_never_commit(message):
    result = parse(message)
    assert result.action in {"inform", "clarification"}, result
    assert result.terms_delta == {}


@pytest.mark.parametrize("message", [
    "Предлагаю предоплату 30% или 40%.", "I propose 30% or 40% prepayment.",
    "Предлагаю поставку за 6 недель или 8 недель.", "I propose 6 weeks or 8 weeks delivery.",
    "Предлагаю цену 105000 EUR плюс 5000 EUR.",
    "I propose EUR 105,000 plus EUR 5,000.",
    "Снизить цену на -10000 EUR.", "Reduce the price by EUR -10,000.",
    "Снизить цену в 2 раза.", "Divide the price by 2.",
    "Скидка 10000 EUR.", "A discount of EUR 10,000.",
    "Цена 105000 EUR без учета 20% налога.", "EUR 105,000 excluding 20% tax.",
])
def test_ambiguous_alternatives_and_unsupported_calculations_require_clarification(message):
    result = parse(message)
    assert result.action == "clarification", result
    assert result.terms_delta == {}


def test_relative_change_keeps_provenance_during_confirmation():
    result = parse("Снизить цену на 10000 EUR", pending=True)
    assert result.action == "counter_offer"
    assert result.terms_delta == {"price": 110000}
    assert result.details["baseline_offer_revision"] == 7
