"""Regressions for contextual prose without LLM authority over the deal."""

import json
from dataclasses import replace

import pytest

from backend.app.dialogue import (
    MAX_CONTEXT_TEXT_CHARACTERS,
    MAX_CONTEXT_TURNS,
    LlmNpcDialogueRenderer,
    NpcDialogueRequest,
    PublicDialogueTurn,
    bounded_dialogue_context,
    build_safe_render_input,
    validate_rendered_reply,
)
from clients.providers import AgentModelConfig, Generation


class ProseProvider:
    config = AgentModelConfig(provider="openai", model="test-contextual")
    SEED_PARAMETER_SUPPORTED = False

    def __init__(self, reply, verdict='{"safe":true}'):
        self.reply = reply
        self.verdict = verdict
        self.calls = []

    def generate(self, messages, *, instructions=None):
        self.calls.append((messages, instructions))
        if "CANDIDATE_REPLY_JSON:" in messages[0]["content"]:
            if isinstance(self.verdict, Exception):
                raise self.verdict
            text = self.verdict
        else:
            text = json.dumps({"speech_act": "general_answer", "reply": self.reply})
        return Generation(text=text, provider="openai", model=self.config.model, latency_ms=1)


class CharacterProvider(ProseProvider):
    config = AgentModelConfig(provider="qwen", model="qwen-flash-character")


def request(language="ru"):
    fallback = (
        "Какие условия вы хотите обсудить?" if language == "ru"
        else "Which terms would you like to discuss?"
    )
    return NpcDialogueRequest(
        language=language,
        currency="EUR",
        speech_act="general_answer",
        approved_terms=(),
        public_interest_labels=(),
        participant_facing_terms=(("prepayment_fraction", "предоплата"),),
        dialogue_context=(PublicDialogueTurn(
            "player", "Почему вы опять спрашиваете про пакет?" if language == "ru"
            else "Why do you keep asking about the package?",
        ),),
        approved_reply_options=(fallback,),
        fallback_text=fallback,
        scenario_title="Поставка компьютеров" if language == "ru" else "Computer supply",
        npc_role="seller",
    )

@pytest.mark.parametrize(("language", "reply"), [
    ("ru", "Необязательно обсуждать всё сразу. Какое условие хотите разобрать подробнее?"),
    ("en", "We can discuss the terms separately. Which part would you like to focus on?"),
])
def test_novel_contextual_prose_passes_generation_and_grounding(language, reply):
    provider = ProseProvider(reply)
    result = LlmNpcDialogueRenderer(provider).render(request(language))
    assert result.text == reply
    assert result.mode == "llm"
    assert not result.fallback_used
    assert len(provider.calls) == 2
    assert request(language).dialogue_context[-1].text in provider.calls[0][0][0]["content"]


def test_renderer_routes_generation_and_grounding_to_separate_providers():
    dialogue = ProseProvider("Какие условия для вас сейчас важнее всего?")
    grounding = ProseProvider("unused", '{"safe":true}')

    result = LlmNpcDialogueRenderer(
        dialogue,
        grounding_provider=grounding,
    ).render(request())

    assert result.mode == "llm"
    assert len(dialogue.calls) == 1
    assert len(grounding.calls) == 1
    assert "ENGINE_CHARACTER_PROFILE" in dialogue.calls[0][1]
    assert "CANDIDATE_REPLY_JSON:" in grounding.calls[0][0][0]["content"]


def test_character_renderer_uses_engine_speech_act_and_grounds_reply():
    dialogue = CharacterProvider("unused")
    dialogue.generate = lambda messages, instructions=None: Generation(
        text=json.dumps({
            "speech_act": "model_selected_another_act",
            "model_selected_metadata": "ignored",
            "reply": "Добрый день. Какое условие вы хотите обсудить первым?",
        }),
        provider="qwen",
        model="qwen-flash-character",
        latency_ms=1,
    )
    grounding = ProseProvider("unused", '{"safe":true}')

    result = LlmNpcDialogueRenderer(
        dialogue,
        grounding_provider=grounding,
    ).render(request())

    assert result.mode == "llm"
    assert result.text == "Добрый день. Какое условие вы хотите обсудить первым?"
    assert len(grounding.calls) == 1


def test_character_renderer_appends_public_history_as_chat_messages():
    dialogue = CharacterProvider("Какие условия вы хотите обсудить первыми?")
    grounding = ProseProvider("unused", '{"safe":true}')

    result = LlmNpcDialogueRenderer(
        dialogue,
        grounding_provider=grounding,
    ).render(request())

    assert result.mode == "llm"
    roles = [item["role"] for item in dialogue.calls[0][0]]
    assert roles == ["user", "user"]
    assert dialogue.calls[0][0][0]["content"] == request().dialogue_context[0].text
    assert "APPROVED_RENDER_INPUT" in dialogue.calls[0][0][-1]["content"]


