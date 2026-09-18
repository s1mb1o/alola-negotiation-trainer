from __future__ import annotations

from dataclasses import replace
import json
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.dialogue import LlmNpcDialogueRenderer, NpcDialogueRequest, NpcDialogueResult
from backend.app.main import create_app
from backend.app.scenarios import compile_scenario
from clients.providers import AgentModelConfig, Generation

from .conftest import PROJECT_ROOT, bearer, create_payload


class CapturingRenderer:
    provider = "test"
    model = "conversation-routing"

    def __init__(self) -> None:
        self.requests: list[NpcDialogueRequest] = []

    def render(self, request: NpcDialogueRequest) -> NpcDialogueResult:
        self.requests.append(request)
        return NpcDialogueResult(
            text=request.fallback_text,
            mode="llm",
            provider=self.provider,
            model=self.model,
            fallback_used=False,
        )


def _create(
    client: TestClient, key: str, language: str, *, scenario_version: int = 1
) -> dict[str, Any]:
    payload = create_payload(key, language=language)
    payload["scenario_id"] = f"saas_subscription_{language}"
    payload["scenario_version"] = scenario_version
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 201
    return response.json()


def _send(
    client: TestClient,
    created: dict[str, Any],
    message: str,
    key: str,
    *,
    revision: int | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        headers=bearer(created["participant_token"]),
        json={
            "message": message,
            "idempotency_key": key,
            "expected_revision": created["revision"] if revision is None else revision,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    ("language", "message"),
    [
        ("ru", "Здравствуйте, почему такая цена?"),
        ("en", "Hello, why is the price so high?"),
    ],
)
def test_mixed_greeting_answers_the_substantive_question(
    settings: Settings, language: str, message: str
) -> None:
    renderer = CapturingRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        created = _create(client, f"mixed-greeting-{language}", language)
        response = _send(client, created, message, f"mixed-question-{language}")

    assert response["committed_actions"][-1]["speech_act"] == "general_answer"
    assert renderer.requests[-1].dialogue_context[-1].speaker == "player"
    assert renderer.requests[-1].dialogue_context[-1].text == message


@pytest.mark.parametrize(
    ("language", "offer", "information", "missing_label"),
    [
        (
            "ru",
            "Предлагаю цену 1100000 рублей.",
            "Нам важно избежать рисков при запуске.",
            "срок запуска",
        ),
        (
            "en",
            "I propose a price of RUB 1100000.",
            "We need to avoid disruption during the launch.",
            "launch timeline",
        ),
    ],
)
def test_partial_offer_does_not_turn_every_statement_into_a_package_request(
    settings: Settings,
    language: str,
    offer: str,
    information: str,
    missing_label: str,
) -> None:
    renderer = CapturingRenderer()
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        # A complete opening would carry its other terms into the price counteroffer.
        # Publish a separate test-only version with an incomplete opening instead.
        source_path = PROJECT_ROOT / "examples" / f"scenario_saas_subscription_{language}.yaml"
        document = yaml.safe_load(source_path.read_text(encoding="utf-8"))
        document["scenario"]["version"] = 90
        seller = document["scenario"]["roles"]["seller"]
        opening = seller.pop("opening_offer")
        seller["opening_position"] = {"price": opening["price"]}
        client.app.state.database.initialize([compile_scenario(document, source_path)])
        created = _create(
            client, f"partial-information-{language}", language, scenario_version=90
        )
        partial = _send(client, created, offer, f"partial-offer-{language}")
        response = _send(
            client,
            created,
            information,
            f"partial-information-message-{language}",
            revision=partial["revision"],
        )

    assert partial["committed_actions"][-1]["speech_act"] == "acknowledge_partial_offer"
    assert response["committed_actions"][-1]["speech_act"] == "acknowledge_information"
    request = renderer.requests[-1]
    assert missing_label in request.missing_term_labels
    assert request.dialogue_context[-1].text == information
    assert request.approved_terms == ()


@pytest.mark.parametrize("language", ["ru", "en"])
def test_renderer_context_contains_both_speakers_from_only_the_current_session(
    settings: Settings, language: str
) -> None:
    renderer = CapturingRenderer()
    marker_a = "ПРОЕКТ-АЛЬФА" if language == "ru" else "PROJECT-ALPHA"
    marker_b = "ПРОЕКТ-БЕТА" if language == "ru" else "PROJECT-BETA"
    greeting = "Здравствуйте" if language == "ru" else "Hello"
    question = "Почему это важно?" if language == "ru" else "Why does that matter?"
    first_message = f"{greeting}. {marker_a}."
    with TestClient(create_app(settings, npc_dialogue_renderer=renderer)) as client:
        first = _create(client, f"context-first-{language}", language)
        second = _create(client, f"context-second-{language}", language)
        first_reply = _send(client, first, first_message, f"context-a-{language}")
        _send(client, second, f"{greeting}. {marker_b}.", f"context-b-{language}")
        _send(
            client,
            first,
            question,
            f"context-followup-{language}",
            revision=first_reply["revision"],
        )

    request = renderer.requests[-1]
    context = request.dialogue_context
    assert [turn.speaker for turn in context[-3:]] == ["player", "npc", "player"]
    assert context[-3].text == first_message
    assert context[-1].text == question
    assert marker_a in " ".join(turn.text for turn in context)
    assert marker_b not in " ".join(turn.text for turn in context)
    assert request.scenario_title
    assert request.npc_role == "seller"


class RecordingProvider:
    def __init__(self) -> None:
        self.config = AgentModelConfig(provider="openai", model="redaction-test")
        self.calls: list[str] = []

    def generate(self, messages, *, instructions=None) -> Generation:
        content = messages[0]["content"]
        self.calls.append(content)
        request = json.loads(content.split("\n", 2)[1])
        return Generation(
            text=json.dumps(
                {"speech_act": request["speech_act"], "reply": request["approved_reply_options"][0]},
                ensure_ascii=False,
            ),
            provider="openai",
            model="redaction-test",
            latency_ms=0,
        )


def test_programmatic_settings_secrets_are_redacted_before_storage_and_provider(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin_secret = "ADMINPLAINCANARY"
    provider_secret = "PROVIDERPLAINCANARY"
    monkeypatch.delenv("NEGOTIATION_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("NEGOTIATION_NPC_API_KEY_ENV", raising=False)
    monkeypatch.setenv("TEST_CUSTOM_KEY", provider_secret)
    configured = replace(settings, admin_token=admin_secret, npc_api_key_env="TEST_CUSTOM_KEY")
    provider = RecordingProvider()
    renderer = LlmNpcDialogueRenderer(provider)
    with TestClient(create_app(configured, npc_dialogue_renderer=renderer)) as client:
        created = _create(client, "configured-secret-input", "ru")
        response = _send(
            client,
            created,
            f"Здравствуйте. {admin_secret} {provider_secret}.",
            "configured-secret-message",
        )
        with client.app.state.database.read_connection() as connection:
            persisted = [
                list(row)
                for query in (
                    "SELECT content FROM messages",
                    "SELECT plan_json FROM npc_render_jobs",
                    "SELECT public_payload_json, private_payload_json FROM events",
                    "SELECT response_json FROM idempotency_results",
                )
                for row in connection.execute(query)
            ]
    material = json.dumps([persisted, provider.calls, response], ensure_ascii=False)
    assert provider.calls
    assert "[REDACTED_CREDENTIAL]" in material
    assert admin_secret not in material
    assert provider_secret not in material


def test_programmatic_secret_is_redacted_when_projecting_legacy_context(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "LEGACYPLAINCANARY"
    monkeypatch.delenv("NEGOTIATION_ADMIN_TOKEN", raising=False)
    configured = replace(settings, admin_token=secret)
    renderer = CapturingRenderer()
    with TestClient(create_app(configured, npc_dialogue_renderer=renderer)) as client:
        created = _create(client, "legacy-secret-context", "ru")
        first = _send(client, created, "Здравствуйте", "legacy-first-message")
        with client.app.state.database.write_transaction() as connection:
            connection.execute(
                "UPDATE messages SET content = ? WHERE session_id = ? AND role = 'buyer'",
                (f"Здравствуйте. {secret}.", created["session_id"]),
            )
        _send(
            client, created, "Почему это важно?", "legacy-followup", revision=first["revision"]
        )
    context = " ".join(turn.text for turn in renderer.requests[-1].dialogue_context)
    assert secret not in context
    assert "[REDACTED_CREDENTIAL]" in context


@pytest.mark.parametrize("field", ["text", "provider", "model"])
def test_injected_renderer_cannot_reflect_programmatically_configured_secrets(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    secret = "OUTPUTPLAINCANARY"
    monkeypatch.delenv("NEGOTIATION_ADMIN_TOKEN", raising=False)

    class SecretRenderer(CapturingRenderer):
        def render(self, request: NpcDialogueRequest) -> NpcDialogueResult:
            result = super().render(request)
            value = f"Здравствуйте. {secret}." if field == "text" else secret
            return replace(result, **{field: value})

    configured = replace(settings, admin_token=secret)
    with TestClient(create_app(configured, npc_dialogue_renderer=SecretRenderer())) as client:
        created = _create(client, f"configured-secret-output-{field}", "ru")
        response = _send(client, created, "Здравствуйте", f"secret-output-message-{field}")
        with client.app.state.database.read_connection() as connection:
            persisted = [list(row) for row in connection.execute("SELECT content FROM messages")]
    metadata = response["committed_actions"][-1]["dialogue_renderer"]
    assert metadata["fallback_used"] is True
    assert metadata["failure_reason"] == "output_invalid"
    assert secret not in json.dumps([response, persisted], ensure_ascii=False)
