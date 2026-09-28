"""Regression checks from the independent supply integration review."""

from __future__ import annotations

from copy import deepcopy
import uuid

from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from backend.tests.conftest import bearer, credentials
from backend.tests.test_supply_protocol import FULL, create_supply, submit


def _pending_publication(client, language="en", run_mode="training"):
    session = create_supply(client, language, both_external=True, run_mode=run_mode)
    tokens = credentials(session)
    submit(client, session, tokens["buyer"], FULL[language])
    submit(
        client,
        session,
        tokens["seller"],
        "Why this schedule?" if language == "en" else "Почему такой график?",
    )
    pending = submit(
        client,
        session,
        tokens["buyer"],
        "Publish my final offer" if language == "en" else "Публикую окончательное предложение",
    )
    assert pending["pending_offer_publication"]
    return session, tokens, pending


def _published_offer(client, language="en"):
    session, tokens, pending = _pending_publication(client, language)
    published = submit(
        client,
        session,
        tokens["buyer"],
        "I confirm the final offer"
        if language == "en"
        else "Подтверждаю окончательное предложение",
    )
    assert (
        published["observation"]["active_offers"][0]["terms"]
        == pending["pending_offer_publication"]["terms"]
    )
    return session, tokens, published


@pytest.mark.parametrize("language", ["ru", "en"])
def test_actual_ui_acceptance_cancellation_removes_pending_authority(client, language):
    session, tokens, _ = _published_offer(client, language)
    submit(
        client,
        session,
        tokens["seller"],
        "I accept the offer" if language == "en" else "Принимаю предложение",
    )
    cancelled = submit(
        client,
        session,
        tokens["seller"],
        "I do not confirm acceptance of the offer."
        if language == "en"
        else "Не подтверждаю принятие предложения.",
    )
    assert cancelled["result"] == "confirmation_cancelled"
    assert not cancelled.get("pending_confirmation")
    restored = client.get(
        f"/api/v1/sessions/{session['session_id']}", headers=bearer(tokens["seller"])
    ).json()
    assert not restored.get("pending_confirmation")
    assert restored.get("confirmation_kind") != "accept_offer"
    # A later isolated confirmation must not resurrect the cancelled intent.
    reply = submit(
        client,
        session,
        tokens["seller"],
        "I confirm acceptance" if language == "en" else "Подтверждаю принятие",
    )
    assert reply["status"] != "agreement_reached"


def test_question_returns_the_same_owner_acceptance_snapshot(client):
    session, tokens, _ = _published_offer(client)
    intent = submit(client, session, tokens["seller"], "I accept the offer")
    snapshot = deepcopy(intent["pending_confirmation"])
    question = submit(client, session, tokens["seller"], "Why this schedule?")
    assert question["confirmation_kind"] == "accept_offer"
    assert question["pending_confirmation"] == snapshot
    assert question["next_actor"] == intent["next_actor"]
    assert question["observation"]["active_offers"] == intent["observation"]["active_offers"]
    for role in ("buyer", "seller"):
        restored = client.get(
            f"/api/v1/sessions/{session['session_id']}", headers=bearer(tokens[role])
        ).json()
        assert restored.get("pending_confirmation") == (snapshot if role == "seller" else None)


def test_clarification_expiry_removes_publication_and_active_preliminary_projection(client):
    session, tokens, _ = _pending_publication(client, run_mode="benchmark")
    result = None
    for _ in range(10):
        result = submit(
            client,
            session,
            tokens["buyer"],
            "We propose 110000 EUR if there is an unlimited penalty.",
        )
        if result["status"] != "active":
            break
    assert result is not None and result["status"] == "expired"
    assert not result.get("pending_offer_publication")
    assert not result.get("pending_confirmation")
    assert result.get("confirmation_kind") not in {"publish_offer", "accept_offer"}
    assert result["observation"]["preliminary_proposals"] == []
    restored = client.get(
        f"/api/v1/sessions/{session['session_id']}", headers=bearer(tokens["buyer"])
    ).json()
    assert not restored.get("pending_offer_publication")
    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "I confirm the final offer",
            "expected_revision": restored["revision"],
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"] == "session_terminal"


