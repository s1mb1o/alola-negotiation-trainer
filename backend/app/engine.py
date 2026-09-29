from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from .parsing_context import ParseContext, is_relative_change, scope_asserted_message
from .scenarios import constraint_violations, evaluate_utility, validate_terms


@dataclass(slots=True)
class ParsedAction:
    action: str
    terms_delta: dict[str, Any] = field(default_factory=dict)
    reason_code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


_WALK_AWAY = (
    "ухожу из переговоров",
    "уходим из переговоров",
    "выходим из переговоров",
    "прекращаю переговоры",
    "прекращаем переговоры",
    "отказываюсь от сделки",
    "отказываемся от сделки",
    "сделки не будет",
    "walk away",
    "end negotiations",
    "no deal",
)
_ACCEPT_INTENT = (
    "принимаю предложение",
    "принимаю все условия",
    "согласен на все условия",
    "согласна на все условия",
    "accept the offer",
    "accept all terms",
    "agree to all terms",
    "i accept",
)
_CONFIRM = (
    "подтверждаю принятие",
    "подтверждаю полное принятие",
    "подтверждаю соглашение",
    "да, подтверждаю",
    "confirm acceptance",
    "fully confirm acceptance",
    "i confirm",
)
_CANONICAL_CONFIRMATIONS = {
    "подтверждаю принятие",
    "подтверждаю принятие полного предложения",
    "подтверждаю принятие полного предложения без дополнительных условий",
    "подтверждаю полное принятие предложения без дополнительных условий",
    "подтверждаю соглашение",
    "да, подтверждаю",
    "confirm acceptance",
    "i confirm",
    "i confirm acceptance",
    "i confirm acceptance of the complete offer",
    "i confirm acceptance of the complete offer without additional conditions",
    "i fully confirm acceptance of the complete offer without additional conditions",
}
_CONDITIONAL_MARKERS = (
    "если",
    "при условии",
    "но только",
    "but ",
    "if ",
    "provided that",
    "on condition",
)
_CANCEL = (
    "не подтверждаю",
    "отменяю принятие",
    "отмена подтверждения",
    "cancel acceptance",
    "do not confirm",
)
_REJECT = (
    "отклоняю предложение",
    "предложение отклонено",
    "reject the offer",
)
_WITHDRAW = (
    "отзываю предложение",
    "снимаю предложение",
    "withdraw the offer",
)
_AMBIGUOUS_AGREEMENT = {
    "согласен",
    "согласна",
    "согласны",
    "да",
    "договорились",
    "ок",
    "окей",
    "хорошо",
    "agree",
    "agreed",
    "yes",
    "ok",
    "okay",
    "deal",
}
_ACCEPT_INTENT_PATTERNS = (
    re.compile(r"принима(?:ю|ем)\s+(?:\S+\s+){0,3}?(?:предложени\w*|услови\w*|пакет\w*)"),
    re.compile(
        r"согласн(?:ы|а|ен)\s+(?:на\s+|с\s+|со\s+)?(?:\S+\s+){0,3}?"
        r"(?:предложени\w*|услови\w*|пакет\w*)"
    ),
    re.compile(r"готов(?:ы|а)?\s+принять\s+(?:\S+\s+){0,3}?(?:предложени\w*|услови\w*|пакет\w*)"),
    re.compile(
        r"\b(?:we|i)\s+(?:fully\s+)?accept\s+(?:\S+\s+){0,3}?"
        r"(?:offer|terms|proposal|package|deal)\b"
    ),
    re.compile(
        r"\baccept(?:s|ed|ing)?\s+(?:the|your|this|that|all|these)\s+(?:\S+\s+){0,2}?"
        r"(?:offer|terms|proposal|package|deal)\b"
    ),
    re.compile(r"\bagree\s+to\s+(?:\S+\s+){0,3}?(?:offer|terms|proposal|package|deal)\b"),
)
_NEGATION_TOKENS = {"не", "ни", "нет", "никогда", "not", "never", "no", "cannot", "without"}
_SENTENCE_SPLIT = re.compile(r"[.!?;]")

_RU_NUMBER_WORDS = {
    "ноль": 0,
    "один": 1,
    "одна": 1,
    "одно": 1,
    "одного": 1,
    "одной": 1,
    "одну": 1,
    "два": 2,
    "две": 2,
    "двух": 2,
    "три": 3,
    "трёх": 3,
    "трех": 3,
    "четыре": 4,
    "четырёх": 4,
    "четырех": 4,
    "пять": 5,
    "пяти": 5,
    "шесть": 6,
    "шести": 6,
    "семь": 7,
    "семи": 7,
    "восемь": 8,
    "восьми": 8,
    "девять": 9,
    "девяти": 9,
    "десять": 10,
    "десяти": 10,
    "одиннадцать": 11,
    "одиннадцати": 11,
    "двенадцать": 12,
    "двенадцати": 12,
    "тринадцать": 13,
    "тринадцати": 13,
    "четырнадцать": 14,
    "четырнадцати": 14,
    "пятнадцать": 15,
    "пятнадцати": 15,
    "шестнадцать": 16,
    "шестнадцати": 16,
    "семнадцать": 17,
    "семнадцати": 17,
    "восемнадцать": 18,
    "восемнадцати": 18,
    "девятнадцать": 19,
    "девятнадцати": 19,
    "двадцать": 20,
    "двадцати": 20,
    "тридцать": 30,
    "тридцати": 30,
    "сорок": 40,
    "сорока": 40,
    "пятьдесят": 50,
    "пятидесяти": 50,
    "шестьдесят": 60,
    "шестидесяти": 60,
    "семьдесят": 70,
    "семидесяти": 70,
    "восемьдесят": 80,
    "восьмидесяти": 80,
    "девяносто": 90,
    "девяноста": 90,
    "сто": 100,
    "ста": 100,
    "двести": 200,
    "двухсот": 200,
    "триста": 300,
    "трёхсот": 300,
    "трехсот": 300,
    "четыреста": 400,
    "четырёхсот": 400,
    "четырехсот": 400,
    "пятьсот": 500,
    "пятисот": 500,
    "шестьсот": 600,
    "шестисот": 600,
    "семьсот": 700,
    "семисот": 700,
    "восемьсот": 800,
    "восьмисот": 800,
    "девятьсот": 900,
    "девятисот": 900,
}
_EN_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_MULTIPLIER_WORDS = {
    "тысяча": 1_000,
    "тысячи": 1_000,
    "тысяч": 1_000,
    "тыс": 1_000,
    "миллион": 1_000_000,
    "миллиона": 1_000_000,
    "миллионов": 1_000_000,
    "млн": 1_000_000,
    "thousand": 1_000,
    "million": 1_000_000,
}
_DIGIT_MULTIPLIER = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[ \u00a0\u202f,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"\s*(тыс\.?|тысяч[аи]?|млн\.?|миллион(?:а|ов)?|thousand|million|k|к)(?![\wа-яё])",
    re.IGNORECASE,
)
_TRAILING_PUNCTUATION = ".,;:!?)»\"'"


def _multiply_decimal(raw: str, multiplier: int) -> int:
    normalized = "".join(raw.split()).replace("\u00a0", "").replace("\u202f", "")
    if "," in normalized and "." not in normalized:
        head, _, tail = normalized.rpartition(",")
        normalized = f"{head}.{tail}" if len(tail) <= 2 else normalized.replace(",", "")
    else:
        normalized = normalized.replace(",", "")
    return round(float(normalized) * multiplier)


def _expand_word_numbers(text: str) -> str:
    parts = re.split(r"(\s+)", text)
    output: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if index % 2 == 1 or not part:
            output.append(part)
            index += 1
            continue
        run_end = index
        total = 0
        current = 0
        seen_number = False
        trailing = ""
        cursor = index
        while cursor < len(parts):
            token = parts[cursor] if cursor % 2 == 0 else None
            if token is None:
                cursor += 1
                continue
            stripped = token.rstrip(_TRAILING_PUNCTUATION)
            punctuation = token[len(stripped) :]
            word = (
                stripped.casefold().replace("ё", "е")
                if stripped.casefold() not in _RU_NUMBER_WORDS
                else stripped.casefold()
            )
            lookup = stripped.casefold()
            if lookup in _RU_NUMBER_WORDS or lookup in _EN_NUMBER_WORDS:
                value = _RU_NUMBER_WORDS.get(lookup, _EN_NUMBER_WORDS.get(lookup, 0))
                current += value
                seen_number = True
            elif lookup == "hundred" and seen_number:
                current = (current or 1) * 100
            elif lookup.rstrip(".") in _MULTIPLIER_WORDS and seen_number and current > 0:
                total += current * _MULTIPLIER_WORDS[lookup.rstrip(".")]
                current = 0
            else:
                break
            run_end = cursor
            trailing = punctuation
            cursor += 1
            if punctuation and punctuation != ",":
                break
            del word
        if seen_number:
            total += current
            output.append(f"{total}{trailing}")
            index = run_end + 1
            continue
        output.append(part)
        index += 1
    return "".join(output)


