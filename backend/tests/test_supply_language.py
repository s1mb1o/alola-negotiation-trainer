from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from backend.app.supply_language import (
    decide_supply_action,
    parse_supply_message,
    validate_supply_extraction,
)


@pytest.fixture
def opening() -> dict:
    return {
        "base_price": {"currency": "EUR", "minor_units": 12000000},
        "delivery_lots": [
            {
                "lot_id": "main",
                "quantity": 100,
                "window_start": "2026-11-26",
                "window_end": "2026-11-26",
            }
        ],
    }


@pytest.fixture
def split_terms() -> dict:
    return {
        "base_price": {"currency": "EUR", "minor_units": 10950000},
        "delivery_lots": [
            {
                "lot_id": "early",
                "quantity": 10,
                "window_start": "2026-11-05",
                "window_end": "2026-11-07",
            },
            {
                "lot_id": "remaining",
                "quantity": 90,
                "window_start": "2026-11-20",
                "window_end": "2026-11-20",
            },
        ],
        "payment_schedule": [
            {"lot_id": "early", "advance_bps": 10000, "balance_days": 0},
            {"lot_id": "remaining", "advance_bps": 5000, "balance_days": 0},
        ],
        "delivery_basis": {"basis": "DDP", "destination_id": "vector_site"},
        "reserve_policy": {"mode": "none"},
    }


@pytest.fixture
def scenario() -> dict:
    path = (
        Path(__file__).resolve().parents[2] / "examples" / "scenario_supplier_integration_ru.yaml"
    )
    return yaml.safe_load(path.read_text())["scenario"]


@pytest.mark.parametrize(
    "message",
    [
        "Как насчет 50% предоплаты?",
        "Вы можете снизить цену до 110000 EUR?",
        "Что если 50% аванса?",
        "What if we offer 50% advance?",
        "Could you deliver on November 10?",
        "Would you accept EUR 110000?",
        "Вы готовы обсуждать 50% аванса?",
        "Are you ready to pay 50%?",
        "Вы предлагали 115000 EUR",
        'You said "EUR 115000"',
    ],
)
def test_quantitative_question_or_quote_never_changes_package(opening: dict, message: str) -> None:
    before = deepcopy(opening)
    result = parse_supply_message(message, "ru", opening, 7)
    assert result.action in {"inform", "question"}
    assert result.terms is None
    assert result.source_revision == 7
    assert opening == before


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Предлагаю €109 500", 10950000),
        ("Цена 109500 евро", 10950000),
        ("We offer EUR 109500", 10950000),
        ("We offer €109,500", 10950000),
        ("We offer 109500.25 EUR", 10950025),
    ],
)
def test_money_is_exact_and_not_a_quantity(
    opening: dict, message: str, expected: int | None
) -> None:
    result = parse_supply_message(message, "en", opening, 1)
    if expected is None:
        assert result.terms is None
    else:
        assert result.action == "amend"
        assert result.terms["base_price"]["minor_units"] == expected
        assert result.terms["delivery_lots"] == opening["delivery_lots"]


@pytest.mark.parametrize(
    "message",
    [
        "Мы готовы внести 50% предоплаты при условии, что получим DDP 10 ноября",
        "We offer 50% advance provided delivery is DDP November 10",
    ],
)
def test_conditional_payment_and_delivery_materialize_atomically(
    opening: dict, message: str
) -> None:
    result = parse_supply_message(message, "ru", opening, 4)
    assert result.action == "amend"
    assert result.source_revision == 4
    assert result.terms["payment_schedule"] == [{"lot_id": "main", "advance_bps": 5000}]
    assert result.terms["delivery_lots"][0]["window_end"] == "2026-11-10"
    assert result.terms["delivery_basis"]["basis"] == "DDP"
    assert "reserve_policy" not in result.terms
    assert "payment_schedule" not in opening


@pytest.mark.parametrize(
    "message",
    [
        "Предлагаю цену 110000 EUR если вы оплатите рекламу",
        "Готовы внести 50% аванс, если проведете обучение",
        "We offer 50% advance if installation is included",
        "We propose 110000 EUR if sales exceed our forecast",
        "Представьте окончательное предложение 110000 EUR со штрафом",
        "Предлагаю 110000 EUR, включая монтаж",
        "Предлагаю скидку 5%",
        "Предлагаю 110000 USD",
        "Предлагаю 110000 EUR за единицу",
        "We offer 50% advance with delivery November 10, 2027",
    ],
)
def test_unknown_dependency_does_not_commit_a_known_subset(opening: dict, message: str) -> None:
    result = parse_supply_message(message, "ru", opening, 3)
    assert result.terms is None
    assert result.action == "inform"
    assert result.clarification
    assert result.clarification_code == "unsupported_composite_semantics"