def test_publication_is_actor_bound_and_restored_without_changing_the_snapshot(client, settings):
    session, tokens, pending = _pending_publication(client)
    route = f"/api/v1/sessions/{session['session_id']}"
    wrong_actor = client.post(
        route + "/messages",
        headers=bearer(tokens["seller"]),
        json={
            "message": "I confirm the final offer",
            "expected_revision": pending["revision"],
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert wrong_actor.status_code == 409
    assert wrong_actor.json()["error"] == "not_your_turn"
    with TestClient(create_app(settings)) as restarted:
        restored = restarted.get(route, headers=bearer(tokens["buyer"])).json()
        assert restored["pending_offer_publication"] == pending["pending_offer_publication"]
        assert restored["revision"] == pending["revision"]
        assert (
            restarted.get(route, headers=bearer(tokens["seller"])).json()[
                "pending_offer_publication"
            ]
            is None
        )
        body = {
            "message": "I confirm the final offer",
            "expected_revision": restored["revision"],
            "idempotency_key": uuid.uuid4().hex,
        }
        first = restarted.post(route + "/messages", headers=bearer(tokens["buyer"]), json=body)
        repeated = restarted.post(route + "/messages", headers=bearer(tokens["buyer"]), json=body)
        assert first.status_code == 200
        assert repeated.json() == first.json()
        assert (
            first.json()["observation"]["active_offers"][0]["terms"]
            == pending["pending_offer_publication"]["terms"]
        )
        history = restarted.get(route + "/history", headers=bearer(tokens["buyer"])).json()
        assert sum(event["type"] == "offer.created" for event in history["events"]) == 1


def test_amended_publication_rejects_the_old_session_revision_and_does_not_resurrect(client):
    session, tokens, pending = _pending_publication(client)
    route = f"/api/v1/sessions/{session['session_id']}"
    amended = submit(client, session, tokens["buyer"], "We propose 110000 EUR")
    assert not amended.get("pending_offer_publication")
    stale = client.post(
        route + "/messages",
        headers=bearer(tokens["buyer"]),
        json={
            "message": "I confirm the final offer",
            "expected_revision": pending["revision"],
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"] == "revision_conflict"
    submit(client, session, tokens["seller"], "Why this schedule?")
    fresh = submit(client, session, tokens["buyer"], "I confirm the final offer")
    assert fresh["status"] == "active"
    assert fresh["observation"]["active_offers"] == []
    assert fresh["observation"]["current_public_terms"]["base_price"]["minor_units"] == 11000000


def test_amending_a_formal_offer_supersedes_it_and_invalidates_acceptance(client):
    session, tokens, published = _published_offer(client)
    formal = published["observation"]["active_offers"][0]
    submit(client, session, tokens["seller"], "I accept the offer")
    amended = submit(client, session, tokens["seller"], "We propose 110000 EUR")
    assert not amended.get("pending_confirmation")
    assert amended["observation"]["active_offers"] == []
    assert (
        amended["observation"]["preliminary_proposals"][0]["terms"]["base_price"]["minor_units"]
        == 11000000
    )
    detail = client.get(
        f"/api/v1/admin/sessions/{session['session_id']}", headers=bearer("test-admin")
    ).json()
    assert (
        next(offer for offer in detail["offers"] if offer["offer_id"] == formal["offer_id"])[
            "status"
        ]
        == "superseded"
    )
    submit(client, session, tokens["buyer"], "Why this schedule?")
    old_confirmation = submit(client, session, tokens["seller"], "I confirm acceptance")
    assert old_confirmation["status"] == "active"
    assert old_confirmation["observation"]["active_offers"] == []
