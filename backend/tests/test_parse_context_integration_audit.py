"""Independent DR-28 checks for public parser context and delivery boundaries."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.app.dialogue import NpcDialogueResult, TemplateNpcDialogueRenderer
from backend.app.main import create_app

from .conftest import bearer, create_payload, credentials
from .test_continuity_integration import _create, _history, _submit


def _context(client, session):
    service = client.app.state.service
    with service.database.read_connection() as connection:
        row, actor = service._authenticated_rows(
            connection, session["session_id"], session["participant_token"]
        )
        return service._parse_context(
            connection, row, actor, service._scenario_source(connection, row),
            json.loads(row["state_json"]),
        )


def _external_session(client, key):
    payload = create_payload(key, both_external=True)
    payload.update(scenario_id="supplier_001", scenario_version=5)
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 201, response.text
    session = response.json()
    return session, credentials(session)


def _external_send(client, session, token, message, *, revision=None, key=None):
    revision = session["revision"] if revision is None else revision
    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/messages",
        headers=bearer(token),
        json={"message": message, "expected_revision": revision,
              "idempotency_key": key or f"audit-{revision}"},
    )
    if response.status_code == 200:
        session["revision"] = response.json()["revision"]
    return response


def test_two_sessions_keep_independent_term_focus_and_numeric_answers(client):
    price_session = _create(client, "audit-price-focus", version=5)
    week_session = _create(client, "audit-week-focus", version=5)
    _submit(client, price_session, "Сначала обсудим цену.")
    _submit(client, week_session, "Сначала обсудим срок поставки.")
    assert _context(client, price_session).expected_term_id == "price"
    assert _context(client, week_session).expected_term_id == "delivery_weeks"
    price = _submit(client, price_session, "110000")
    weeks = _submit(client, week_session, "6")
    assert price["observation"]["active_offers"][0]["terms"] == {"price": 110000}
    assert weeks["observation"]["active_offers"][0]["terms"] == {
        "price": 120000, "delivery_weeks": 6,
    }
    assert price["status"] == weeks["status"] == "active"


def test_relative_edits_use_current_revision_and_reject_stale_command(client):
    session, tokens = _external_session(client, "audit-relative-revision")
    first = _external_send(client, session, tokens["buyer"], "Снизить цену на 10000 EUR.")
    assert first.status_code == 200, first.text
    assert first.json()["observation"]["active_offers"][0]["terms"] == {"price": 110000}
    old_revision = session["revision"]
    second = _external_send(client, session, tokens["seller"], "Снизить цену на 2000 EUR.")
    assert second.status_code == 200, second.text
    before = second.json()["observation"]["active_offers"]
    assert before[0]["terms"] == {"price": 108000}
    stale = _external_send(
        client, session, tokens["buyer"], "Снизить цену на 2000 EUR.",
        revision=old_revision, key="audit-stale",
    )
    assert stale.status_code == 409
    assert stale.json()["error"] == "revision_conflict"
    latest = _external_send(client, session, tokens["buyer"], "Снизить цену на 2000 EUR.")
    assert latest.status_code == 200, latest.text
    assert latest.json()["observation"]["active_offers"][0]["terms"] == {"price": 106000}
    assert latest.json()["observation"]["active_offers"][0]["offer_revision"] == before[0]["offer_revision"] + 1


def test_withdrawn_offer_cannot_supply_relative_baseline(client):
    session, tokens = _external_session(client, "audit-withdrawn-baseline")
    assert _external_send(client, session, tokens["buyer"], "Здравствуйте").status_code == 200
    withdrawn = _external_send(client, session, tokens["seller"], "Отзываю предложение.")
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["observation"]["active_offers"] == []
    relative = _external_send(client, session, tokens["buyer"], "Снизить цену на 10000 EUR.")
    assert relative.status_code == 200, relative.text
    assert relative.json()["result"] == "clarification_required"
    assert relative.json()["clarification"]["reason_code"] == "relative_change_requires_baseline"
    assert relative.json()["observation"]["active_offers"] == []


def test_numeric_question_about_received_offer_cannot_request_acceptance(client):
    session, tokens = _external_session(client, "audit-received-numeric-question")
    offer = _external_send(
        client, session, tokens["buyer"],
        "Предлагаю цену 110000 EUR, предоплату 50%, срок поставки 6 недель.",
    )
    assert offer.status_code == 200, offer.text
    active = offer.json()["observation"]["active_offers"]
    response = _external_send(client, session, tokens["seller"], "Почему цена 110000 EUR?")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"] == "turn_committed"
    assert body["committed_actions"][0]["action"] == "question"
    assert body["observation"]["active_offers"] == active
    assert body["status"] == "active"


class ProseOnlyQuestionRenderer:
    def render(self, request):
        return NpcDialogueResult(
            text="Какую цену вы хотите обсудить?", mode="llm", provider="offline",
            model="test", fallback_used=False,
        )


def test_generated_question_does_not_create_requested_term(settings):
    with TestClient(create_app(settings, npc_dialogue_renderer=ProseOnlyQuestionRenderer())) as client:
        session = _create(client, "audit-prose-is-not-parser-context", version=5)
        body = _submit(client, session, "Здравствуйте")
        assert body["committed_actions"][-1]["message"] == "Какую цену вы хотите обсудить?"
        context = _context(client, session)
        assert context.expected_term_id is None
        assert context.focused_term_id is None
        answer = _submit(client, session, "105 тысяч")
        assert answer["result"] == "clarification_required"
        assert answer["clarification"]["reason_code"] == "numeric_answer_requires_term"
        assert answer["observation"]["active_offers"][0]["terms"] == {"price": 120000}


def test_a_later_reply_does_not_reuse_an_old_requested_term(client):
    session = _create(client, "audit-old-requested-term", version=5)
    _submit(client, session, "Сначала обсудим цену.")
    assert _context(client, session).expected_term_id == "price"
    _submit(client, session, "Цену обсудим позже.")
    context = _context(client, session)
    assert context.expected_term_id is None
    assert context.focused_term_id is None
    answer = _submit(client, session, "105 тысяч")
    assert answer["result"] == "clarification_required"
    assert answer["clarification"]["reason_code"] == "numeric_answer_requires_term"


class BlockingContextRenderer:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def render(self, request):
        self.entered.set()
        assert self.release.wait(5)
        return TemplateNpcDialogueRenderer().render(request)


def test_requested_term_is_not_read_from_pending_intent(settings):
    renderer = BlockingContextRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        session = _create(client, "audit-pending-requested-term", version=5)
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(_submit, client, session, "Сначала обсудим цену.")
            try:
                assert renderer.entered.wait(5)
                context = _context(client, session)
                # A player-authored focus is already public. A pending NPC request
                # is not a delivered request and cannot supply expected_term_id.
                assert context.focused_term_id == "price"
                assert context.expected_term_id is None
                assert not [event for event in _history(client, session)
                            if event["type"] == "npc.utterance.delivered"]
            finally:
                renderer.release.set()
            assert result.result(timeout=5)["status"] == "active"
        assert _context(client, session).expected_term_id == "price"