@pytest.mark.parametrize(
    "message",
    [
        "Мы готовы внести 100% предоплаты за 10 единиц, чтобы завершить интеграцию, если сможем получить их в начале ноября, тогда остальные для нас приемлемо 20 ноября.",
        "We offer 100% advance for 10 units in early November, with the remaining 90 units on November 20.",
    ],
)
def test_split_preserves_the_remaining_lot_payment(opening: dict, message: str) -> None:
    opening["payment_schedule"] = [{"lot_id": "main", "advance_bps": 5000, "balance_days": 0}]
    result = parse_supply_message(message, "ru", opening, 4)
    assert result.action == "amend", result
    assert result.terms["delivery_lots"] == [
        {
            "lot_id": "early",
            "quantity": 10,
            "window_start": "2026-11-05",
            "window_end": "2026-11-07",
        },
        {
            "lot_id": "remaining",
            "quantity": 90,
            "window_start": "2026-11-20",
            "window_end": "2026-11-20",
        },
    ]
    assert result.terms["payment_schedule"] == [
        {"lot_id": "early", "advance_bps": 10000, "balance_days": 0},
        {"lot_id": "remaining", "advance_bps": 5000, "balance_days": 0},
    ]
    assert sum(lot["quantity"] for lot in result.terms["delivery_lots"]) == 100


@pytest.mark.parametrize("message", ["Мы предлагаем 75% аванса", "We offer 75% advance"])
def test_split_unspecified_payment_scope_requires_clarification(
    split_terms: dict, message: str
) -> None:
    result = parse_supply_message(message, "ru", split_terms, 8)
    assert result.terms is None
    assert result.clarification_code == "ambiguous_composite_scope"


@pytest.mark.parametrize(
    "message", ["Сохраним 50% аванса по остальным", "We keep 50% advance for the remaining lot"]
)
def test_remaining_advance_never_changes_first_lot(split_terms: dict, message: str) -> None:
    result = parse_supply_message(message, "ru", split_terms, 8)
    assert result.action == "amend"
    assert result.terms["payment_schedule"][0]["advance_bps"] == 10000
    assert result.terms["payment_schedule"][1]["advance_bps"] == 5000


@pytest.mark.parametrize(
    "message",
    [
        "Желательно иметь 3 устройства и быструю замену, после 1 декабря мы готовы оплатить лишние устройства, если они окажутся невостребованными",
        "We propose 3 reserve units with the remaining lot; after December 1 we will purchase unused units at the same unit price",
    ],
)
def test_reserve_is_extra_and_not_a_main_lot_change(split_terms: dict, message: str) -> None:
    result = parse_supply_message(message, "ru", split_terms, 8)
    assert result.action == "amend", result
    assert result.terms["delivery_lots"] == split_terms["delivery_lots"]
    reserve = result.terms["reserve_policy"]
    assert reserve["quantity"] == 3
    assert reserve["use_cutoff"] == "2026-12-01"
    assert reserve["unused_payable_on"] == "2026-12-02"


def test_inverted_diagnosis_is_not_committed(split_terms: dict) -> None:
    message = "Критерий: если после ремонта сбои прекращаются, считаем устройство платным; если сбой остается, это FOC"
    result = parse_supply_message(message, "ru", split_terms, 9)
    assert result.terms is None
    assert result.clarification_code == "unsupported_composite_semantics"


def test_inverse_verified_outcomes_cannot_become_the_opposite_authored_rule(
    split_terms: dict,
) -> None:
    result = parse_supply_message(
        "Подтвержденный аппаратный дефект оплачивается; причина в ПО означает бесплатную замену",
        "ru",
        split_terms,
        1,
    )
    assert result.terms is None
    assert result.clarification


def test_payment_scopes_do_not_depend_on_percentage_order(opening: dict) -> None:
    result = parse_supply_message(
        "Предлагаю 10 устройств в начале ноября, остальные 90 устройств 20 ноября; по остальным 50% аванса, по первым 100% аванса",
        "ru",
        opening,
        1,
    )
    assert result.action == "amend"
    assert result.terms["payment_schedule"] == [
        {"lot_id": "early", "advance_bps": 10000},
        {"lot_id": "remaining", "advance_bps": 5000},
    ]


def test_extractor_candidate_requires_exact_full_source_and_revision(opening: dict) -> None:
    message = "Предлагаем 110000 EUR"
    parsed = parse_supply_message(message, "ru", opening, 4)
    candidate = {
        "action": "amend",
        "terms": parsed.terms,
        "source_revision": 4,
        "source_text": message,
    }
    assert validate_supply_extraction(candidate, message, "ru", opening, 4) == parsed
    for changed in (
        {"source_revision": 3},
        {"source_text": "110000 EUR"},
        {"action": "publish"},
        {"terms": {"base_price": {"minor_units": 11000000}}},
    ):
        result = validate_supply_extraction(candidate | changed, message, "ru", opening, 4)
        assert result.terms is None
        assert result.clarification_code == "extraction_unavailable"