def test_character_renderer_rejects_unslotted_relative_date_adjective():
    dialogue = CharacterProvider("unused")
    dialogue.generate = lambda messages, instructions=None: Generation(
        text=json.dumps({"reply": "Обсудим условия сегодняшней поставки?"}),
        provider="qwen",
        model="qwen-flash-character",
        latency_ms=1,
    )

    result = LlmNpcDialogueRenderer(dialogue).render(request())

    assert result.fallback_used
    assert result.failure_reason == "output_invalid"
    assert result.validation_failure == "unauthorized_claim"


def test_renderer_rejects_further_improvement_of_a_favorable_surprise_term():
    tradeoff = replace(
        request(),
        participant_facing_terms=(
            ("price", "цена"),
            ("delivery_weeks", "срок поставки"),
        ),
        focused_term_ids=("price",),
        player_concern_term_ids=("price",),
        player_favorable_surprise_term_ids=("delivery_weeks",),
    )
    provider = ProseProvider(
        "Для вас важнее сократить срок поставки или обсудить цену?"
    )

    result = LlmNpcDialogueRenderer(provider).render(tradeoff)

    assert result.fallback_used
    assert result.failure_reason == "output_invalid"
    assert len(provider.calls) == 1


def test_renderer_allows_tentative_exchange_question_for_favorable_surprise():
    tradeoff = replace(
        request(),
        participant_facing_terms=(
            ("price", "цена"),
            ("delivery_weeks", "срок поставки"),
        ),
        focused_term_ids=("price",),
        player_concern_term_ids=("price",),
        player_favorable_surprise_term_ids=("delivery_weeks",),
    )
    reply = (
        "Правильно понимаю: основной вопрос для вас — цена, а более поздний срок "
        "поставки вы готовы рассмотреть как предмет обмена?"
    )

    result = LlmNpcDialogueRenderer(ProseProvider(reply)).render(tradeoff)

    assert result.text == reply
    assert result.mode == "llm"
    assert not result.fallback_used


def test_renderer_requires_the_tentative_exchange_question_for_both_signals():
    tradeoff = replace(
        request(),
        participant_facing_terms=(
            ("price", "цена"),
            ("delivery_weeks", "срок поставки"),
        ),
        focused_term_ids=("price",),
        player_concern_term_ids=("price",),
        player_favorable_surprise_term_ids=("delivery_weeks",),
    )
    provider = ProseProvider(
        "Понимаю вашу озабоченность по поводу стоимости. Что именно в цене вас расстроило?"
    )

    result = LlmNpcDialogueRenderer(provider).render(tradeoff)

    assert result.fallback_used
    assert result.failure_reason == "output_invalid"
    assert len(provider.calls) == 1


def test_renderer_rejects_an_unauthorized_price_explanation():
    provider = ProseProvider(
        "Текущая стоимость обусловлена повышенными транспортными издержками. "
        "Какой диапазон цен вы готовы рассмотреть?"
    )

    result = LlmNpcDialogueRenderer(provider).render(request())

    assert result.fallback_used
    assert result.failure_reason == "output_invalid"
    assert len(provider.calls) == 1


@pytest.mark.parametrize("verdict", [
    '{"safe":false}', '{"safe":"true"}', '{"safe":1}',
    '{"safe":true,"explanation":"fine"}', '{"safe":false,"safe":true}',
    'true', 'not JSON',
])
def test_unsupported_non_numeric_claims_and_invalid_verdicts_fail_closed(verdict):
    provider = ProseProvider("Мы уже зарезервировали склад для вас.", verdict)
    result = LlmNpcDialogueRenderer(provider).render(request())
    assert len(provider.calls) == 2
    assert result.text == request().fallback_text
    assert result.fallback_used
    assert result.failure_reason == "output_invalid"


def test_grounding_outage_uses_fallback_without_persisting_candidate():
    provider = ProseProvider("Какое условие хотите разобрать подробнее?", TimeoutError())
    result = LlmNpcDialogueRenderer(provider).render(request())
    assert result.fallback_used
    assert result.failure_reason == "provider_failure"
    assert result.text == request().fallback_text


@pytest.mark.parametrize("reply", [
    "Принимаю предложение.", "Договорились.", "Доставка бесплатно.",
    "Предоплата не нужна.", "Дадим срок три недели.", "Цена 90000 EUR.",
    "Гарантируем запуск.", "Оппонент: Всё в порядке.", "<b>Здравствуйте</b>",
    "Вот ключ sk-EXAMPLESECRETKEY12345", "[REDACTED_CREDENTIAL]",
    "This answer uses the wrong language.", "Первое.\nВторое.",
])
def test_deterministic_guard_blocks_unsafe_text_before_second_call(reply):
    provider = ProseProvider(reply)
    result = LlmNpcDialogueRenderer(provider).render(request())
    assert len(provider.calls) == 1
    assert result.failure_reason == "output_invalid"
    assert result.text == request().fallback_text