def expand_numbers(message: str) -> str:
    """Rewrite number words and thousand/million abbreviations as plain digits."""

    expanded = _expand_word_numbers(message)

    def _replace(match: re.Match[str]) -> str:
        unit = match.group(2).casefold().rstrip(".")
        multiplier = 1_000 if unit in {"k", "к"} else _MULTIPLIER_WORDS.get(unit, 1_000)
        try:
            return str(_multiply_decimal(match.group(1), multiplier))
        except ValueError:
            return match.group(0)

    return _DIGIT_MULTIPLIER.sub(_replace, expanded)


def _negated_before(normalized: str, index: int) -> bool:
    sentence_start = 0
    for match in _SENTENCE_SPLIT.finditer(normalized, 0, index):
        sentence_start = match.end()
    preceding = normalized[sentence_start:index].split()
    window = preceding[-4:]
    return any(token.strip(",") in _NEGATION_TOKENS or token.endswith("n't") for token in window)


def _walk_away_intent(normalized: str) -> bool:
    for cue in _WALK_AWAY:
        for match in re.finditer(rf"(?<!\w){re.escape(cue)}(?![\w-])", normalized):
            if not _negated_before(normalized, match.start()):
                return True
    return False


def _acceptance_intent(normalized: str) -> bool:
    for phrase in _ACCEPT_INTENT:
        for match in re.finditer(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized):
            if not _negated_before(normalized, match.start()):
                return True
    for pattern in _ACCEPT_INTENT_PATTERNS:
        for match in pattern.finditer(normalized):
            if not _negated_before(normalized, match.start()):
                return True
    return False


_CURRENCY_PATTERNS = {
    "RUB": re.compile(
        r"(?:₽|(?<![\w])(?:rub|rur|rubles?|roubles?|"
        r"руб(?:\.|л(?:ь|я|ей|и|ю|ём|ем)?\.?)?)(?![\w]))",
        re.IGNORECASE,
    ),
    "EUR": re.compile(
        r"(?:€|(?<![\w])(?:eur|euros?|евро)(?![\w]))",
        re.IGNORECASE,
    ),
    "USD": re.compile(
        r"(?:\$|(?<![\w])(?:usd|us\$|dollars?|"
        r"доллар(?:а|ов|у|ы|ом|ах|ами)?)(?![\w]))",
        re.IGNORECASE,
    ),
    "GBP": re.compile(
        r"(?:£|(?<![\w])(?:gbp|pounds?|"
        r"фунт(?:а|ов|у|ы|ом|ах|ами)?)(?![\w]))",
        re.IGNORECASE,
    ),
    "CNY": re.compile(
        r"(?<![\w])(?:cny|rmb|yuan|yuans|юан(?:ь|я|ей|и|ю|ем)?)"
        r"(?![\w])",
        re.IGNORECASE,
    ),
}

_CLAUSE_BOUNDARY = re.compile(
    r"[;:\n]+|(?<=[.!?])\s+(?=[A-ZА-ЯЁ])|"
    r"(?:,\s*|\s+)(?i:\b(?:но|but)\b)\s+"
)
_MONEY_CANDIDATE = re.compile(r"(?<!\d)(\d{1,3}(?:[\s,]\d{3})+|\d{4,}(?:[.,]\d{1,2})?)(?!\d)")
_PROPOSAL_CUES = (
    "готов",
    "предлага",
    "встречн",
    "можем заключить",
    "can proceed",
    "can offer",
    "i offer",
    "we offer",
    "our offer",
    "i can meet",
    "we can meet",
    "i need",
    "we need",
    "i would need",
    "we would need",
    "willing to",
    "prepared to",
    "propose",
)
_REJECTION_CUES = (
    "не подходит",
    "не устраивает",
    "не можем принять",
    "не могу принять",
    "не сможем",
    "не смогу",
    "не готов",
    "can't meet",
    "cannot meet",
    "can't accept",
    "cannot accept",
    "not acceptable",
    "doesn't work",
    "will not work",
    "won't work",
)
_PRICE_REFERENCE_CUES = (
    "при этой цене",
    "при такой цене",
    "при этой ставке",
    "при такой ставке",
    "at this price",
    "at that price",
    "at this rent",
    "at that rent",
    "at this rate",
    "at that rate",
    "this price",
    "that price",
)

_MONETARY_TERM_IDS = ("price", "annual_rent")
_WEEK_TERM_IDS = ("delivery_weeks", "office_readiness_weeks")

_UNSUPPORTED_COMPOSITE_TERM_PATTERNS = (
    re.compile(
        r"\b(?:первая|вторая|ранняя|пилотная)\s+парт(?:ия|ии|ию|ией)\b|"
        r"\b(?:остальн\w*)\s+(?:единиц\w*|устройств\w*|компьютер\w*)\b|"
        r"\b(?:раздел[её]нн\w*|частичн\w*)\s+поставк\w*\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:резервн\w*\s+(?:единиц\w*|устройств\w*)|"
        r"(?:единиц\w*|устройств\w*)\s+(?:в\s+)?резерв\w*)\b|"
        r"\b(?:foc|rma|брак\w*|диагност\w*|замен\w*)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:first|second|early|pilot)\s+(?:delivery\s+)?batch\b|"
        r"\bremaining\s+(?:units?|devices?|computers?)\b|"
        r"\b(?:split|partial)\s+deliver(?:y|ies)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:reserve\s+(?:units?|devices?)|(?:units?|devices?)\s+in\s+reserve|"
        r"foc|rma|defects?|diagnos(?:is|tic)|replacements?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|"
        r"октябр|ноябр|декабр)\w*\b|"
        r"\b(?:january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\b|"
        r"\b\d{4}-\d{2}-\d{2}\b",
        re.IGNORECASE,
    ),
)

_ABUSIVE_PATTERNS = (
    re.compile(r"\bдурак\w*\b", re.IGNORECASE),
    re.compile(r"\bдур(?:а|ы|ой|е|ам|ами|ах)\b", re.IGNORECASE),
    re.compile(r"\bидиот\w*\b", re.IGNORECASE),
    re.compile(r"\bтуп(?:ой|ая|ые|ого|ых|ым|ыми)\b", re.IGNORECASE),
    re.compile(r"\bжули(?:к|ки|ков|кам|ками|ках)\b", re.IGNORECASE),
    re.compile(r"\bзаткнись\b", re.IGNORECASE),
    re.compile(r"\bfuck\s+you\b", re.IGNORECASE),
    re.compile(r"\bidiots?\b", re.IGNORECASE),
    re.compile(r"\bstupid\b", re.IGNORECASE),
    re.compile(r"\bshut\s+up\b", re.IGNORECASE),
)
_GREETING_CUES = (
    "добрый день",
    "доброе утро",
    "добрый вечер",
    "здравствуйте",
    "привет",
    "hello",
    "hi",
    "good morning",
    "good afternoon",
    "good evening",
)
_INTEREST_QUESTION_CUES = (
    "что для вас важно",
    "что вам важно",
    "какое условие для вас приоритет",
    "какие условия для вас важ",
    "ваши приоритет",
    "что для вас приоритет",
    "какие условия для вас принципиальны",
    "какое условие для вас принципиально",
    "что для вас самое важное",
    "что для вас наиболее важно",
    "какие условия наиболее важны",
    "what matters to you",
    "what matters most to you",
    "what terms matter to you",
    "what is important to you",
    "what is most important to you",
    "which term is your priority",
    "which condition is your priority",
    "which term matters most to you",
    "which terms matter most to you",
    "which condition matters most to you",
    "which terms are important",
    "your priorities",
)
_INTEREST_QUESTION_PREFIXES = (
    "что для вас важнее всего",
    "что для вас важнее",
    "какое условие важнее",
    "какие условия важнее",
    "какое условие для вас важнее",
    "какие условия для вас важнее",
)
_COMPLETE_OFFER_REQUEST_CUES = (
    "хотим обсудить",
    "хочу обсудить",
    "готов обсудить",
    "готовы обсудить",
    "обсудить условия",
    "would like to discuss",
    "want to discuss",
    "ready to discuss",
    "discuss the terms",
)


def _normalized(message: str) -> str:
    return " ".join(message.casefold().strip().split())


