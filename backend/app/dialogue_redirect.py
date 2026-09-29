"""Bounded, deterministic topic returns. This is not a relevance classifier."""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from .conversation import mentioned_term_ids
from .engine import deterministic_npc_fallback


_QUESTION = re.compile(r"\?|\b(?:как|какой|какая|какие|кто|где|почему|зачем|есть ли|вы любите|what|who|where|why|how|do you|have you)\b", re.I)
_SIDE_TOPIC = re.compile(
    r"\b(?:собак\w*|кошк\w*|кот(?:а|у|ом)?|питом\w*|гуффи|хобби|увлечен\w*|"
    r"погод\w*|футбол\w*|хокке\w*|политик\w*|президент\w*|"
    r"dog\w*|cat|cats|pet|pets|goofy|hobb\w*|weather|football|hockey|politic\w*|president)\b",
    re.I,
)
_BUSINESS = re.compile(
    r"\d|[%€$₽]|\b(?:услови\w*|сделк\w*|предлож\w*|бюджет\w*|компьютер\w*|"
    r"оборудован\w*|договор\w*|заказ\w*|конфигурац\w*|резерв\w*|скидк\w*|цен\w*|"
    r"terms?|deal|offer|budget|price|computer\w*|equipment|contract|order|configuration|reserve|discount)\b",
    re.I,
)
_DOG = re.compile(r"\b(?:собак\w*|гуффи|dog\w*|goofy)\b", re.I)
_DOG_WELLBEING_RU = re.compile(r"\bкак\s+(?:там\s+)?поживает\b|\bкак\s+себя\s+чувствует\b", re.I)
_DOG_WELLBEING_EN = re.compile(r"\bhow\s+is\b|\bhow(?:'s|\s+does)\b", re.I)


def personal_fact_reply_options(
    message: str,
    language: str,
    training_context: Mapping[str, str],
) -> tuple[str, ...]:
    """Return one authored reply for a supported personal-fact question."""
    if (
        not training_context.get("personal_fact")
        or not _QUESTION.search(message)
        or not _DOG.search(message)
        or _BUSINESS.search(message)
    ):
        return ()
    if language == "ru" and _DOG_WELLBEING_RU.search(message):
        return ("Гуффи чувствует себя хорошо. Спасибо, что спросили.",)
    if language == "en" and _DOG_WELLBEING_EN.search(message):
        return ("Goofy is doing well. Thank you for asking.",)
    return ()


def topic_return_options(
    message: str,
    language: str,
    labels: Mapping[str, str],
    dialogue_context: Sequence,
    training_context: Mapping[str, str],
    current_topic: str | None = None,
) -> tuple[str, ...]:
    """Offer safe wording only for an unrelated question without an approved fact."""
    if not _QUESTION.search(message) or not _SIDE_TOPIC.search(message):
        return ()
    if mentioned_term_ids(message, labels) or _BUSINESS.search(message):
        return ()
    if _DOG.search(message) and training_context.get("personal_fact"):
        return ()
    # Resume a public question's topic, never its numeric values or factual claims.
    focus = current_topic if current_topic in labels else None
    if focus is None:
        for turn in reversed(dialogue_context):
            if turn.speaker == "npc" and "?" in turn.text:
                topics = mentioned_term_ids(turn.text, labels)
                if len(topics) == 1:
                    focus = topics[0]
                break
    if language == "ru":
        follow_up = (
            f"Какой вариант по условию «{labels[focus]}» вы предлагаете?"
            if focus else "Какие условия вы хотели бы обсудить?"
        )
        leads = (
            "Предлагаю продолжить обсуждение нашей сделки.",
            "Давайте сосредоточимся на условиях сделки, которые помогут нам договориться.",
            "Буду рад продолжить разговор об условиях сделки.",
            "Мне важно найти подходящее для нас обоих решение в этих переговорах.",
            "Давайте вернёмся к условиям, которые мы обсуждали.",
            "Предлагаю вместе рассмотреть следующий шаг в переговорах.",
        )
    else:
        follow_up = (
            f"What would you propose for {labels[focus]}?"
            if focus else "Which terms would you like to discuss?"
        )
        leads = (
            "I suggest we continue discussing our deal terms.",
            "Let us focus on deal terms that can help us reach an agreement.",
            "I would be glad to continue discussing the deal terms.",
            "Finding deal terms that work for both of us matters to me.",
            "Let us return to the deal terms we were discussing.",
            "I suggest we consider the next step in our negotiation together.",
        )
    return tuple(f"{lead} {follow_up}" for lead in leads)


def select_varied_fallback(options: tuple[str, ...], message: str, previous: Sequence[str]) -> str:
    """Prefer unseen options, then the least recently used one; preserve replay determinism."""
    initial = options.index(deterministic_npc_fallback(options, message))
    ordered = options[initial:] + options[:initial]
    last_used = {text: index for index, text in enumerate(previous)}
    return min(ordered, key=lambda text: last_used.get(text, -1))
