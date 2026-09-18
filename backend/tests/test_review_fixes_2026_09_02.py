"""Regression tests for the defects found in the 2026-09-02 review."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.engine import expand_numbers, parse_message

from .conftest import SCENARIO_ID, bearer, create_payload, credentials

TERMS = {"price": {}, "prepayment_fraction": {}, "delivery_weeks": {}}


def _create(client: TestClient, key: str, **kwargs: object) -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/api/v1/sessions",
        headers=bearer("test-admin"),
        json=create_payload(key, **kwargs),  # type: ignore[arg-type]
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    return body, credentials(body)


def _send(client: TestClient, session: dict, token: str, revision: int, message: str, key: str):
    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/messages",
        headers=bearer(token),
        json={"message": message, "idempotency_key": key, "expected_revision": revision},
    )
    return response.status_code, response.json()


def _active_offer(client: TestClient, session: dict, token: str) -> dict | None:
    observation = client.get(
        f"/api/v1/sessions/{session['session_id']}/observation", headers=bearer(token)
    ).json()
    offers = observation["active_offers"]
    return offers[0] if offers else None


# --- parser -----------------------------------------------------------------


def test_number_words_and_abbreviations_expand_to_digits() -> None:
    assert expand_numbers("110 тыс. евро") == "110000 евро"
    assert expand_numbers("1,2 млн рублей") == "1200000 рублей"
    assert expand_numbers("сто десять тысяч евро") == "110000 евро"
    assert expand_numbers("one point") == "1 point"
    parsed = parse_message(
        "Предлагаю сто десять тысяч евро, предоплата тридцать процентов, поставка шесть недель.",
        TERMS,
        pending_confirmation=False,
        scenario_currency="EUR",
    )
    assert parsed.action == "counter_offer"
    assert parsed.terms_delta == {"price": 110000, "prepayment_fraction": 0.3, "delivery_weeks": 6}
    parsed = parse_message(
        "Готовы дать 110 тыс. евро, предоплата 30 %, срок 6 нед.",
        TERMS,
        pending_confirmation=False,
        scenario_currency="EUR",
    )
    assert parsed.terms_delta == {"price": 110000, "prepayment_fraction": 0.3, "delivery_weeks": 6}
    parsed = parse_message(
        "Поставку всего заказа в течение шести полных недель при цене 110 000 евро.",
        TERMS,
        pending_confirmation=False,
        scenario_currency="EUR",
    )
    assert parsed.terms_delta["delivery_weeks"] == 6


def test_natural_acceptance_phrases_are_acceptance_intents() -> None:
    for message in (
        "Принимаю ваше предложение целиком.",
        "Принимаю всё предложение целиком.",
        "Согласны на ваше встречное предложение.",
        "Договорились, принимаем ваши условия.",
        "We accept your offer.",
        "I agree to all of your terms.",
    ):
        assert parse_message(message, TERMS, pending_confirmation=False).action == (
            "acceptance_intent"
        ), message
    assert parse_message(
        "Не принимаю ваше предложение.", TERMS, pending_confirmation=False
    ).action == ("inform")
    conditional = parse_message(
        "Принимаю предложение, если цена 1 250 000 рублей.",
        TERMS,
        pending_confirmation=False,
        scenario_currency="RUB",
    )
    assert conditional.action == "counter_offer"
    assert conditional.terms_delta == {"price": 1250000}
    for message in ("Согласен.", "Договорились.", "Ok!"):
        parsed = parse_message(message, TERMS, pending_confirmation=False)
        assert parsed.action == "clarification", message
        assert parsed.reason_code == "ambiguous_agreement_scope"


def test_negated_walk_away_is_not_a_walk_away() -> None:
    parsed = parse_message(
        "Мы не уйдём из переговоров и не скажем, что сделки не будет. "
        "Предлагаю цена 1 200 000 рублей, предоплата 50%, срок 8 недель.",
        TERMS,
        pending_confirmation=False,
        scenario_currency="RUB",
    )
    assert parsed.action == "counter_offer"
    assert parse_message(
        "There is no deal-breaker here.", TERMS, pending_confirmation=False
    ).action == ("inform")
    assert (
        parse_message("Сделки не будет.", TERMS, pending_confirmation=False).action == "walk_away"
    )
    assert parse_message("We walk away.", TERMS, pending_confirmation=False).action == "walk_away"


# --- binding integrity ----------------------------------------------------


def test_conditional_acceptance_during_pending_confirmation_is_a_real_counteroffer(
    client: TestClient,
) -> None:
    session, tokens = _create(client, "c1-conditional", both_external=True, hints_enabled=False)
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        session["revision"],
        "Предлагаю пакет: цена 1 200 000 рублей, предоплата 50%, срок 8 недель.",
        "c1-offer",
    )
    assert status == 200 and body["result"] == "turn_committed"
    status, body = _send(
        client, session, tokens["seller"], body["revision"], "Принимаю предложение.", "c1-intent"
    )
    assert status == 200 and body["result"] == "confirmation_required"
    status, body = _send(
        client,
        session,
        tokens["seller"],
        body["revision"],
        "Принимаю предложение, если цена 1 250 000 рублей.",
        "c1-conditional",
    )
    assert status == 200 and body["result"] == "turn_committed"
    offer = _active_offer(client, session, tokens["buyer"])
    assert offer is not None
    assert offer["proposer_role"] == "seller"
    assert offer["terms"]["price"] == 1250000


def test_builtin_npc_never_binds_above_the_counterpart_hard_constraint(
    client: TestClient,
) -> None:
    session, tokens = _create(client, "h2-cap", hints_enabled=False)
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        session["revision"],
        "Предлагаю пакет: цена 1 300 000 рублей, предоплата 50%, срок 8 недель.",
        "h2-offer",
    )
    assert status == 200
    assert body["status"] != "agreement_reached"
    npc_actions = [
        action
        for action in body["committed_actions"]
        if action["action"] != "counter_offer" or action["participant_id"].endswith("_seller")
    ]
    assert all(action["action"] != "accept" for action in npc_actions)


def test_natural_acceptance_reaches_confirmation_and_restating_terms_does_not_bind(
    client: TestClient,
) -> None:
    session, tokens = _create(client, "h1-accept", hints_enabled=False)
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        session["revision"],
        "Предлагаю пакет: цена 950 000 рублей, предоплата 50%, срок 8 недель.",
        "h1-lowball",
    )
    assert status == 200 and body["status"] == "active"
    counter = _active_offer(client, session, tokens["buyer"])
    assert counter is not None and counter["proposer_role"] == "seller"
    terms = counter["terms"]
    restated = (
        f"Принимаем: {terms['price']:,} рублей, предоплата "
        f"{int(terms['prepayment_fraction'] * 100)}%, срок {terms['delivery_weeks']} недель."
    ).replace(",", " ")
    status, body = _send(client, session, tokens["buyer"], body["revision"], restated, "h1-restate")
    assert status == 200 and body["result"] == "confirmation_required", body
    assert body["pending_confirmation"]["terms"] == terms
    status, body = _send(
        client, session, tokens["buyer"], body["revision"], "Подтверждаю принятие.", "h1-confirm"
    )
    assert status == 200 and body["status"] == "agreement_reached"

    # A natural acceptance phrase must reach the same confirmation step.
    session, tokens = _create(client, "h1-natural", hints_enabled=False)
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        session["revision"],
        "Предлагаю пакет: цена 950 000 рублей, предоплата 50%, срок 8 недель.",
        "h1-natural-lowball",
    )
    assert status == 200 and body["status"] == "active"
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        body["revision"],
        "Принимаю ваше предложение целиком.",
        "h1-natural-accept",
    )
    assert status == 200 and body["result"] == "confirmation_required"
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        body["revision"],
        "Подтверждаю принятие.",
        "h1-natural-confirm",
    )
    assert status == 200 and body["status"] == "agreement_reached"


def test_reject_requires_the_recipient(client: TestClient) -> None:
    session, tokens = _create(client, "l2-reject", both_external=True, hints_enabled=False)
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        session["revision"],
        "Предлагаю пакет: цена 1 200 000 рублей, предоплата 50%, срок 8 недель.",
        "l2-offer",
    )
    assert status == 200
    status, body = _send(
        client, session, tokens["seller"], body["revision"], "Мне нужно подумать.", "l2-pass"
    )
    assert status == 200 and body["result"] == "turn_committed"
    status, body = _send(
        client, session, tokens["buyer"], body["revision"], "Отклоняю предложение.", "l2-own"
    )
    assert status == 409 and body["error"] == "offer_not_owned"


# --- rounds and expiry ------------------------------------------------------


def test_external_sessions_expire_at_max_rounds(client: TestClient) -> None:
    session, tokens = _create(client, "h4-external", both_external=True, hints_enabled=False)
    revision = session["revision"]
    actor = "buyer"
    messages = 0
    status_value = "active"
    while status_value == "active" and messages < 60:
        status, body = _send(
            client, session, tokens[actor], revision, f"Комментарий {messages}.", f"h4-{messages}"
        )
        assert status == 200, body
        revision = body["revision"]
        status_value = body["status"]
        actor = "seller" if actor == "buyer" else "buyer"
        messages += 1
    assert status_value == "expired"
    assert messages == 24


def test_npc_gets_no_extra_action_after_the_human_completes_the_last_round(
    client: TestClient,
) -> None:
    session, tokens = _create(client, "h4-npc", hints_enabled=False, human_role="seller")
    revision = session["revision"]
    last_body: dict = {}
    for index in range(40):
        status, body = _send(
            client,
            session,
            tokens["seller"],
            revision,
            f"Уточняем детали {index}.",
            f"h4-npc-{index}",
        )
        assert status == 200, body
        revision = body["revision"]
        last_body = body
        if body["status"] != "active":
            break
    assert last_body["status"] == "expired"
    human_actions = [
        action
        for action in last_body["committed_actions"]
        if action["participant_id"].endswith("_seller")
    ]
    npc_actions = [
        action
        for action in last_body["committed_actions"]
        if action["participant_id"].endswith("_buyer")
    ]
    assert len(human_actions) == 1
    assert npc_actions == []


# --- NPC conversation -------------------------------------------------------


def test_npc_answers_questions_while_the_player_offer_is_incomplete(
    client: TestClient,
) -> None:
    # supplier_001 version 3 opens with a price-only position, so a price-only counter
    # stays incomplete; the SaaS scenario would carry the complete opening terms over.
    payload = create_payload("h5-partial", hints_enabled=False)
    payload.update({"scenario_id": "supplier_001", "scenario_version": 3})
    created = client.post("/api/v1/sessions", headers=bearer("test-admin"), json=payload)
    assert created.status_code == 201, created.json()
    session = created.json()
    tokens = credentials(session)
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        session["revision"],
        "Предлагаю цену 110 000 евро.",
        "h5-partial",
    )
    assert status == 200, body
    npc_action = body["committed_actions"][-1]
    assert npc_action["speech_act"] == "acknowledge_partial_offer"
    assert body["observation"]["active_offers"][0]["unresolved_required_terms"] == [
        "prepayment_fraction", "delivery_weeks",
    ]
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        body["revision"],
        "Какие условия для вас важнее всего в этой сделке?",
        "h5-question",
    )
    assert status == 200
    npc_action = body["committed_actions"][-1]
    assert npc_action["speech_act"] == "qualitative_interest_answer"


def test_npc_counteroffers_are_monotonic(client: TestClient) -> None:
    session, tokens = _create(client, "m1-monotonic", hints_enabled=False)
    revision = session["revision"]
    counters: list[int] = []
    for index, price in enumerate((950000, 970000, 990000)):
        status, body = _send(
            client,
            session,
            tokens["buyer"],
            revision,
            f"Предлагаю пакет: цена {price} рублей, предоплата 50%, срок 8 недель.",
            f"m1-{index}",
        )
        assert status == 200 and body["status"] == "active", body
        revision = body["revision"]
        offer = _active_offer(client, session, tokens["buyer"])
        assert offer is not None and offer["proposer_role"] == "seller"
        counters.append(int(offer["terms"]["price"]))
    assert counters == sorted(counters, reverse=True)
    assert counters[-1] < counters[0]


# --- review, statistics, administration -------------------------------------


def test_review_contains_readable_moments_and_recommendations(client: TestClient) -> None:
    session, tokens = _create(client, "review-content", hints_enabled=False)
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        session["revision"],
        "Предлагаю пакет: цена 950 000 рублей, предоплата 50%, срок 8 недель.",
        "rev-offer",
    )
    assert status == 200 and body["status"] == "active"
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        body["revision"],
        "Принимаю ваше предложение целиком.",
        "rev-accept",
    )
    assert status == 200 and body["result"] == "confirmation_required"
    status, body = _send(
        client, session, tokens["buyer"], body["revision"], "Подтверждаю принятие.", "rev-confirm"
    )
    assert status == 200 and body["status"] == "agreement_reached"
    review = client.get(
        f"/api/v1/sessions/{session['session_id']}/review", headers=bearer(tokens["buyer"])
    ).json()
    moments = review["key_moments"]
    assert moments[0]["title"] == "Первое предложение"
    assert "Поставщик сделал первое предложение" in moments[0]["summary"]
    buyer_moment = next(moment for moment in moments if "Покупатель" in moment["summary"])
    assert "встречное предложение" in buyer_moment["summary"]
    assert buyer_moment["detail"].startswith("«Предлагаю пакет")
    assert moments[-1]["type"] == "agreement.reached"
    assert "Соглашение достигнуто" in moments[-1]["summary"]
    assert isinstance(review["recommendations"], list)
    assert any(item["skill"] == "probing" for item in review["recommendations"])
    assert all("Зафиксировано событие" not in moment["summary"] for moment in moments)


def test_get_session_returns_pending_protocol_state_for_restore(client: TestClient) -> None:
    session, tokens = _create(client, "restore-state", hints_enabled=False)
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        session["revision"],
        "Предлагаю пакет: цена 950 000 рублей, предоплата 50%, срок 8 недель.",
        "restore-lowball",
    )
    assert status == 200 and body["status"] == "active"
    status, body = _send(
        client,
        session,
        tokens["buyer"],
        body["revision"],
        "Принимаю ваше предложение целиком.",
        "restore-accept",
    )
    assert status == 200 and body["result"] == "confirmation_required"
    snapshot = client.get(
        f"/api/v1/sessions/{session['session_id']}", headers=bearer(tokens["buyer"])
    ).json()
    assert snapshot["hints_enabled"] is False
    assert snapshot["pending_confirmation"]["terms"] == body["pending_confirmation"]["terms"]
    assert snapshot["clarification"] is None
    status, body = _send(
        client, session, tokens["buyer"], body["revision"], "Согласен.", "restore-ambiguous"
    )
    assert status == 200 and body["result"] == "clarification_required"
    snapshot = client.get(
        f"/api/v1/sessions/{session['session_id']}", headers=bearer(tokens["buyer"])
    ).json()
    assert snapshot["clarification"]["reason_code"] == body["clarification"]["reason_code"]
    assert snapshot["clarification"]["question"]


def test_stats_hide_sealed_benchmark_outcomes_and_count_sessions_once(
    client: TestClient,
) -> None:
    payload = create_payload("stats-bench", both_external=True, hints_enabled=False)
    payload.update(
        {
            "run_mode": "benchmark",
            "benchmark_run_id": "stats-run",
            "trial_id": "stats-trial-1",
            "benchmark_expected_trials": 2,
            "seed": 7,
        }
    )
    created = client.post("/api/v1/sessions", headers=bearer("test-admin"), json=payload)
    assert created.status_code == 201
    session = created.json()
    tokens = credentials(session)
    status, body = _send(
        client, session, tokens["buyer"], session["revision"], "Прекращаю переговоры.", "stats-end"
    )
    assert status == 200 and body["status"] == "walked_away"
    stats = client.get("/api/v1/stats").json()
    assert stats["totals"]["agreements"] == 0
    assert stats["totals"]["agreement_rate"] is None
    scenario_row = next(row for row in stats["by_scenario"] if row["key"] == f"{SCENARIO_ID}@1")
    assert scenario_row["completed_count"] == 1
    assert scenario_row["agreement_rate"] is None
    model_row = stats["by_model"][0]
    assert model_row["session_count"] == 1
    assert model_row["seat_count"] == 2


def test_benchmark_session_creation_requires_the_administrator_token(
    client: TestClient,
) -> None:
    payload = create_payload("bench-auth", both_external=True, hints_enabled=False)
    payload.update(
        {
            "run_mode": "benchmark",
            "benchmark_run_id": "auth-run",
            "trial_id": "t1",
            "benchmark_expected_trials": 1,
            "seed": 1,
        }
    )
    assert client.post("/api/v1/sessions", json=payload).status_code == 401
    assert client.post("/api/v1/sessions", headers=bearer("wrong"), json=payload).status_code == 401
    assert (
        client.post("/api/v1/sessions", headers=bearer("test-admin"), json=payload).status_code
        == 201
    )
    assert client.post("/api/v1/sessions", json=create_payload("train-auth")).status_code == 201


def test_non_ascii_administrator_credential_is_rejected_cleanly(client: TestClient) -> None:
    response = client.get("/api/v1/admin/sessions", headers={"Authorization": b"Bearer caf\xe9"})
    assert response.status_code == 401