_PUBLIC_POSITION_TOPIC = re.compile(
    r"\b(?:услов\w*|огранич\w*|предложен\w*|позици\w*|параметр\w*|"
    r"terms?|conditions?|limits?|offer|position)\b",
    re.IGNORECASE,
)
_PUBLIC_POSITION_QUESTION = re.compile(
    r"\b(?:какой|какая|какие|какое|какую|какого|каких|каким|каковы|каково|"
    r"что|what|which)\b",
    re.IGNORECASE,
)
_DIRECT_PUBLIC_POSITION_REQUEST = re.compile(
    r"\b(?:назов(?:и|ите)|скаж(?:и|ите)|перечисл(?:и|ите)|"
    r"озвуч(?:ь|ьте)|повтор(?:и|ите)|tell|list|state|repeat)\b",
    re.IGNORECASE,
)
_COUNTERPART_REFERENCE = re.compile(
    r"\b(?:у\s+вас|ваш\w*|сво\w*|вы|ты|you|your|yours)\b",
    re.IGNORECASE,
)
_ELLIPTICAL_PUBLIC_POSITION_REQUEST = re.compile(
    r"^(?:все|всё|все\s+их|everything|all(?:\s+of\s+them)?)$|"
    r"\b(?:скаж\w*|назов\w*|перечисл\w*|озвуч\w*|повтор\w*|"
    r"tell|say|list|state|repeat)\b",
    re.IGNORECASE,
)


def requests_npc_public_position(
    message: str,
    *,
    recent_messages: tuple[str, ...] = (),
) -> bool:
    """Detect a request to repeat the NPC's already published deal position."""

    normalized = _normalized(message).strip(" .,!?:;\"'«»")
    has_topic = bool(_PUBLIC_POSITION_TOPIC.search(normalized))
    if has_topic and _DIRECT_PUBLIC_POSITION_REQUEST.search(normalized):
        return True
    if (
        has_topic
        and _PUBLIC_POSITION_QUESTION.search(normalized)
        and _COUNTERPART_REFERENCE.search(normalized)
    ):
        return True
    if re.search(
        r"\b(?:какой|какая|какие|какое|какую|какого|каких|каким|каковы|каково|"
        r"что)\b.{0,32}\bу\s+вас\b|\b(?:what|which)\b.{0,24}\byours\b",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if not _ELLIPTICAL_PUBLIC_POSITION_REQUEST.search(normalized):
        return False
    if not (
        _COUNTERPART_REFERENCE.search(normalized)
        or normalized in {"все", "всё", "все их", "everything", "all", "all of them"}
        or re.search(r"\b(?:их|them)\b", normalized, re.IGNORECASE)
    ):
        return False
    context = " ".join(_normalized(item) for item in recent_messages[-4:])
    return bool(_PUBLIC_POSITION_TOPIC.search(context))


def _contains_complete_phrase(normalized: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized))


def _number(value: str) -> float | int:
    normalized = "".join(value.split())
    if normalized.count(",") == 1 and normalized.count(".") == 0:
        tail = normalized.rsplit(",", 1)[1]
        normalized = normalized.replace(",", ".") if len(tail) <= 2 else normalized.replace(",", "")
    else:
        normalized = normalized.replace(",", "")
    result = float(normalized)
    return int(result) if result.is_integer() else result


def _explicit_currencies(message: str) -> set[str]:
    return {currency for currency, pattern in _CURRENCY_PATTERNS.items() if pattern.search(message)}


