from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import uuid

import pytest

from backend.app.main import create_app
from backend.tests.conftest import bearer, create_payload, credentials


FULL = {
    "ru": "Предлагаем 109500 EUR за 100 устройств, 10 устройств в начале ноября со 100% авансом, остальные 90 устройств 20 ноября с 50% авансом, остаток при поставке, DDP, без резерва.",
    "en": "We propose 109500 EUR for 100 devices, 10 devices in early November with 100% advance, remaining 90 devices on November 20 with 50% advance, balance on delivery, DDP, no reserve.",
}


def create_supply(
    client, language="ru", both_external=False, human_role="buyer", run_mode="training"
):
    payload = create_payload(
        uuid.uuid4().hex,
        difficulty="easy",
        both_external=both_external,
        language=language,
        human_role=human_role,
    )
    payload.update(scenario_id="supplier_integration_" + language, scenario_version=1)
    headers = None
    if run_mode == "benchmark":
        payload.update(
            run_mode="benchmark",
            difficulty="normal",
            hints_enabled=False,
            benchmark_run_id="supply-protocol-bound",
            trial_id=uuid.uuid4().hex,
            benchmark_expected_trials=1,
        )
        headers = bearer("test-admin")
    response = client.post("/api/v1/sessions", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def submit(client, session, token, text, *, key=None):
    revision = client.get(
        f"/api/v1/sessions/{session['session_id']}", headers=bearer(token)
    ).json()["revision"]
    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/messages",
        headers=bearer(token),
        json={
            "message": text,
            "expected_revision": revision,
            "idempotency_key": key or uuid.uuid4().hex,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("language", ["ru", "en"])
def test_supply_initial_is_preliminary_without_payment_defaults(client, language):
    session = create_supply(client, language)
    observation = session["observation"]
    assert observation["active_offers"] == []
    assert session["negotiation_contract_version"] == "supply-package-v1"
    proposal = observation["preliminary_proposals"][0]
    assert set(proposal["terms"]) == {"base_price", "delivery_lots"}
    assert proposal["source_event_ids"]
    assert "financial_summary" not in observation
    assert observation["conversation"]
    assert "0%" not in observation["conversation"][0]["message"]
    before = deepcopy(proposal)
    reply = submit(
        client,
        session,
        credentials(session)["buyer"],
        "А если 50% аванса?" if language == "ru" else "What if we pay 50% advance?",
    )
    assert reply["status"] == "active"
    assert reply["observation"]["preliminary_proposals"][0]["terms"] == before["terms"]


@pytest.mark.parametrize("language", ["ru", "en"])
def test_complete_preliminary_requires_publication_then_exact_confirmation(client, language):
    session = create_supply(client, language, both_external=True)
    tokens = credentials(session)
    proposed = submit(client, session, tokens["buyer"], FULL[language])
    assert proposed["result"] == "committed", proposed
    assert proposed["observation"]["active_offers"] == []
    assert proposed["observation"]["preliminary_proposals"][0]["unresolved_required_terms"] == []
    # A counterpart question returns the turn without publishing or accepting.
    submit(
        client,
        session,
        tokens["seller"],
        "Почему такой график?" if language == "ru" else "Why this schedule?",
    )
    publish = submit(
        client,
        session,
        tokens["buyer"],
        "Публикую окончательное предложение" if language == "ru" else "Publish my final offer",
    )
    assert publish["confirmation_kind"] == "publish_offer"
    pending = publish["pending_offer_publication"]
    assert pending["snapshot_digest"]
    restored = client.get(
        f"/api/v1/sessions/{session['session_id']}", headers=bearer(tokens["buyer"])
    ).json()
    other_view = client.get(
        f"/api/v1/sessions/{session['session_id']}", headers=bearer(tokens["seller"])
    ).json()
    assert restored["pending_offer_publication"] == pending
    assert other_view["pending_offer_publication"] is None
    published = submit(
        client,
        session,
        tokens["buyer"],
        "Подтверждаю окончательное предложение"
        if language == "ru"
        else "I confirm the final offer",
    )
    assert published["status"] == "active"
    assert published["observation"]["preliminary_proposals"] == []
    assert published["observation"]["active_offers"][0]["terms"] == pending["terms"]
    intent = submit(
        client,
        session,
        tokens["seller"],
        "Принимаю предложение" if language == "ru" else "I accept the offer",
    )
    assert intent["confirmation_kind"] == "accept_offer"
    assert intent["status"] == "active"
    confirmed = submit(
        client,
        session,
        tokens["seller"],
        "Подтверждаю принятие" if language == "ru" else "I confirm acceptance",
    )
    assert confirmed["status"] == "agreement_reached"
    review = client.get(
        f"/api/v1/sessions/{session['session_id']}/review", headers=bearer(tokens["buyer"])
    )
    assert review.status_code == 200, review.text
    assert review.json()["outcome"]["agreement"]


def test_npc_does_not_accept_preliminary_and_presents_final_before_acceptance(client):
    session = create_supply(client)
    token = credentials(session)["buyer"]
    proposed = submit(client, session, token, FULL["ru"])
    assert proposed["status"] == "active"
    assert proposed["observation"]["active_offers"] == []
    final = submit(client, session, token, "Покажите окончательное предложение")
    if final.get("pending_offer_publication"):
        final = submit(client, session, token, "Подтверждаю окончательное предложение")
        assert final["status"] == "agreement_reached"
    else:
        assert final["status"] == "active"
        assert final["observation"]["active_offers"]
        intent = submit(client, session, token, "Принимаю предложение")
        assert intent["status"] == "active"
        assert (
            submit(client, session, token, "Подтверждаю принятие")["status"] == "agreement_reached"
        )


def test_amendment_invalidates_publication_and_conditional_error_is_atomic(client):
    session = create_supply(client, both_external=True)
    tokens = credentials(session)
    submit(client, session, tokens["buyer"], FULL["ru"])
    submit(client, session, tokens["seller"], "Почему такой график?")
    pending = submit(client, session, tokens["buyer"], "Публикую окончательное предложение")
    assert pending["pending_offer_publication"]
    before = pending["observation"]["current_public_terms"]
    invalid = submit(
        client, session, tokens["buyer"], "Предлагаем 108000 EUR, если включите штраф за задержку."
    )
    assert invalid["result"] == "clarification_required"
    assert invalid["observation"]["current_public_terms"] == before
    amended = submit(client, session, tokens["buyer"], "Предлагаем 110000 EUR")
    assert amended["pending_offer_publication"] is None
    assert amended["observation"]["current_public_terms"]["base_price"]["minor_units"] == 11000000


def test_supply_sessions_are_isolated_and_idempotent(client):
    sessions = [create_supply(client, language) for language in ("ru", "en")]

    def play(index):
        session = sessions[index]
        token = credentials(session)["buyer"]
        language = "ru" if index == 0 else "en"
        key = "isolated-repeat"
        initial = session["revision"]
        body = {"message": FULL[language], "expected_revision": initial, "idempotency_key": key}
        route = f"/api/v1/sessions/{session['session_id']}/messages"
        first = client.post(route, headers=bearer(token), json=body)
        repeat = client.post(route, headers=bearer(token), json=body)
        assert first.status_code == 200, first.text
        assert repeat.json() == first.json()
        return first.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(play, range(2)))
    assert results[0]["session_id"] != results[1]["session_id"]
    for index, result in enumerate(results):
        assert all(
            item["participant_id"].startswith("participant_" + sessions[index]["session_id"][5:])
            for item in result["observation"]["conversation"]
        )


def test_restart_preserves_supply_history_without_renderer_calls(client, settings):
    from fastapi.testclient import TestClient

    session = create_supply(client)
    token = credentials(session)["buyer"]
    submit(client, session, token, FULL["ru"])
    route = f"/api/v1/sessions/{session['session_id']}/history"
    history = client.get(route, headers=bearer(token)).json()
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(route, headers=bearer(token)).json() == history
        assert restarted.get(
            f"/api/v1/sessions/{session['session_id']}", headers=bearer(token)
        ).json()["observation"]["preliminary_proposals"]
