"""Offline reference conversations through the real authenticated Player API.

These tests verify negotiation semantics. They do not rate LLM naturalness.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import uuid

import pytest
import yaml

from backend.app.supply import (
    evaluate_supply_utility,
    supply_constraint_violations,
    supply_financial_summary,
    validate_supply_terms,
)
from backend.tests.conftest import bearer, create_payload, credentials


REFERENCE = {
    "ru": {
        "budget": "Добрый день, да, качество нас устраивает полностью, но к сожалению данное предложение выходит за выделенный мне бюджет, имеется ли возможность оптимизировать стоимость? С уважением, Александр",
        "advance_question": "У нас есть возможность предложить вам оплату части продукта авансом, на сколько это будет вам интересно?",
        "advance": "Мы готовы внести предоплату 50%, при условии что получим DDP 10 ноября",
        "split": "Мы готовы внести 100% предоплаты за 10 единиц, чтобы завершить интеграцию, если сможем получить их в начале ноября, тогда остальные для нас приемлемо 20 ноября.",
        "keep": "Да, мы можем сохранить 50% предоплаты, мы достаточно гибки в этом вопросе, особенно при хорошей цене",
        "reserve_question": "Еще мы хотели обсудить % Free of Charge на случай брака",
        "reserve": "Желательно иметь 3 устройства и быструю замену, после 1 декабря мы готовы оплатить лишние устройства если они окажутся невостребованными",
        "ambiguous": "Критерием может служить невозможность стабильной работы нашей системы, далее мы берем устройство из FOC, а вы забираете засбоившее устройство для диагностики, по результатам вашей диагностики или исправления если сбои прекращаются — считаем что это устройство требует оплаты, если сбой остается — это FOC",
        "criterion": "Предлагаю такой критерий: подтвержденная аппаратная неисправность или ваш ремонт означают бесплатную замену; подтвержденная причина в ПО, конфигурации или инфраструктуре покупателя означает оплату резерва.",
        "publish": "Публикую окончательное предложение",
        "confirm_publish": "Подтверждаю окончательное предложение",
        "accept": "Принимаю полное предложение без дополнительных условий",
        "confirm_accept": "Подтверждаю принятие полного предложения без дополнительных условий",
    },
    "en": {
        "budget": "Good afternoon. The quality meets our needs, but this proposal exceeds my allocated budget. Is there a way to reduce the price? Regards, Alexander",
        "advance_question": "We can offer advance payment for part of the order. Would that interest you?",
        "advance": "We offer 50% advance provided delivery is DDP November 10",
        "split": "We offer 100% advance for 10 units in early November, with the remaining 90 units on November 20.",
        "keep": "Yes, we can keep 50% advance. We are flexible on this point, especially for a better price.",
        "reserve_question": "We would also like to discuss Free of Charge reserve units for defects.",
        "reserve": "We propose 3 reserve units with the remaining lot; after December 1 we will purchase unused units at the same unit price",
        "ambiguous": "For diagnosis, we take a reserve if our system is unstable and you collect the original. If the problem stops after repair the reserve is payable; if the problem remains it is free.",
        "criterion": "We propose this diagnosis criterion: a confirmed hardware fault or your repair means a free replacement; a confirmed buyer-side software, configuration, or infrastructure cause means the reserve is payable.",
        "publish": "Publish my final offer",
        "confirm_publish": "I confirm the final offer",
        "accept": "I accept the complete offer without additional conditions",
        "confirm_accept": "I confirm acceptance of the complete offer without additional conditions",
    },
}


def _scenario(language):
    path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / f"scenario_supplier_integration_{language}.yaml"
    )
    return yaml.safe_load(path.read_text())["scenario"]


def _create(client, language, human_role="buyer"):
    payload = create_payload(
        uuid.uuid4().hex, difficulty="easy", language=language, human_role=human_role
    )
    payload.update(scenario_id=f"supplier_integration_{language}", scenario_version=1)
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _send(client, session, token, message):
    route = f"/api/v1/sessions/{session['session_id']}"
    current = client.get(route, headers=bearer(token))
    assert current.status_code == 200, current.text
    response = client.post(
        route + "/messages",
        headers=bearer(token),
        json={
            "message": message,
            "expected_revision": current.json()["revision"],
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("language", ["ru", "en"])
def test_user_reference_progressively_constructs_a_safe_complete_deal(client, settings, language):
    assert settings.npc_provider == "template"
    scenario = _scenario(language)
    text = REFERENCE[language]
    session = _create(client, language)
    token = credentials(session)["buyer"]
    opening = session["observation"]["current_public_terms"]
    assert set(opening) == {"base_price", "delivery_lots"}
    assert "0%" not in session["observation"]["conversation"][0]["message"]

    budget = _send(client, session, token, text["budget"])
    price = budget["observation"]["current_public_terms"]["base_price"]["minor_units"]
    assert price in scenario["supply_model"]["npc_policy"]["price_candidates_minor"]
    assert price < opening["base_price"]["minor_units"]
    before = deepcopy(budget["observation"]["current_public_terms"])
    question = _send(client, session, token, text["advance_question"])
    assert question["observation"]["current_public_terms"] == before

    advance = _send(client, session, token, text["advance"])
    terms = advance["observation"]["current_public_terms"]
    assert terms["payment_schedule"] == [{"lot_id": "main", "advance_bps": 5000, "balance_days": 0}]
    assert terms["delivery_basis"] == {"basis": "DDP", "destination_id": "vector_site"}
    assert terms["delivery_lots"][0]["window_end"] == "2026-11-10"
    assert "reserve_policy" not in terms
    assert advance["status"] == "active" and advance["observation"]["active_offers"] == []

    split = _send(client, session, token, text["split"])
    terms = split["observation"]["current_public_terms"]
    assert [lot["quantity"] for lot in terms["delivery_lots"]] == [10, 90]
    assert terms["delivery_lots"][0]["window_start"] == "2026-11-05"
    assert terms["delivery_lots"][0]["window_end"] == "2026-11-07"
    assert terms["delivery_lots"][1]["window_end"] == "2026-11-20"
    assert [payment["advance_bps"] for payment in terms["payment_schedule"]] == [10000, 5000]
    kept = _send(client, session, token, text["keep"])
    assert [
        entry["advance_bps"]
        for entry in kept["observation"]["current_public_terms"]["payment_schedule"]
    ] == [10000, 5000]

    before = deepcopy(kept["observation"]["current_public_terms"])
    reserve_question = _send(client, session, token, text["reserve_question"])
    assert reserve_question["observation"]["current_public_terms"] == before
    assert reserve_question["result"] != "clarification_required"
    assert reserve_question["observation"]["conversation"][-1]["role"] == "seller"
    reserve = _send(client, session, token, text["reserve"])
    terms = reserve["observation"]["current_public_terms"]
    assert terms["reserve_policy"]["quantity"] == 3
    assert terms["reserve_policy"]["delivery_lot_id"] == "remaining"
    assert terms["reserve_policy"]["unused_payable_on"] == "2026-12-02"
    assert sum(lot["quantity"] for lot in terms["delivery_lots"]) == 100
    assert reserve["status"] == "active" and reserve["observation"]["active_offers"] == []

    before = deepcopy(terms)
    ambiguous = _send(client, session, token, text["ambiguous"])
    assert ambiguous["result"] == "clarification_required"
    assert ambiguous["observation"]["current_public_terms"] == before
    assert ambiguous["status"] == "active"
    clarified = _send(client, session, token, text["criterion"])
    assert clarified["result"] in {"committed", "turn_committed"}, clarified
    terms = clarified["observation"]["current_public_terms"]
    assert terms["reserve_policy"]["diagnosis_policy_id"] == "hardware-replacement-v1"
    assert validate_supply_terms(scenario, terms, complete=True) == []
    assert supply_constraint_violations(scenario, "buyer", terms) == []
    assert supply_constraint_violations(scenario, "seller", terms) == []
    assert supply_financial_summary(scenario, terms)["weighted_advance_fraction"] == 0.55
    assert (
        evaluate_supply_utility(scenario, "seller", terms)
        >= scenario["utility_model"]["role_models"]["seller"]["reservation_utility"]
    )
    assert clarified["status"] == "active" and clarified["observation"]["active_offers"] == []

    # Explicitly establish one final snapshot. NPC presentation is not acceptance.
    final = _send(client, session, token, text["publish"])
    assert final["status"] == "active"
    if final.get("pending_offer_publication"):
        snapshot = final["pending_offer_publication"]["terms"]
        assert snapshot == terms
        completed = _send(client, session, token, text["confirm_publish"])
    else:
        assert final["observation"]["active_offers"]
        assert final["observation"]["active_offers"][0]["terms"] == terms
        intent = _send(client, session, token, text["accept"])
        assert intent["status"] == "active" and intent["confirmation_kind"] == "accept_offer"
        completed = _send(client, session, token, text["confirm_accept"])
    assert completed["status"] == "agreement_reached", completed

    route = f"/api/v1/sessions/{session['session_id']}"
    history = client.get(route + "/history", headers=bearer(token))
    assert history.status_code == 200
    public_history = json.dumps(history.json(), ensure_ascii=False)
    assert text["ambiguous"] in public_history
    assert "proposal.revised" in public_history and "agreement.reached" in public_history
    assert "base_cost_minor" not in public_history and "npc_policy" not in public_history
    review = client.get(route + "/review", headers=bearer(token))
    assert review.status_code == 200, review.text
    assert review.json()["outcome"]["agreement"] is True


@pytest.mark.parametrize("language", ["ru", "en"])
def test_buyer_npc_uses_same_complete_package_and_explicit_publication(client, settings, language):
    assert settings.npc_provider == "template"
    session = _create(client, language, human_role="seller")
    token = credentials(session)["seller"]
    message = (
        "Предлагаем 109500 EUR за 100 устройств, 10 устройств в начале ноября со 100% авансом, остальные 90 устройств 20 ноября с 50% авансом, остаток при поставке, DDP, без резерва."
        if language == "ru"
        else "We propose 109500 EUR for 100 devices, 10 devices in early November with 100% advance, remaining 90 devices on November 20 with 50% advance, balance on delivery, DDP, no reserve."
    )
    proposed = _send(client, session, token, message)
    assert proposed["status"] == "active"
    terms = proposed["observation"]["current_public_terms"]
    assert proposed["observation"]["active_offers"] == []
    assert validate_supply_terms(_scenario(language), terms, complete=True) == []
    pending = _send(client, session, token, REFERENCE[language]["publish"])
    assert pending["status"] == "active"
    assert pending["confirmation_kind"] == "publish_offer"
    assert pending["pending_offer_publication"]["terms"] == terms
    completed = _send(client, session, token, REFERENCE[language]["confirm_publish"])
    assert completed["status"] == "agreement_reached", completed