def _defined_term(term_definitions: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    return next((term_id for term_id in candidates if term_id in term_definitions), None)


def _money_candidates(message: str) -> list[float | int]:
    lowered = message.casefold()
    money_context = bool(_explicit_currencies(message)) or any(
        token in lowered
        for token in (
            "цена",
            "стоим",
            "предлага",
            "аренд",
            "ставк",
            "в год",
            "price",
            "offer",
            "rent",
            "rate",
            "per year",
            "annually",
        )
    )
    if not money_context:
        return []
    values: list[float | int] = []
    for candidate in _MONEY_CANDIDATE.findall(message):
        try:
            value = _number(candidate)
        except ValueError:
            continue
        if value >= 10_000:
            values.append(value)
    return values


def _clause_flags(clause: str) -> tuple[bool, bool]:
    normalized = _normalized(clause).replace("’", "'")
    proposal = any(cue in normalized for cue in _PROPOSAL_CUES)
    rejected = any(cue in normalized for cue in _REJECTION_CUES)
    rejected = rejected or bool(
        re.search(r"превыша\w*.{0,30}бюджет|(?:exceeds|above|over).{0,30}budget", normalized)
    )
    return proposal, rejected


def _select_proposal_clause(
    message: str, term_definitions: dict[str, Any]
) -> tuple[str, str | None]:
    if _defined_term(term_definitions, _MONETARY_TERM_IDS) is None:
        return message, None
    clauses = [clause.strip() for clause in _CLAUSE_BOUNDARY.split(message) if clause.strip()]
    anchors: list[tuple[int, str, list[float | int], bool, bool]] = []
    for index, clause in enumerate(clauses):
        amounts = _money_candidates(clause)
        if not amounts:
            continue
        proposal, rejected = _clause_flags(clause)
        anchors.append((index, clause, amounts, proposal, rejected))
    if not anchors:
        return message, None

    linked_anchors: list[tuple[str, list[float | int], bool, bool]] = []
    for index, clause, amounts, proposal, rejected in anchors:
        linked_clauses = [clause]
        if index > 0 and not _money_candidates(clauses[index - 1]):
            previous_proposal, previous_rejected = _clause_flags(clauses[index - 1])
            if previous_proposal and not previous_rejected:
                proposal = True
                linked_clauses.insert(0, clauses[index - 1])
        if index + 1 < len(clauses) and not _money_candidates(clauses[index + 1]):
            following = _normalized(clauses[index + 1])
            following_proposal, following_rejected = _clause_flags(clauses[index + 1])
            if (
                following_proposal
                and not following_rejected
                and any(cue in following for cue in _PRICE_REFERENCE_CUES)
            ):
                proposal = True
                linked_clauses.append(clauses[index + 1])
        linked_anchors.append((" ".join(linked_clauses), amounts, proposal, rejected))

    viable = [anchor for anchor in linked_anchors if not anchor[3]]
    explicit = [anchor for anchor in viable if anchor[2]]
    candidates = explicit or viable
    if not candidates:
        return "", None
    if len(candidates) > 1 or len(candidates[0][1]) > 1:
        return "", "multiple_offer_candidates"
    return candidates[0][0], None


def _extract_terms(message: str, term_definitions: dict[str, Any]) -> dict[str, Any]:
    lowered = message.casefold()
    result: dict[str, Any] = {}

    monetary_term = _defined_term(term_definitions, _MONETARY_TERM_IDS)
    if monetary_term is not None:
        money_candidates = _money_candidates(message)
        if money_candidates:
            result[monetary_term] = money_candidates[0]

    zero_prepayment = bool(re.search(
        r"\b(?:без|нулев\w*)\s+(?:предоплат\w*|аванс\w*)\b|"
        r"\b(?:no|zero)\s+(?:prepayment|advance)\b",
        lowered,
        re.IGNORECASE,
    ))
    percentage_match = re.search(
        r"(?<!\d)(\d{1,3}(?:[.,]\d+)?)\s*(?:%|процент\w*|percent)", message, re.IGNORECASE
    )
    if zero_prepayment and "prepayment_fraction" in term_definitions:
        result["prepayment_fraction"] = 0.0
    elif percentage_match and any(
        token in lowered for token in ("аванс", "предоплат", "prepay", "advance")
    ):
        fraction = float(percentage_match.group(1).replace(",", ".")) / 100.0
        if "prepayment_fraction" in term_definitions:
            result["prepayment_fraction"] = fraction

    weeks_match = re.search(
        r"(?<!\d)(\d{1,2})\s*(?:[-‐‑‒–—]\s*)?"
        r"(?:(?:полн\w*|календарн\w*|рабоч\w*|full|calendar|business)\s+)?"
        r"(?:недел\w*|нед\b\.?|weeks?\b|wks?\b)",
        lowered,
    )
    week_term = _defined_term(term_definitions, _WEEK_TERM_IDS)
    if weeks_match and week_term is not None:
        result[week_term] = int(weeks_match.group(1))

    quantity_match = re.search(r"(?:количеств\w*|quantity)\D{0,12}(\d{1,6})", lowered)
    if quantity_match and "quantity" in term_definitions:
        result["quantity"] = int(quantity_match.group(1))
    return result


def _contains_unsupported_composite_term(message: str) -> bool:
    """Detect proposal semantics that the scalar MVP grammar cannot bind safely."""

    return any(pattern.search(message) for pattern in _UNSUPPORTED_COMPOSITE_TERM_PATTERNS)


_INPUT_TERM_PATTERNS = {
    "price": re.compile(r"\b(?:цен\w*|стоим\w*|price|cost)\b", re.IGNORECASE),
    "annual_rent": re.compile(r"\b(?:аренд\w*|ставк\w*|rent|rental|rate)\b", re.IGNORECASE),
    "prepayment_fraction": re.compile(r"\b(?:предоплат\w*|аванс\w*|prepay\w*|advance)\b", re.IGNORECASE),
    "delivery_weeks": re.compile(r"\b(?:срок\w*|поставк\w*|доставк\w*|запуск\w*|delivery|lead\s+time|launch|timeline)\b", re.IGNORECASE),
    "office_readiness_weeks": re.compile(r"\b(?:срок\w*|готовност\w*|въезд\w*|readiness|move.in|ready)\b", re.IGNORECASE),
    "quantity": re.compile(r"\b(?:количеств\w*|quantity|units?)\b", re.IGNORECASE),
}
_INPUT_NUMBER = r"\d{1,3}(?:[ \u00a0\u202f,]\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?"
_INPUT_NUMBER_PATTERN = re.compile(rf"(?<![\w.])(?:{_INPUT_NUMBER})(?!\w|\.\d)")
_RELATIVE_MULTI_REFERENCE = re.compile(
    r"\b(?:либо|или|either|or|previous|earlier|original|previously|"
    r"прошл\w*|предыдущ\w*|первоначальн\w*|раньше)\b", re.IGNORECASE
)


def _input_focused_term(
    message: str, term_definitions: dict[str, Any], context: ParseContext | None,
    *, prefer_expected: bool = False,
) -> tuple[str | None, str | None]:
    mentioned = [
        term_id for term_id, pattern in _INPUT_TERM_PATTERNS.items()
        if term_id in term_definitions and pattern.search(message)
    ]
    if len(mentioned) > 1:
        return None, "ambiguous_numeric_reference"
    if mentioned:
        return mentioned[0], None
    if context is None:
        return None, "numeric_answer_requires_term"
    if prefer_expected and context.expected_term_id in term_definitions:
        return context.expected_term_id, None
    choices = {
        term for term in (context.expected_term_id, context.focused_term_id)
        if term is not None
    }
    if len(choices) > 1:
        return None, "ambiguous_numeric_reference"
    if not choices or next(iter(choices)) not in term_definitions:
        return None, "numeric_answer_requires_term"
    return next(iter(choices)), None


def _without_input_currencies(message: str) -> str:
    for pattern in _CURRENCY_PATTERNS.values():
        message = pattern.sub(" ", message)
    return message.strip()


def _numeric_ambiguity_reason(message: str) -> str | None:
    if not re.search(r"\d", message):
        return None
    if re.search(
        r"\b(?:плюс|минус|plus|minus|divide|multiply|делить|умножить|"
        r"скидк\w*|discount|налог\w*|ндс|tax|vat)\b|"
        r"(?<!\w)[−-]\s*\d",
        message, re.IGNORECASE,
    ):
        return "ambiguous_relative_change"
    for unit in (r"%|процент\w*|percent", r"недел\w*|нед\b|weeks?\b|wks?\b"):
        if len(re.findall(rf"(?:{_INPUT_NUMBER})\s*(?:[-‐‑‒–—]\s*)?(?:{unit})", message, re.IGNORECASE)) > 1:
            return "multiple_offer_candidates"
    return None


def _prepayment_values(message: str) -> set[float]:
    """Return explicit prepayment values for contradiction detection."""

    values: set[float] = set()
    if re.search(
        r"\b(?:без|нулев\w*)\s+(?:предоплат\w*|аванс\w*)\b|"
        r"\b(?:no|zero)\s+(?:prepayment|advance)\b",
        message,
        re.IGNORECASE,
    ):
        values.add(0.0)
    for match in re.finditer(
        r"(?<!\d)(\d{1,3}(?:[.,]\d+)?)\s*(?:%|процент\w*|percent)",
        message,
        re.IGNORECASE,
    ):
        if re.search(
            r"(?:предоплат\w*|аванс\w*|prepay\w*|advance)",
            message[max(0, match.start() - 32):match.end() + 32],
            re.IGNORECASE,
        ):
            values.add(float(match.group(1).replace(",", ".")) / 100.0)
    return values


def _supported_relative_change(message: str) -> bool:
    """Ignore qualitative cost language that does not edit a deal term."""

    for clause in re.split(r"[.!?;\n]+", message):
        if not is_relative_change(clause):
            continue
        if re.search(r"\d", clause):
            return True
        if any(pattern.search(clause) for pattern in _INPUT_TERM_PATTERNS.values()):
            return True
    return False


def _contextual_numeric_action(
    message: str,
    term_definitions: dict[str, Any],
    context: ParseContext | None,
    expected_currency: str | None,
) -> ParsedAction | None:
    """Resolve only bounded relative edits and unambiguous short numeric answers."""

    relative = _supported_relative_change(message)
    if relative and not re.search(r"\d|\b(?:наполовину|вдвое|half)\b", message, re.IGNORECASE):
        # A qualitative willingness to change a term is discussion evidence.
        # It is not a numeric edit to the active offer.
        return None
    stripped = _without_input_currencies(message).strip(" .!")
    short = re.fullmatch(
        rf"(?P<value>{_INPUT_NUMBER})\s*(?P<unit>%|процент\w*|percent|"
        r"недел\w*|нед\.?|weeks?|wks?)?", stripped, re.IGNORECASE
    )
    if not relative and short is None:
        return None
    explicit_currencies = _explicit_currencies(message)
    term_id, focus_reason = _input_focused_term(
        message, term_definitions, context, prefer_expected=short is not None,
    )
    if short and explicit_currencies:
        term_id = _defined_term(term_definitions, _MONETARY_TERM_IDS)
        focus_reason = None if term_id else "numeric_answer_requires_term"
    if relative and _RELATIVE_MULTI_REFERENCE.search(message):
        return ParsedAction("clarification", reason_code="ambiguous_numeric_reference")
    if focus_reason:
        return ParsedAction("clarification", reason_code=focus_reason)
    assert term_id is not None
    monetary = term_id in _MONETARY_TERM_IDS
    if explicit_currencies and (
        not monetary or expected_currency is None or explicit_currencies != {expected_currency}
    ):
        return ParsedAction("clarification", reason_code="currency_mismatch", details={
            "expected_currency": expected_currency,
            "provided_currencies": sorted(explicit_currencies),
        })
    if short:
        value = _number(short.group("value"))
        unit = (short.group("unit") or "").casefold()
        percentage = unit == "%" or unit.startswith(("процент", "percent"))
        weeks = bool(unit) and not percentage
        if term_id == "prepayment_fraction":
            if not percentage:
                return ParsedAction("clarification", reason_code="numeric_answer_requires_unit")
            value = float(Decimal(str(value)) / Decimal(100))
        elif percentage or (weeks and term_id not in _WEEK_TERM_IDS):
            return ParsedAction("clarification", reason_code="numeric_answer_requires_unit")
        if term_id in (*_WEEK_TERM_IDS, "quantity") and value != int(value):
            return ParsedAction("clarification", reason_code="numeric_answer_requires_unit")
        return ParsedAction("counter_offer", {term_id: value})
    # A relative edit never searches a transcript or chooses an old offer.
    if context is None or (
        context.active_offer_id is None or context.active_offer_revision is None
        or term_id not in context.active_offer_terms
    ):
        return ParsedAction("clarification", reason_code="relative_change_requires_baseline")
    if context.ambiguous_offer_reference:
        return ParsedAction("clarification", reason_code="ambiguous_numeric_reference")
    if monetary and (
        expected_currency is None or context.active_offer_currency != expected_currency
    ):
        return ParsedAction("clarification", reason_code="currency_mismatch", details={
            "expected_currency": expected_currency,
            "provided_currencies": [context.active_offer_currency] if context.active_offer_currency else [],
        })
    numbers = _INPUT_NUMBER_PATTERN.findall(message)
    target_match = re.search(
        rf"\b(?:до|to)\s+(?P<value>{_INPUT_NUMBER})\s*"
        r"(?P<unit>%|процент\w*|percent|недел\w*|нед\.?|weeks?|wks?)?",
        message,
        re.IGNORECASE,
    )
    if target_match and len(numbers) == 1:
        value = _number(target_match.group("value"))
        unit = (target_match.group("unit") or "").casefold()
        percentage = unit == "%" or unit.startswith(("процент", "percent"))
        weeks = bool(unit) and not percentage
        if term_id == "prepayment_fraction":
            if not percentage:
                return ParsedAction("clarification", reason_code="numeric_answer_requires_unit")
            value = float(Decimal(str(value)) / Decimal(100))
        elif percentage or (weeks and term_id not in _WEEK_TERM_IDS):
            return ParsedAction("clarification", reason_code="numeric_answer_requires_unit")
        if term_id in (*_WEEK_TERM_IDS, "quantity") and value != int(value):
            return ParsedAction("clarification", reason_code="numeric_answer_requires_unit")
        return ParsedAction("counter_offer", {term_id: value}, details={
            "baseline_offer_id": context.active_offer_id,
            "baseline_offer_revision": context.active_offer_revision,
        })
    if len(numbers) != 1 or not re.search(r"\b(?:на|by)\s+", message, re.IGNORECASE):
        return ParsedAction("clarification", reason_code="ambiguous_relative_change")
    percent = bool(re.search(r"%|процент|percent", message, re.IGNORECASE))
    points = bool(re.search(r"процентн\w*\s+пункт\w*|percentage\s+points?", message, re.IGNORECASE))
    if (term_id == "prepayment_fraction" and not points) or (
        percent and not monetary and term_id != "prepayment_fraction"
    ) or (monetary and points):
        return ParsedAction("clarification", reason_code="ambiguous_relative_change")
    decrease = bool(re.search(
        r"\b(?:сниз\w*|сниж\w*|уменьш\w*|сократ\w*|reduce|reducing|decrease|"
        r"decreasing|lower|lowering|cut|cutting|shorten|shortening)\b", message, re.IGNORECASE
    ))
    increase = bool(re.search(
        r"\b(?:повыс\w*|повыш\w*|увелич\w*|increase|increasing|raise|raising|extend|extending)\b",
        message, re.IGNORECASE,
    ))
    if decrease == increase:
        return ParsedAction("clarification", reason_code="ambiguous_relative_change")
    try:
        baseline = Decimal(str(context.active_offer_terms[term_id]))
        delta = Decimal(str(_number(numbers[0])))
        if points:
            delta /= Decimal(100)
        elif percent:
            delta = baseline * delta / Decimal(100)
        resolved = baseline - delta if decrease else baseline + delta
        value = int(resolved) if resolved == resolved.to_integral_value() else float(resolved)
    except (InvalidOperation, OverflowError, ValueError):
        return ParsedAction("clarification", reason_code="ambiguous_relative_change")
    if not math.isfinite(value) or (term_id in (*_WEEK_TERM_IDS, "quantity") and value != int(value)):
        return ParsedAction("clarification", reason_code="ambiguous_relative_change")
    return ParsedAction("counter_offer", {term_id: value}, details={
        "baseline_offer_id": context.active_offer_id,
        "baseline_offer_revision": context.active_offer_revision,
    })


def _contextual_package_action(
    message: str, term_definitions: dict[str, Any], context: ParseContext | None,
    expected_currency: str | None,
) -> ParsedAction | None:
    """Combine separately scoped relative edits without choosing between alternatives."""
    mentioned = {term for term, pattern in _INPUT_TERM_PATTERNS.items()
                 if term in term_definitions and pattern.search(message)}
    if len(mentioned) < 2 or not re.search(r"\d", message) or not _supported_relative_change(message):
        return None
    if re.search(r"\b(?:если|if|unless)\b", message, re.I):
        # Preserve the existing clarification for conditional branches. Only
        # conjunctions of distinct asserted edits are combined here.
        return None
    if re.search(r"\b(?:или|либо|иначе|or|otherwise|either)\b", message, re.I):
        return ParsedAction("clarification", reason_code="multiple_offer_candidates")
    clauses = re.split(r";|,(?!\d)|\b(?:и|and)\b", message, flags=re.I)
    if len(clauses) < 2:
        return None
    terms: dict[str, Any] = {}
    details: dict[str, Any] = {}
    for clause in clauses:
        clause_terms = {term for term, pattern in _INPUT_TERM_PATTERNS.items()
                        if term in term_definitions and pattern.search(clause)}
        if not clause_terms and not re.search(r"\d", clause):
            continue
        if len(clause_terms) != 1:
            return ParsedAction("clarification", reason_code="ambiguous_numeric_reference")
        action = _contextual_numeric_action(clause, term_definitions, context, expected_currency)
        if action is not None and action.action == "clarification":
            return action
        selected, reason = _select_proposal_clause(clause, term_definitions)
        if reason:
            return ParsedAction("clarification", reason_code=reason)
        values = action.terms_delta if action else _extract_terms(selected, term_definitions)
        if set(values) != clause_terms:
            return ParsedAction("clarification", reason_code="unsupported_term_value",
                                details={"term_id": next(iter(clause_terms))})
        if terms.keys() & values.keys():
            return ParsedAction("clarification", reason_code="multiple_offer_candidates")
        terms.update(values)
        if action:
            details.update(action.details)
    return ParsedAction("counter_offer", terms, details=details) if terms else None


def parse_message(
    message: str,
    term_definitions: dict[str, Any],
    *,
    pending_confirmation: bool,
    scenario_currency: str | None = None,
    context: ParseContext | None = None,
) -> ParsedAction:
    message = expand_numbers(message)
    asserted_message, has_question = scope_asserted_message(message)
    normalized = _normalized(asserted_message)

    if _walk_away_intent(normalized):
        return ParsedAction("walk_away")

    expected_currency = scenario_currency.upper() if scenario_currency else None
    if len(_prepayment_values(asserted_message)) > 1:
        return ParsedAction("clarification", reason_code="multiple_offer_candidates")
    ambiguity_reason = _numeric_ambiguity_reason(asserted_message)
    if ambiguity_reason:
        return ParsedAction("clarification", reason_code=ambiguity_reason)
    contextual = _contextual_package_action(
        asserted_message, term_definitions, context, expected_currency
    ) or _contextual_numeric_action(
        asserted_message, term_definitions, context, expected_currency
    )
    if contextual is not None and contextual.action == "clarification":
        return contextual
    proposal_clause, extraction_reason = _select_proposal_clause(asserted_message, term_definitions)
    if extraction_reason is not None:
        return ParsedAction("clarification", reason_code=extraction_reason)
    terms = contextual.terms_delta if contextual else _extract_terms(proposal_clause, term_definitions)
    if not contextual:
        # One monetary anchor can have explicit secondary terms in later sentences.
        # Attribution, questions, and negation were removed before this extraction.
        terms.update({key: value for key, value in _extract_terms(asserted_message, term_definitions).items()
                      if key not in _MONETARY_TERM_IDS})
    if terms and _contains_unsupported_composite_term(message):
        return ParsedAction("clarification", reason_code="unscored_proposal")

    explicit_currencies = _explicit_currencies(proposal_clause)
    mismatched_currencies = sorted(
        currency
        for currency in explicit_currencies
        if expected_currency is not None and currency != expected_currency
    )
    has_monetary_term = any(term_id in terms for term_id in _MONETARY_TERM_IDS)
    if has_monetary_term and mismatched_currencies:
        return ParsedAction(
            "clarification",
            reason_code="currency_mismatch",
            details={
                "expected_currency": expected_currency,
                "provided_currencies": sorted(explicit_currencies),
            },
        )

    mentioned_terms = {
        term_id
        for term_id, pattern in _INPUT_TERM_PATTERNS.items()
        if term_id in term_definitions and pattern.search(asserted_message)
    }
    if len(terms) > 1 and re.search(r"\b(?:или|либо|иначе|or|otherwise|either)\b", asserted_message, re.I):
        return ParsedAction("clarification", reason_code="multiple_offer_candidates")
    missing_asserted_terms = sorted(mentioned_terms - set(terms))
    if terms and missing_asserted_terms:
        return ParsedAction(
            "clarification",
            reason_code="unsupported_term_value",
            details={"term_id": missing_asserted_terms[0]},
        )

    if pending_confirmation:
        if any(phrase in normalized for phrase in _CANCEL):
            return ParsedAction("cancel_acceptance")
        conditional = any(marker in normalized for marker in _CONDITIONAL_MARKERS)
        if terms or conditional:
            if terms:
                return contextual or ParsedAction("counter_offer", terms)
            return ParsedAction("clarification", reason_code="conditional_confirmation")
        canonical = normalized.rstrip(".! ")
        if canonical in _CANONICAL_CONFIRMATIONS:
            return ParsedAction("confirm_acceptance")
        if any(phrase in normalized for phrase in _CONFIRM):
            return ParsedAction("clarification", reason_code="ambiguous_confirmation")
        if terms:
            return ParsedAction("counter_offer", terms)
        return ParsedAction("clarification", reason_code="ambiguous_confirmation")

    if any(phrase in normalized for phrase in _WITHDRAW):
        return ParsedAction("withdraw")
    if any(phrase in normalized for phrase in _REJECT):
        return ParsedAction("reject")
    if _acceptance_intent(normalized):
        if terms:
            return contextual or ParsedAction("counter_offer", terms)
        if any(marker in normalized for marker in _CONDITIONAL_MARKERS):
            return ParsedAction("clarification", reason_code="ambiguous_agreement_scope")
        return ParsedAction("acceptance_intent")
    if normalized.strip(" .!?") in _AMBIGUOUS_AGREEMENT:
        return ParsedAction("clarification", reason_code="ambiguous_agreement_scope")
    if terms:
        return contextual or ParsedAction("counter_offer", terms)
    if has_question or "?" in message or normalized.startswith(
        ("что ", "как ", "когда ", "почему ", "можете ", "what ", "how ", "when ", "can ")
    ):
        return ParsedAction("question")
    return ParsedAction("inform")


def offer_is_complete(scenario: dict[str, Any], terms: dict[str, Any]) -> bool:
    from .supply import is_supply_scenario, unresolved_supply_terms
    if is_supply_scenario(scenario):
        return not unresolved_supply_terms(scenario, terms)
    return not any(term not in terms for term in scenario["terms"]["required_term_ids"])


def offer_is_acceptable(scenario: dict[str, Any], role: str, terms: dict[str, Any]) -> bool:
    if validate_terms(scenario, terms, complete=True):
        return False
    if constraint_violations(scenario, role, terms):
        return False
    utility = evaluate_utility(scenario, role, terms)
    reservation = float(scenario["utility_model"]["role_models"][role]["reservation_utility"])
    return utility >= reservation


def binding_violations(scenario: dict[str, Any], terms: dict[str, Any]) -> list[str]:
    """Return every reason that stops a complete package from binding for any role."""

    violations = validate_terms(scenario, terms, complete=True)
    for role in scenario["roles"]:
        violations.extend(constraint_violations(scenario, role, terms))
    return sorted(set(violations))


def offer_is_bindable(scenario: dict[str, Any], terms: dict[str, Any]) -> bool:
    return not binding_violations(scenario, terms)


def deterministic_counter_terms(
    scenario: dict[str, Any],
    npc_role: str,
    received_terms: dict[str, Any],
    opening_terms: dict[str, Any],
    previous_counter_terms: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Move the monetary term halfway from the received offer towards the NPC anchor.

    The anchor is the NPC's own previous counteroffer when one exists, so the NPC never
    asks for more than it asked before. The opening terms anchor only the first counter.
    """

    candidate = dict(received_terms)
    monetary_term = next(
        (
            term_id
            for term_id in _MONETARY_TERM_IDS
            if term_id in candidate and term_id in opening_terms
        ),
        None,
    )
    if monetary_term is None:
        return dict(opening_terms)
    current = float(candidate[monetary_term])
    anchor_terms = previous_counter_terms or opening_terms
    anchor = float(anchor_terms.get(monetary_term, opening_terms[monetary_term]))
    function = scenario["utility_model"]["role_models"][npc_role]["value_functions"].get(
        monetary_term
    )
    prefers_higher = True
    if function and function["type"] == "linear":
        prefers_higher = float(function["utility_at_max"]) >= float(function["utility_at_min"])
    midpoint = (current + anchor) / 2
    if prefers_higher:
        candidate[monetary_term] = int(round(max(current, min(anchor, midpoint))))
    else:
        candidate[monetary_term] = int(round(min(current, max(anchor, midpoint))))
    if offer_is_acceptable(scenario, npc_role, candidate):
        return candidate
    if previous_counter_terms and offer_is_acceptable(scenario, npc_role, previous_counter_terms):
        return dict(previous_counter_terms)
    return dict(opening_terms)


def _format_money(value: Any, currency: str, language: str) -> str:
    number = format(Decimal(str(value)), ",f")
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    if language == "ru":
        number = number.replace(",", "\u00a0").replace(".", ",")
        symbol = {"RUB": "₽", "EUR": "€", "USD": "$", "GBP": "£"}.get(currency, currency)
        return f"{number} {symbol}"
    return f"{currency} {number}"


def _format_percentage(value: Any) -> str:
    number = format(Decimal(str(value)) * 100, "f")
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return number + "%"


def _ru_week_word(value: int) -> str:
    if value % 10 == 1 and value % 100 != 11:
        return "неделю"
    if value % 10 in {2, 3, 4} and value % 100 not in {12, 13, 14}:
        return "недели"
    return "недель"


def classify_npc_speech_act(message: str, player_action: str) -> str:
    """Select a non-binding NPC speech act from the latest public player message."""

    normalized = _normalized(message)
    if any(pattern.search(normalized) for pattern in _ABUSIVE_PATTERNS):
        return "abusive_language_boundary"
    if any(normalized.startswith(cue) for cue in _INTEREST_QUESTION_PREFIXES) or any(
        cue in normalized for cue in _INTEREST_QUESTION_CUES
    ):
        return "qualitative_interest_answer"
    greeting_only = any(
        re.fullmatch(rf"[\s,.!?;:—-]*{re.escape(cue)}[\s,.!?;:—-]*", normalized)
        for cue in _GREETING_CUES
    )
    # A greeting at the start of a substantive message is social context, not its intent.
    if player_action == "question" and not greeting_only:
        return "general_answer"
    if greeting_only:
        return "greeting"
    if any(cue in normalized for cue in _COMPLETE_OFFER_REQUEST_CUES):
        return "request_complete_offer"
    if player_action == "question":
        return "general_answer"
    return "acknowledge_information"


def participant_term_labels(scenario: dict[str, Any], language: str) -> dict[str, str]:
    """Return domain-safe labels for participant-facing authored terms."""

    scenario_id = str(scenario.get("id", ""))
    is_saas = scenario_id.startswith("saas_subscription")
    labels = {
        "ru": {
            "price": "цена",
            "annual_rent": "годовая арендная плата",
            "prepayment_fraction": "размер предоплаты",
            "delivery_weeks": "срок запуска" if is_saas else "срок поставки",
            "office_readiness_weeks": "срок готовности офиса к въезду",
            "quantity": "количество",
        },
        "en": {
            "price": "price",
            "annual_rent": "annual rent",
            "prepayment_fraction": "prepayment",
            "delivery_weeks": "launch timeline" if is_saas else "delivery timeline",
            "office_readiness_weeks": "time until the office is ready for move-in",
            "quantity": "quantity",
        },
    }[language]
    return {
        term_id: labels.get(term_id, term_id.replace("_", " "))
        for term_id in scenario.get("terms", {}).get("definitions", {})
    }


def _format_term(
    term_id: str,
    value: Any,
    *,
    currency: str,
    language: str,
    labels: dict[str, str],
) -> str:
    label = labels.get(term_id, term_id.replace("_", " "))
    if language == "ru":
        # Package lists read as nominative items: "цена X, предоплата Y%, срок Z".
        label = {
            "annual_rent": "годовая арендная плата",
            "prepayment_fraction": "предоплата",
            "office_readiness_weeks": "готовность офиса к въезду через",
        }.get(term_id, label)
    if term_id in _MONETARY_TERM_IDS:
        rendered_value = _format_money(value, currency, language)
    elif term_id == "prepayment_fraction":
        rendered_value = _format_percentage(value)
    elif term_id in _WEEK_TERM_IDS:
        weeks = int(value)
        if language == "ru":
            rendered_value = f"{weeks} {_ru_week_word(weeks)}"
        else:
            rendered_value = f"{weeks} {'week' if weeks == 1 else 'weeks'}"
    else:
        rendered_value = str(value)
    if language == "ru":
        return f"{label} {rendered_value}"
    return f"{label} of {rendered_value}"


def _format_package(
    terms: dict[str, Any],
    *,
    scenario: dict[str, Any],
    language: str,
) -> str:
    labels = participant_term_labels(scenario, language)
    required = list(scenario.get("terms", {}).get("required_term_ids", ()))
    ordered = [term_id for term_id in required if term_id in terms]
    ordered.extend(term_id for term_id in terms if term_id not in ordered)
    return ", ".join(
        _format_term(
            term_id,
            terms[term_id],
            currency=str(scenario.get("currency", "RUB")),
            language=language,
            labels=labels,
        )
        for term_id in ordered
    )


def _dialogue_subject(scenario: dict[str, Any], language: str) -> str:
    scenario_id = str(scenario.get("id", ""))
    family = scenario_id.rsplit("_", 1)[0]
    subjects = {
        "en": {
            "freight_contract": "freight terms",
            "saas_subscription": "subscription and launch terms",
            "office_lease": "lease terms",
        },
        "ru": {
            "freight_contract": "условия перевозки",
            "supplier": "условия поставки промышленных компьютеров",
            "saas_subscription": "условия подписки и запуска",
            "office_lease": "условия аренды",
        },
    }
    fallback = "deal terms" if language == "en" else "условия сделки"
    return subjects[language].get(family, fallback)


def npc_message_options(
    language: str,
    speech_act: str,
    terms: dict[str, Any] | None = None,
    *,
    scenario: dict[str, Any] | None = None,
    priority_labels: tuple[str, ...] = (),
    missing_labels: tuple[str, ...] = (),
    focused_labels: tuple[str, ...] = (),
    reason_texts: tuple[str, ...] = (),
    difficulty: str = "normal",
    conversation_style: str = "pragmatic",
    requested_label: str | None = None,
    exchange_labels: tuple[str, ...] = (),
    changed_labels: tuple[str, ...] = (),
    retained_labels: tuple[str, ...] = (),
    objection_labels: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Return the closed set of engine-approved natural replies for one speech act."""

    configured_scenario = scenario or {"terms": {"definitions": {}}, "currency": "RUB"}
    package = _format_package(terms or {}, scenario=configured_scenario, language=language)
    subject = _dialogue_subject(configured_scenario, language)
    primary_priority = priority_labels[0] if priority_labels else None
    other_priorities = ", ".join(priority_labels[1:])
    missing = ", ".join(missing_labels)
    focused = ", ".join(focused_labels)
    comparison = ""
    if speech_act == "complete_counteroffer" and changed_labels:
        changed = ", ".join(changed_labels)
        retained = ", ".join(retained_labels)
        if language == "ru":
            comparison = f"Спасибо за предложение. В этом пакете мне нужно изменить условия: {changed}. "
            if retained:
                comparison += f"В моём встречном пакете сохраняются ваши условия: {retained}. "
        else:
            comparison = f"Thank you for the proposal. In this package, I need to change: {changed}. "
            if retained:
                comparison += f"My counteroffer retains your terms for: {retained}. "

    if reason_texts:
        explanation = " ".join(reason_texts)
        return (explanation,)
    if speech_act == "offer_rejection" and objection_labels:
        objections = ", ".join(objection_labels)
        if language == "ru":
            return (f"Спасибо за предложение. В этом пакете мне не подходят условия: {objections}. Предлагаю пересмотреть их и снова оценить пакет целиком.",)
        return (f"Thank you for the proposal. In this package, these terms do not work for me: {objections}. I suggest revising them so we can evaluate the whole package again.",)
    if speech_act == "complete_counteroffer" and exchange_labels:
        trade = ", ".join(exchange_labels)
        if language == "ru":
            return (f"{comparison}Предлагаю обмен уступками: изменение цены связано с изменением условий «{trade}». Полный пакет: {package}.",)
        return (f"{comparison}I propose a trade: the price change depends on changes to {trade}. The complete package is: {package}.",)
    if speech_act == "public_position_restatement":
        if language == "ru":
            unresolved = f" Пока не согласовано: {missing}." if missing else ""
            return (
                f"Повторю мою последнюю публичную позицию: {package}.{unresolved}",
                f"Мои последние названные условия: {package}.{unresolved}",
                f"Моё последнее предложение было таким: {package}.{unresolved}",
            )
        unresolved = f" Still unresolved: {missing}." if missing else ""
        return (
            f"I will repeat my latest public position: {package}.{unresolved}",
            f"My latest stated terms were: {package}.{unresolved}",
            f"My latest offer was: {package}.{unresolved}",
        )
    if requested_label:
        if speech_act == "acknowledge_partial_offer":
            if language == "ru":
                return (f"Спасибо, учёл предложенные условия. Чтобы оценить пакет, уточните, пожалуйста, условие «{requested_label}».",)
            return (f"Thank you, I have noted your proposed terms. To evaluate the package, please specify {requested_label}.",)
        if language == "ru":
            lead = "Давайте разберём это по шагам." if difficulty in {"guided", "easy"} else "Продолжим обсуждение."
            if conversation_style == "relationship_focused":
                lead = "Давайте найдём подходящий вариант."
            if difficulty == "expert":
                return (f"Какую позицию по условию «{requested_label}» вы можете обосновать?",)
            return (f"{lead} Какой вариант по условию «{requested_label}» вы предлагаете?",
                    f"Обсудим условие «{requested_label}». Что вы предлагаете?")
        lead = "Let us work through this step by step." if difficulty in {"guided", "easy"} else "Let us continue."
        if conversation_style == "relationship_focused":
            lead = "Let us look for a workable option."
        if difficulty == "expert":
            return (f"What position on {requested_label} can you substantiate?",)
        return (f"{lead} What would you propose for {requested_label}?",
                f"Let us discuss {requested_label}. What do you propose?")
    if speech_act == "acknowledge_partial_offer" and difficulty in {"guided", "easy", "expert"}:
        if difficulty == "expert":
            return (("На чём основана ваша позиция и какое встречное изменение вы предлагаете?",)
                    if language == "ru" else ("What supports your position, and what reciprocal change do you propose?",))
        return (("Начнём с этой позиции. Что для вас важно в этом условии?",)
                if language == "ru" else ("Let us start with that position. What matters to you about this term?",))
    if speech_act == "focused_discussion":
        if language == "ru":
            return (
                f"Обсудим условие «{focused}». Какой вариант вы предлагаете?",
                f"Начнём с условия «{focused}». Какую позицию вы хотите предложить?",
            )
        return (
            f"Let us focus on {focused}. What would you propose?",
            f"We can start with {focused}. What is your position on that term?",
        )
    if speech_act == "acknowledge_partial_offer":
        if language == "ru":
            return (
                "Это ваше предложение по части условий, а не окончательная договорённость. На чём основана эта позиция?",
                "Вы обозначили свою позицию. Что делает этот вариант подходящим для вас?",
            )
        return (
            "That is your proposed position, not a final agreement. What is the basis for it?",
            "You have outlined your position. What makes that option work for you?",
        )

    if language == "en":
        if speech_act == "opening_position":
            return (
                f"Hello. I propose that we discuss the {subject}. "
                f"My opening position is: {package}. "
                "I propose that we discuss the remaining terms.",
            )
        if speech_act == "opening_offer":
            return (
                f"Hello. I propose that we discuss the {subject}. My opening offer is: {package}.",
            )
        if speech_act == "offer_acceptance":
            return (f"I accept the complete offer: {package}.",)
        if speech_act == "offer_rejection":
            return (
                "Thank you for the proposal. I cannot accept this combination of terms. Which term could you reconsider?",
            )
        if speech_act == "complete_counteroffer":
            return (f"{comparison}My complete counteroffer is: {package}.",)
        if speech_act == "greeting":
            return (
                f"Hello. I am ready to discuss the {subject} and understand your proposed package.",
                f"Good day. Let us discuss the {subject} and look for a workable package.",
                f"Hello. Thank you for starting the conversation. What package of {subject} would you like to discuss?",
            )
        if speech_act == "qualitative_interest_answer":
            if primary_priority is None:
                return (
                    f"The complete package of {subject} matters to us.",
                    f"We consider the {subject} together as a complete package.",
                )
            if not other_priorities:
                return (
                    f"Our main priority is {primary_priority}.",
                    f"The most important term for us is {primary_priority}.",
                )
            return (
                f"Our main priority is {primary_priority}. We also consider {other_priorities}.",
                f"The most important term for us is {primary_priority}. Other important terms are {other_priorities}.",
            )
        if speech_act == "abusive_language_boundary":
            return (
                "I am ready to continue, but please keep the conversation respectful and focused on the deal.",
                "Let us keep the discussion professional. I can continue when we return to the deal terms.",
            )
        if speech_act == "request_complete_offer":
            if missing:
                return (
                    f"I am ready to discuss the {subject}. To complete the package, please specify: {missing}.",
                    f"Still open: {missing}. Please propose a complete package of terms.",
                    f"Let us review the {subject} as a package. We still need to settle: {missing}.",
                )
            return (
                f"I am ready to discuss the {subject}. Please propose a complete package.",
                f"Let us review the {subject} as a package. What complete set of terms do you propose?",
                f"To evaluate a proposal I need the complete package of {subject}.",
            )
        if speech_act == "general_answer":
            return (
                "Let us clarify that point. What would you like to understand about these terms?",
                "What concerns you most about the proposed terms?",
            )
        return (
            "What would you like to change in the proposed terms?",
            "Thank you, I have noted that point. What would you like to propose for the deal terms?",
            "Let us examine that concern. Which term would you like to discuss first?",
        )

    if speech_act == "opening_position":
        return (
            f"Добрый день. Предлагаю обсудить {subject}. "
            f"Моя начальная позиция: {package}. Остальные условия предлагаю обсудить.",
        )
    if speech_act == "opening_offer":
        return (
            f"Добрый день. Предлагаю обсудить {subject}. Моё начальное предложение: {package}.",
        )
    if speech_act == "offer_acceptance":
        return (f"Принимаю полное предложение: {package}.",)
    if speech_act == "offer_rejection":
        return ("Спасибо за предложение. Пока не могу принять такое сочетание условий. Какое из условий вы готовы пересмотреть?",)
    if speech_act == "complete_counteroffer":
        return (f"{comparison}Моё полное встречное предложение: {package}.",)
    if speech_act == "greeting":
        return (
            f"Добрый день. Готов обсудить {subject} и понять, какой пакет вы предлагаете.",
            f"Здравствуйте. Давайте обсудим {subject} и найдём рабочий пакет.",
            f"Добрый день. Спасибо, что начали разговор. Какой пакет по теме «{subject}» вы хотите обсудить?",
        )
    if speech_act == "qualitative_interest_answer":
        if primary_priority is None:
            return (
                f"Для нас важен полный пакет по теме «{subject}».",
                f"Мы рассматриваем {subject} вместе, в составе полного пакета.",
            )
        if not other_priorities:
            return (
                f"Главный приоритет для нас — {primary_priority}.",
                f"Наиболее важное условие для нас — {primary_priority}.",
            )
        return (
            f"Главный приоритет для нас — {primary_priority}. Также важны {other_priorities}.",
            f"Наиболее важное условие для нас — {primary_priority}. Другие значимые условия — {other_priorities}.",
        )
    if speech_act == "abusive_language_boundary":
        return (
            "Я готов продолжить, но прошу вести разговор уважительно и обсуждать условия сделки.",
            "Давайте сохраним деловой тон. Я продолжу переговоры, когда мы вернёмся к условиям сделки.",
        )
    if speech_act == "request_complete_offer":
        if missing:
            return (
                f"Готов обсудить {subject}. Чтобы пакет был полным, уточните, пожалуйста: {missing}.",
                f"Пока не согласовано: {missing}. Предложите, пожалуйста, полный пакет условий.",
                f"Давайте рассмотрим {subject} как пакет. Осталось определить: {missing}.",
            )
        return (
            f"Готов обсудить {subject}. Предложите, пожалуйста, полный пакет.",
            f"Давайте рассмотрим {subject} как пакет. Какой полный набор условий вы предлагаете?",
            f"Чтобы оценить предложение, мне нужен полный пакет по теме «{subject}».",
        )
    if speech_act == "general_answer":
        return (
            "Давайте уточним этот момент. Что вы хотели бы понять об этих условиях?",
            "Что именно вас беспокоит в предложенных условиях?",
        )
    return (
        "Что вы хотели бы изменить в предложенных условиях?",
        "Спасибо, я учёл этот момент. Что вы предлагаете по условиям сделки?",
        "Давайте разберём ваш вопрос. С какого условия начнём?",
    )


def deterministic_npc_fallback(options: tuple[str, ...], context_text: str) -> str:
    """Select a stable fallback variant without process-random hash state."""

    if len(options) == 1:
        return options[0]
    index = hashlib.sha256(context_text.encode("utf-8")).digest()[0] % len(options)
    return options[index]


def npc_message(
    language: str,
    action: str,
    terms: dict[str, Any] | None = None,
    *,
    scenario: dict[str, Any] | None = None,
    speech_act: str | None = None,
    priority_labels: tuple[str, ...] = (),
    context_text: str = "",
    missing_labels: tuple[str, ...] = (),
) -> str:
    resolved_speech_act = speech_act
    if resolved_speech_act is None:
        resolved_speech_act = {
            "accept": "offer_acceptance",
            "reject": "offer_rejection",
            "counter_offer": "complete_counteroffer",
        }.get(action, "request_complete_offer")
    options = npc_message_options(
        language,
        resolved_speech_act,
        terms,
        scenario=scenario,
        priority_labels=priority_labels,
        missing_labels=missing_labels,
    )
    return deterministic_npc_fallback(options, context_text)


def format_terms(terms: dict[str, Any], *, scenario: dict[str, Any], language: str) -> str:
    """Public wrapper around the canonical package formatting used by NPC messages."""
    from .supply import format_supply_terms, is_supply_scenario
    if is_supply_scenario(scenario):
        return format_supply_terms(scenario, terms, language)
    return _format_package(terms, scenario=scenario, language=language)


def role_label(role: str, language: str) -> str:
    # The Web UI dictionary uses these words for the two authored roles in every scenario.
    labels = {
        "ru": {"buyer": "Покупатель", "seller": "Поставщик"},
        "en": {"buyer": "Buyer", "seller": "Supplier"},
    }
    return labels.get(language, labels["en"]).get(role, role)


def clarification_text(
    language: str,
    reason_code: str,
    *,
    expected_currency: str | None = None,
    term_label: str | None = None,
) -> str:
    # Numeric input errors are not acceptance questions. Preserve the specific cause.
    messages = {
        "numeric_answer_requires_term": (
            "К какому условию относится указанное число? Укажите название условия вместе со значением.",
            "Which term does this number refer to? Please give the term and its value.",
        ),
        "numeric_answer_requires_unit": (
            f"Уточните, пожалуйста, единицу измерения{f' для условия «{term_label}»' if term_label else ''}: сумму, проценты или недели.",
            f"Please specify the unit{f' for {term_label}' if term_label else ''}: money, percent, or weeks.",
        ),
        "ambiguous_numeric_reference": (
            "Уточните, пожалуйста, какое значение вы предлагаете для каждого условия. Укажите одно значение на условие.",
            "Please specify the value you propose for each term. Give one value per term.",
        ),
        "relative_change_requires_baseline": (
            "Неясно, от какого предложения считать изменение. Укажите, пожалуйста, итоговое значение условия.",
            "It is unclear which offer is the baseline. Please specify the resulting term value.",
        ),
        "ambiguous_relative_change": (
            "Уточните, пожалуйста, итоговое значение после изменения. Для предоплаты укажите итоговый процент.",
            "Please specify the resulting value after the change. For prepayment, give the final percentage.",
        ),
        "unsupported_term_value": (
            f"Не удалось определить значение{f' условия «{term_label}»' if term_label else ' одного из условий'}. Укажите, пожалуйста, его явно.",
            f"I could not identify the value{f' for {term_label}' if term_label else ' of one term'}. Please state it explicitly.",
        ),
    }
    if reason_code in messages:
        return messages[reason_code][language == "en"]
    if language == "en":
        if reason_code == "multiple_offer_candidates":
            return (
                "Submit one offer package at a time. Multiple alternatives are not supported yet."
            )
        if reason_code == "currency_mismatch":
            return (
                f"This scenario uses {expected_currency}. Restate the amount in "
                f"{expected_currency}."
            )
        if reason_code == "unscored_proposal":
            return (
                "This proposal contains a schedule, contingency, reserve, or other "
                "composite term outside the current deal grammar. Restate one complete "
                "offer using the displayed terms."
            )
        if reason_code == "ambiguous_confirmation":
            return "Do you confirm acceptance of the complete displayed offer, or cancel it?"
        if reason_code == "ambiguous_agreement_scope":
            return "Do you accept the complete active offer, or only agree with one condition?"
        return "Please clarify which change you propose to the deal terms."
    if reason_code == "multiple_offer_candidates":
        return "Отправьте один пакет предложения. Несколько альтернатив пока не поддерживаются."
    if reason_code == "currency_mismatch":
        return (
            f"В этом сценарии используется валюта {expected_currency}. "
            f"Укажите сумму в {expected_currency}."
        )
    if reason_code == "unscored_proposal":
        return (
            "Предложение содержит график, условие, резерв или другую составную конструкцию "
            "вне текущей грамматики сделки. Сформулируйте один полный пакет только через "
            "показанные условия."
        )
    if reason_code == "ambiguous_confirmation":
        return "Вы подтверждаете принятие всего показанного предложения или отменяете его?"
    if reason_code == "ambiguous_agreement_scope":
        return "Вы принимаете всё активное предложение или соглашаетесь только с одним условием?"
    return "Уточните, пожалуйста, какое изменение условий сделки вы предлагаете."