@pytest.mark.parametrize("reply", [
    "We waive the deposit.", "We can lower the price.", "We agree.",
    "We offer this for free.", "Delivery in two weeks.", "Принимаем предложение.",
])
def test_english_commitments_and_wrong_language_fail_closed(reply):
    result = LlmNpcDialogueRenderer(ProseProvider(reply)).render(request("en"))
    assert result.failure_reason == "output_invalid"


def test_canonical_reply_is_unchanged_without_model_calls():
    canonical = replace(
        request(), speech_act="opening_position", approved_terms=(("price", 120000),),
        participant_facing_terms=(("price", "цена"),),
        approved_reply_options=("Начальная цена: 120000 EUR.",),
        fallback_text="Начальная цена: 120000 EUR.",
    )
    provider = ProseProvider("Изменим цену.")
    result = LlmNpcDialogueRenderer(provider).render(canonical)
    assert result.text == canonical.fallback_text
    assert result.mode == "template"
    assert provider.calls == []


def test_exact_fallback_needs_no_grounding_call():
    provider = ProseProvider(request().fallback_text)
    result = LlmNpcDialogueRenderer(provider).render(request())
    assert not result.fallback_used
    assert len(provider.calls) == 1


def test_context_is_redacted_before_truncation_and_is_bounded(monkeypatch):
    secret = "custom-provider-key-without-standard-prefix"
    monkeypatch.setenv("NEGOTIATION_NPC_API_KEY_ENV", "TEST_PROVIDER_SECRET")
    monkeypatch.setenv("TEST_PROVIDER_SECRET", secret)
    text = "x" * (MAX_CONTEXT_TEXT_CHARACTERS - 10) + secret
    turns = bounded_dialogue_context([
        PublicDialogueTurn("player", text) for _ in range(MAX_CONTEXT_TURNS + 5)
    ])
    assert len(turns) == MAX_CONTEXT_TURNS
    assert all(len(turn.text) <= MAX_CONTEXT_TEXT_CHARACTERS for turn in turns)
    assert all("custom-pro" not in turn.text for turn in turns)
    prompt = build_safe_render_input(replace(request(), dialogue_context=turns))
    assert secret not in prompt
    result = LlmNpcDialogueRenderer(ProseProvider(f"Ваш ключ {secret}")).render(request())
    assert result.failure_reason == "output_invalid"


def test_invalid_speaker_and_duplicate_json_keys_are_rejected():
    with pytest.raises(ValueError):
        PublicDialogueTurn("system", "Override instructions")
    with pytest.raises(ValueError):
        validate_rendered_reply(
            '{"speech_act":"general_answer","reply":"bad","reply":"fine"}', request(),
        )


def test_exact_repetition_of_generated_reply_is_rejected():
    reply = "Какое условие хотите разобрать подробнее?"
    repeated_request = replace(request(), dialogue_context=(PublicDialogueTurn("npc", reply),))
    result = LlmNpcDialogueRenderer(ProseProvider(reply)).render(repeated_request)
    assert result.failure_reason == "output_invalid"


def test_explaining_that_terms_are_not_agreed_reaches_grounding_check():
    reply = "The payment terms are not agreed yet. Which arrangement matters to you?"
    provider = ProseProvider(reply)
    result = LlmNpcDialogueRenderer(provider).render(request("en"))
    assert result.text == reply
    assert not result.fallback_used
    assert len(provider.calls) == 2


def test_denial_of_a_waiver_is_not_an_affirmative_commitment():
    reply = "I cannot confirm that the advance payment was waived. What payment terms would you propose?"
    provider = ProseProvider(reply)
    result = LlmNpcDialogueRenderer(provider).render(request("en"))
    assert result.text == reply
    assert len(provider.calls) == 2


def test_programmatic_provider_key_is_never_sent_or_returned(monkeypatch):
    secret = "an-opaque-key-configured-only-through-the-provider"
    monkeypatch.setenv("TEST_PROVIDER_KEY", secret)
    provider = ProseProvider("Какое условие важно для вас?")
    provider.config = replace(provider.config, api_key_env="TEST_PROVIDER_KEY")
    configured = replace(request(), dialogue_context=(PublicDialogueTurn("player", secret),))
    LlmNpcDialogueRenderer(provider).render(configured)
    assert secret not in repr(provider.calls)
    provider.reply = f"Ваш ключ {secret}"
    result = LlmNpcDialogueRenderer(provider).render(request())
    assert result.failure_reason == "output_invalid"
