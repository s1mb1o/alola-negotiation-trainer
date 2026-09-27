from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.dialogue import LlmNpcDialogueRenderer, PublicDialogueTurn, utterance_plan_from_payload
from backend.app.dialogue_redirect import select_varied_fallback, topic_return_options
from backend.app.main import create_app
from .conftest import bearer, create_payload, credentials
from .test_npc_dialogue import FailingProvider, SelectingRenderer
from .test_supply_protocol import create_supply, submit


@pytest.mark.parametrize("language,message", [("ru", "Как зовут вашу собаку?"), ("en", "What is your dog's name?")])
def test_six_variants_rotate_and_resume_public_topic(language, message):
    labels = {"price": "цена" if language == "ru" else "price"}
    options = topic_return_options(message, language, labels, (), {}, "price")
    assert len(set(options)) == 6
    assert all(labels["price"] in text and text.count("?") == 1 for text in options)
    previous = []
    for _ in range(12):
        reply = select_varied_fallback(options, message, previous)
        if len(previous) < 6:
            assert reply not in previous
        else:
            assert reply == previous[-6]
        previous.append(reply)


@pytest.mark.parametrize("message", [
    "Как зовут вашу собаку? Давайте обсудим цену.",
    "Как погода повлияет на поставку?", "What about weather and delivery?",
    "Как зовут собаку? Предлагаю 110000 евро.", "Какие условия вас устраивают?",
])
def test_negotiation_and_mixed_messages_keep_existing_handling(message):
    assert not topic_return_options(message, "ru", {"price": "цена", "delivery_weeks": "срок поставки"}, (), {})


def test_approved_dog_fact_is_not_redirected_and_previous_prices_are_not_copied():
    question = "Как зовут вашу собаку?"
    assert not topic_return_options(question, "ru", {}, (), {"personal_fact": "У вас есть собака по кличке Гуффи."})
    options = topic_return_options(question, "ru", {"price": "цена"}, (
        PublicDialogueTurn("npc", "Ваша цена 110000 евро?"),
        PublicDialogueTurn("player", question),
    ), {})
    assert all("цена" in text and "110000" not in text and "Гуффи" not in text for text in options)


def test_multitopic_previous_question_returns_to_terms_without_choosing_one() -> None:
    options = topic_return_options(
        "Как зовут вашу собаку?",
        "ru",
        {"price": "цена", "delivery_weeks": "срок поставки"},
        (
            PublicDialogueTurn(
                "npc",
                "Подходит ли вам цена и срок поставки, и что обсудим первым?",
            ),
        ),
        {},
    )

    assert options
    assert all("Какие условия вы хотели бы обсудить?" in text for text in options)


@pytest.mark.parametrize("language", ["ru", "en"])
def test_disabled_personal_fact_provider_failure_is_polite_durable_and_varied(settings, language):
    provider = FailingProvider()
    with TestClient(create_app(settings, npc_dialogue_renderer=LlmNpcDialogueRenderer(provider))) as client:
        payload = create_payload("redirect-" + language, language=language)
        payload.update(scenario_id="supplier_001", scenario_version=5, training={"personal_detail": False})
        # The industrial scenario is Russian; use the translated scalar scenario for English.
        if language == "en":
            payload.update(scenario_id="saas_subscription_en", scenario_version=1)
        created = client.post("/api/v1/sessions", json=payload)
        assert created.status_code == 201, created.text
        session = created.json()
        question = "Как зовут вашу собаку?" if language == "ru" else "What is your dog's name?"
        initial_offers = session["observation"]["active_offers"]
        replies = []
        for index in range(3):
            response = client.post(f"/api/v1/sessions/{session['session_id']}/messages",
                headers=bearer(session["participant_token"]), json={"message": question,
                    "expected_revision": session["revision"], "idempotency_key": str(index)})
            assert response.status_code == 200, response.text
            session.update(response.json())
            npc = response.json()["committed_actions"][-1]
            assert npc["dialogue_renderer"]["failure_reason"] == "provider_failure"
            replies.append(npc["message"])
            assert response.json()["observation"]["active_offers"] == initial_offers
        assert len(set(replies)) == 3
        assert all("Гуффи" not in reply and "Goofy" not in reply for reply in replies)
        assert all(("переговор" in reply or "обсуждени" in reply or "сделки" in reply) if language == "ru"
                   else ("negotiation" in reply or "discussion" in reply or "deal terms" in reply) for reply in replies)
        with client.app.state.database.read_connection() as connection:
            row = connection.execute("SELECT plan_json FROM npc_render_jobs WHERE session_id = ? ORDER BY intent_revision DESC LIMIT 1",
                                     (session["session_id"],)).fetchone()
        plan = utterance_plan_from_payload(json.loads(row[0]))
        assert plan.request.fallback_text == replies[-1]
        assert len(plan.request.approved_reply_options) == 6


def test_enabled_personal_fact_preserves_grounded_small_talk(settings):
    renderer = SelectingRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        payload = create_payload("enabled-dog")
        payload["training"] = {"personal_detail": True}
        session = client.post("/api/v1/sessions", json=payload).json()
        result = client.post(f"/api/v1/sessions/{session['session_id']}/messages", headers=bearer(session["participant_token"]),
            json={"message": "Как зовут вашу собаку?", "expected_revision": session["revision"], "idempotency_key": "dog"})
        assert result.status_code == 200
        request = renderer.requests[-1]
        assert "Гуффи" in request.training_context["personal_fact"]
        assert len(request.approved_reply_options) != 6


def test_supply_fallback_redirect_preserves_package_and_varies(settings):
    with TestClient(create_app(settings, npc_dialogue_renderer=LlmNpcDialogueRenderer(FailingProvider()))) as client:
        session = create_supply(client)
        original = session["observation"]["preliminary_proposals"][0]["terms"]
        replies = []
        for _ in range(3):
            result = submit(client, session, credentials(session)["buyer"], "Как зовут вашу собаку?")
            action = result["committed_actions"][-1]
            assert action["action"] == "inform"
            assert action["dialogue_renderer"]["failure_reason"] == "provider_failure"
            assert result["observation"]["preliminary_proposals"][0]["terms"] == original
            replies.append(action["message"])
        assert len(set(replies)) == 3
        assert all(not any(char.isdigit() for char in reply) for reply in replies)
