"""DR-58: evaluate the stated package and retain the delivered question context."""

from dataclasses import replace

import pytest

from backend.app.engine import ParseContext, clarification_text, parse_message
from .conftest import bearer, create_payload


TERMS = {"annual_rent": {}, "prepayment_fraction": {}, "office_readiness_weeks": {}}
CONTEXT = ParseContext(
    active_offer_id="off_public", active_offer_revision=3, active_offer_currency="RUB",
    active_offer_terms={"annual_rent": 2850000, "prepayment_fraction": 0.5, "office_readiness_weeks": 10},
    focused_term_id="prepayment_fraction", expected_term_id="annual_rent",
)


def parse(message, context=CONTEXT):
    return parse_message(message, TERMS, pending_confirmation=False, scenario_currency="RUB", context=context)


def test_latest_delivered_question_takes_precedence_over_previous_focus():
    result = parse("2 600 000")
    assert result.action == "counter_offer"
    assert result.terms_delta == {"annual_rent": 2600000}
    assert parse("60", replace(CONTEXT, expected_term_id="prepayment_fraction")).reason_code == "numeric_answer_requires_unit"


@pytest.mark.parametrize("message", [
    "Предлагаю годовую аренду 2600000 рублей. Предоплата 60%.",
    "I propose annual rent of 2600000 RUB. Prepayment 60%.",
    "Готов увеличить предоплату до 60% и снизить годовую аренду до 2600000 рублей.",
    "Increase prepayment to 60% and reduce annual rent to 2600000 RUB.",
    "Предоплата 60%; предлагаю снизить годовую аренду до 2600000 рублей.",
    "Prepayment 60%; reduce annual rent to 2600000 RUB.",
    "Согласен на предоплату 60% при годовой аренде 2600000 рублей.",
    "I accept prepayment 60% with annual rent 2600000 RUB.",
])
def test_all_asserted_terms_form_one_package_not_acceptance(message):
    result = parse(message)
    assert result.action == "counter_offer", result
    assert result.terms_delta == {"annual_rent": 2600000, "prepayment_fraction": 0.6}


@pytest.mark.parametrize("message", [
    "Предлагаю аренду 2600000 рублей, предоплату 60% или готовность через 3 недели.",
    "I propose rent 2600000 RUB, prepayment 60% or readiness in 3 weeks.",
    "Увеличить предоплату до 60% или снизить аренду до 2600000 рублей.",
    "Increase prepayment to 60% or reduce rent to 2600000 RUB.",
])
def test_alternatives_are_not_silently_combined(message):
    assert parse(message).reason_code == "multiple_offer_candidates"


@pytest.mark.parametrize("message", [
    "Предлагаю аренду 2600000 рублей. Почему предоплата 60%?",
    'I propose rent 2600000 RUB. You said "prepayment 60%".',
    "Предлагаю аренду 2600000 рублей. Я не предлагаю предоплату 60%.",
])
def test_questions_quotes_and_negation_do_not_supply_secondary_terms(message):
    assert parse(message).terms_delta == {"annual_rent": 2600000}


@pytest.mark.parametrize("language", ["ru", "en"])
@pytest.mark.parametrize("reason", [
    "numeric_answer_requires_term", "numeric_answer_requires_unit", "ambiguous_numeric_reference",
    "relative_change_requires_baseline", "ambiguous_relative_change", "unsupported_term_value",
])
def test_numeric_clarifications_do_not_ask_about_acceptance(language, reason):
    text = clarification_text(language, reason)
    assert "принимаете" not in text and "accept" not in text
    assert text != clarification_text(language, "ambiguous_agreement_scope")


def create_office(client, language="ru"):
    payload = create_payload("context-package-" + language, language=language)
    payload.update(scenario_id="office_lease_" + language, scenario_version=4)
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def send(client, session, token, message):
    response = client.post(f"/api/v1/sessions/{session['session_id']}/messages", headers=bearer(token), json={
        "message": message, "expected_revision": session["revision"],
        "idempotency_key": "context-turn-" + str(session["revision"]),
    })
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("language", ["ru", "en"])
def test_partial_proposal_questions_and_short_answers_survive_get(client, language):
    session = create_office(client, language)
    token = session["participant_token"]
    session = send(client, session, token, "Отклоняю предложение" if language == "ru" else "I reject the offer")
    session = send(client, session, token, "Предлагаю предоплату 60%" if language == "ru" else "I offer prepayment 60%")
    npc = session["committed_actions"][-1]
    assert "аренд" in npc["message"] if language == "ru" else "rent" in npc["message"]
    restored = client.get(f"/api/v1/sessions/{session['session_id']}", headers=bearer(token)).json()
    session = send(client, restored, token, "2 600 000")
    assert session.get("clarification") is None
    terms = session["observation"]["active_offers"][0]["terms"]
    assert terms == {"annual_rent": 2600000, "prepayment_fraction": 0.6}
    assert session["status"] == "active"


@pytest.mark.parametrize("language", ["ru", "en"])
def test_counteroffer_identifies_changed_and_retained_terms(client, language):
    session = create_office(client, language)
    reply = send(client, session, session["participant_token"],
                 "Предлагаю годовую аренду 1800000 рублей. Предоплата 60%. Готовность через 1 неделю."
                 if language == "ru" else "I propose annual rent 1800000 RUB. Prepayment 60%. Readiness in 1 week.")
    assert reply.get("clarification") is None
    counter = reply["committed_actions"][-1]
    assert counter["action"] == "counter_offer"
    terms = reply["observation"]["active_offers"][0]["terms"]
    assert terms["prepayment_fraction"] == 0.6
    assert terms["annual_rent"] == 2100000
    assert "изменить" in counter["message"] if language == "ru" else "need to change" in counter["message"]
    assert "сохраняются" in counter["message"] if language == "ru" else "retains" in counter["message"]


def test_numeric_clarification_is_specific_after_reload(client):
    session = create_office(client)
    token = session["participant_token"]
    reply = send(client, session, token, "Снизить предоплату на 5%")
    assert reply["clarification"]["reason_code"] == "ambiguous_relative_change"
    restored = client.get(f"/api/v1/sessions/{session['session_id']}", headers=bearer(token)).json()
    assert restored["clarification"]["question"] == reply["clarification"]["question"]
    assert "итоговый процент" in restored["clarification"]["question"]


def test_rejection_names_supported_objection_without_disclosing_private_limit(client, monkeypatch):
    # Exercise the wording branch when no counterproposal is available.
    monkeypatch.setattr("backend.app.service.select_counterproposal", lambda *args, **kwargs: None)
    payload = create_payload("context-rejection")
    payload.update(scenario_id="freight_contract_ru", scenario_version=3)
    session = client.post("/api/v1/sessions", json=payload).json()
    reply = send(client, session, session["participant_token"], "Предлагаю цену 340000 рублей.")
    rejection = reply["committed_actions"][-1]
    assert rejection["action"] == "reject"
    assert "не подходят условия: цена" in rejection["message"]
    assert "минимальн" not in rejection["message"]
    assert "reservation" not in rejection["message"]