@pytest.mark.parametrize(
    "message",
    [
        "Не подтверждаю принятие предложения.",
        "I do not confirm acceptance of the offer.",
    ],
)
def test_current_ui_cancel_is_not_an_informative_turn(opening: dict, message: str) -> None:
    result = parse_supply_message(message, "ru", opening, 7, "accept_offer")
    assert result.action == "cancel"
    assert result.terms is None


@pytest.mark.parametrize(
    "message",
    [
        "We propose 110000 EUR if our board approves a 50% advance for all lots.",
        "Предлагаем 110000 EUR, если наш совет утвердит 50% аванс для всех партий.",
        "We propose 110000 EUR if our accountant approves delivery on November 10.",
        "We propose 110000 EUR if delivery is DDP November 10 and our boss agrees.",
        "We propose 110000 EUR unless delivery is DDP November 10.",
    ],
)
def test_a_known_number_cannot_hide_an_unmodeled_condition(opening: dict, message: str) -> None:
    result = parse_supply_message(message, "ru", opening, 5)
    assert result.terms is None
    assert result.clarification_code == "unsupported_composite_semantics"


@pytest.mark.parametrize(
    "message,expected",
    [
        ("The balance for the first lot is due 30 days after delivery.", [30, 0]),
        ("Остаток по первой партии оплачивается через 30 дней после поставки.", [30, 0]),
        ("По первой партии остаток оплачивается через 30 дней после поставки.", [30, 0]),
        ("The balance for the remaining lot is due 30 days after delivery.", [0, 30]),
    ],
)
def test_balance_delay_preserves_the_untargeted_lot(
    split_terms: dict, message: str, expected: list[int]
) -> None:
    result = parse_supply_message(message, "ru", split_terms, 3)
    assert result.action == "amend", result
    assert [item["balance_days"] for item in result.terms["payment_schedule"]] == expected
    assert [item["advance_bps"] for item in result.terms["payment_schedule"]] == [10000, 5000]


def test_especially_is_not_an_all_lots_payment_scope(split_terms: dict) -> None:
    result = parse_supply_message(
        "Yes, we can keep 50% advance. We are flexible on this point, especially for a better price.",
        "en",
        split_terms,
        3,
    )
    assert result.action == "amend"
    assert [item["advance_bps"] for item in result.terms["payment_schedule"]] == [10000, 5000]


@pytest.mark.parametrize(
    "message",
    [
        "We propose 110000 EUR, balance 60 days after delivery.",
        "Предлагаем 110000 EUR, остаток через 60 дней после поставки.",
        "We propose 110000 EUR and 30 chairs.",
        "Предлагаю 3 резервных устройства, неиспользованные выкупим после 3 декабря.",
    ],
)
def test_unrepresented_numeric_term_invalidates_the_whole_amendment(
    split_terms: dict, message: str
) -> None:
    result = parse_supply_message(message, "ru", split_terms, 4)
    assert result.terms is None
    assert result.clarification_code == "unsupported_composite_semantics"


@pytest.mark.parametrize(
    "message",
    [
        "Предлагаю 3 резервных устройства вместе с первой партией.",
        "We propose 3 reserve units with the first lot.",
    ],
)
def test_reserve_delivery_refers_to_the_named_first_lot(split_terms: dict, message: str) -> None:
    result = parse_supply_message(message, "ru", split_terms, 4)
    assert result.action == "amend", result
    assert result.terms["reserve_policy"]["delivery_lot_id"] == "early"


@pytest.mark.parametrize(
    "message",
    [
        "Еще мы хотели обсудить % Free of Charge на случай брака",
        "We would like to discuss the Free of Charge percentage for defective units",
    ],
)
def test_free_of_charge_discussion_is_a_question_not_a_parser_error(
    split_terms: dict, message: str
) -> None:
    result = parse_supply_message(message, "ru", split_terms, 4)
    assert result.action == "question"
    assert result.clarification is None
    assert result.terms is None


@pytest.mark.parametrize(
    "message,kind,expected",
    [
        ("Подтверждаю окончательное предложение", "publish_offer", "confirm_publication"),
        ("I confirm the final offer", "publish_offer", "confirm_publication"),
        ("I confirm the final offer", None, "inform"),
        (
            "Подтверждаю принятие полного предложения без дополнительных условий",
            "accept_offer",
            "confirm_acceptance",
        ),
        (
            "I confirm acceptance of the complete offer without additional conditions",
            "accept_offer",
            "confirm_acceptance",
        ),
        (
            "I confirm acceptance of the complete offer without additional conditions",
            "publish_offer",
            "inform",
        ),
        ("Принимаю полное предложение без дополнительных условий", None, "accept"),
        ("I accept the complete offer without additional conditions", None, "accept"),
        ("Отменяю подтверждение", "publish_offer", "cancel"),
        ("I cancel confirmation", "accept_offer", "cancel"),
        ("Покажите окончательное предложение", None, "publish"),
        ("Please present your final offer", None, "publish"),
        ("What does final offer mean?", None, "question"),
    ],
)
def test_protocol_language_is_pending_kind_bound(
    opening: dict, message: str, kind: str | None, expected: str
) -> None:
    result = parse_supply_message(message, "ru", opening, 11, kind)
    assert result.action == expected
    assert result.source_revision == 11
    assert result.terms is None


def test_final_request_with_new_price_is_only_preliminary_amendment(opening: dict) -> None:
    result = parse_supply_message("Предлагаю окончательный пакет за 110000 EUR", "ru", opening, 4)
    assert result.action == "amend"
    assert result.terms["base_price"]["minor_units"] == 11000000


def test_complete_preliminary_is_never_accepted(scenario: dict, split_terms: dict) -> None:
    result = decide_supply_action(scenario, "seller", split_terms, "Да, согласен", "ru")
    assert result.action == "inform"
    assert "предваритель" in result.text


def test_explicit_final_request_publishes_only_complete_acceptable_package(
    scenario: dict, split_terms: dict, opening: dict
) -> None:
    final = decide_supply_action(
        scenario, "seller", split_terms, "Покажите окончательное предложение", "ru"
    )
    assert final.action == "publish"
    assert final.terms == split_terms
    incomplete = decide_supply_action(
        scenario, "seller", opening, "Покажите окончательное предложение", "ru"
    )
    assert incomplete.action == "inform"
    assert incomplete.terms is None


@pytest.mark.parametrize("role", ["buyer", "seller"])
def test_formal_acceptance_reads_no_counterpart_utility(
    scenario: dict, split_terms: dict, role: str
) -> None:
    other = "buyer" if role == "seller" else "seller"
    original = decide_supply_action(
        scenario, role, split_terms, "Published", "en", formal=True, proposer_role=other
    )
    scenario["utility_model"]["role_models"][other] = {"must_not_be_read": object()}
    scenario["supply_model"]["economics"][other] = {"must_not_be_read": object()}
    result = decide_supply_action(
        scenario, role, split_terms, "Published", "en", formal=True, proposer_role=other
    )
    assert result == original
    assert result.action == "accept"


def test_formal_question_does_not_accept(scenario: dict, split_terms: dict) -> None:
    result = decide_supply_action(
        scenario,
        "seller",
        split_terms,
        "What does the reserve cover?",
        "en",
        formal=True,
        proposer_role="buyer",
    )
    assert result.action == "inform"


def test_concession_depends_on_structure_not_repeated_turns(scenario: dict, opening: dict) -> None:
    first = decide_supply_action(
        scenario,
        "seller",
        opening,
        "Предложение выходит за бюджет, можно оптимизировать стоимость?",
        "ru",
    )
    assert first.action == "propose"
    assert first.terms["base_price"]["minor_units"] == 11500000
    assert "payment_schedule" not in first.terms
    again = decide_supply_action(scenario, "seller", first.terms, "Нужно снизить цену", "ru")
    assert again.action == "inform"
    assert again.terms is None


def test_progressive_reference_has_exact_split_and_bounded_price(
    scenario: dict, opening: dict
) -> None:
    terms = opening
    messages = [
        "Предложение выходит за бюджет, можно оптимизировать стоимость?",
        "Мы готовы внести 50% предоплаты при условии, что получим DDP 10 ноября",
        "Мы готовы внести 100% предоплаты за 10 единиц в начале ноября, остальные 90 единиц до 20 ноября",
        "Желательно иметь 3 устройства и быструю замену, после 1 декабря мы готовы оплатить лишние устройства, если они окажутся невостребованными",
    ]
    for revision, message in enumerate(messages, 1):
        action = parse_supply_message(message, "ru", terms, revision)
        assert action.clarification is None, action
        if action.terms is not None:
            terms = action.terms
        decision = decide_supply_action(
            scenario, "seller", terms, message, "ru", proposer_role="buyer"
        )
        assert decision.action not in {"publish", "accept"}
        if decision.terms is not None:
            terms = decision.terms
    assert terms["base_price"]["minor_units"] == 10950000
    assert terms["payment_schedule"][0]["advance_bps"] == 10000
    assert terms["payment_schedule"][1]["advance_bps"] == 5000
    assert terms["reserve_policy"]["quantity"] == 3
    assert terms["reserve_policy"]["diagnosis_policy_id"] == "hardware-replacement-v1"
