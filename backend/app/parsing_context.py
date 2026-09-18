"""Bounded public input context. Generated NPC wording is not a parser instruction."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ParseContext:
    active_offer_id: str | None = None
    active_offer_revision: int | None = None
    active_offer_terms: dict[str, int | float] = field(default_factory=dict)
    active_offer_currency: str | None = None
    focused_term_id: str | None = None
    expected_term_id: str | None = None
    ambiguous_offer_reference: bool = False

    def __post_init__(self) -> None:
        for value in (self.active_offer_id, self.focused_term_id, self.expected_term_id):
            if value is not None and (
                not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", value)
            ):
                raise ValueError("Invalid public parse-context identifier")
        if self.active_offer_revision is not None and (
            type(self.active_offer_revision) is not int or self.active_offer_revision < 0
        ):
            raise ValueError("Invalid public offer revision")
        if self.active_offer_currency is not None and (
            not isinstance(self.active_offer_currency, str)
            or not re.fullmatch(r"[A-Z]{3}", self.active_offer_currency)
        ):
            raise ValueError("Invalid public offer currency")
        if not isinstance(self.active_offer_terms, dict) or len(self.active_offer_terms) > 12:
            raise ValueError("Public parse context exceeds its term bound")
        for key, value in self.active_offer_terms.items():
            if (
                not isinstance(key, str)
                or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,79}", key)
                or type(value) not in (int, float)
                or not math.isfinite(value)
            ):
                raise ValueError("Invalid public numeric term")
        if type(self.ambiguous_offer_reference) is not bool:
            raise ValueError("Invalid public baseline ambiguity flag")
        # Detach the bounded snapshot from the caller's mutable offer dictionary.
        object.__setattr__(self, "active_offer_terms", dict(self.active_offer_terms))


_QUOTED_TEXT = re.compile(r'«[^»]*»|“[^”]*”|"[^"\n]*"|(?<!\w)\'[^\'\n]*\'(?!\w)')
_QUESTION_START = re.compile(
    r"^(?:(?:а|и|and|but|then|so)\s+)?(?:почему|зачем|как(?:ую|ой|ие|ие)?|"
    r"что|когда|сколько|каков\w*|какие|какое|какую|какой|можете|можно|"
    r"неужели|разве|правильно\s+ли|why|what|how|when|where|which|can|could|"
    r"would|should|do|does|did|is|are|was|were)\b",
    re.IGNORECASE,
)
_PROPOSAL_START = (
    r"(?:я\s+|мы\s+)?(?:предлага\w*|готов\w*|встречн\w*|можем\s+предложить)|"
    r"(?:i|we)\s+(?:offer|propose|can\s+offer|would\s+offer)|our\s+offer"
)
_INPUT_BOUNDARY = re.compile(
    r"(?<=[?!;])\s*|(?<=\.)\s+(?=[A-ZА-ЯЁ])|"
    rf"(?i:,\s*(?:а\s+|and\s+|but\s+)?(?=(?:{_PROPOSAL_START}|почему|зачем|why|what|how)\b)|"
    r"\s+(?:а|and)\s+(?=(?:почему|зачем|why|what|how)\b))",
)
_REPORTED_POSITION = re.compile(
    r"\b(?:вы\s+(?:сказали|назвали|предложили|указали|просили|заявили)|"
    r"you\s+(?:said|quoted|offered|proposed|stated|asked)|"
    r"(?:your|their|previous|earlier|former)\s+(?:offer|price|rent|quote|proposal)|"
    r"(?:ваш\w*|их|прошл\w*|прежн\w*)\s+(?:предложени\w*|цен\w*|ставк\w*)|"
    r"раньше\s+цен\w*|цен\w*\s+был[аи]|price\s+was)\b",
    re.IGNORECASE,
)
_NEGATED_TERM = re.compile(
    r"\b(?:не\s+(?:предлага\w*|готов\w*|можем|могу|подходит|устраива\w*)|"
    r"(?:do\s+not|don't|cannot|can't|never)\s+(?:offer|propose|accept|meet)|"
    r"not\s+acceptable|doesn't\s+work|won't\s+work)\b",
    re.IGNORECASE,
)
_NUMERIC_NEGATION = re.compile(r"\b(?:не|not|never)\b|\b\w+n't\b", re.IGNORECASE)
_HISTORICAL_EDIT = re.compile(
    r"\b(?:вы|мы|я|you|we|i)\s+(?:(?:уже|already|have|had)\s+)?"
    r"(?:снизил[аи]?|уменьшил[аи]?|повысил[аи]?|увеличил[аи]?|"
    r"reduced|lowered|decreased|increased|raised|shortened|extended)\b",
    re.IGNORECASE,
)
_RELATIVE_VERB = re.compile(
    r"\b(?:сниз\w*|сниж\w*|уменьш\w*|сократ\w*|повыс\w*|повыш\w*|"
    r"увелич\w*|reduce|reducing|decrease|decreasing|lower|lowering|increase|"
    r"increasing|raise|raising|cut|cutting|shorten|shortening|extend|extending)\b",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"\b(?:не|not)\s+((?:(?:eur|rub|usd|gbp|cny)\s*)?"
    r"\d[\d\s,.]*(?:\s*(?:eur|rub|usd|gbp|cny|евро|руб\w*|%))?)"
    r"\s*,?\s*(?:а|but)\s+",
    re.IGNORECASE,
)


def is_relative_change(message: str) -> bool:
    return bool(_RELATIVE_VERB.search(message))


def scope_asserted_message(message: str) -> tuple[str, bool]:
    """Exclude questions and attributed quotations before any numeric extraction.

    Keep explicit proposal clauses in mixed messages. This is deliberately a
    bounded grammar, not a claim of general natural-language understanding.
    """

    unquoted = _QUOTED_TEXT.sub(" ", message)
    clauses = [part.strip() for part in _INPUT_BOUNDARY.split(unquoted) if part.strip()]
    asserted: list[str] = []
    has_question = False
    for clause in clauses:
        if re.search(r'[«»“”"]', clause) or _HISTORICAL_EDIT.search(clause):
            continue
        if "?" in clause or (
            _QUESTION_START.search(clause)
            and not re.match(r"do\s+not\b", clause, re.IGNORECASE)
        ):
            has_question = True
            continue
        corrected, corrections = _CORRECTION.subn("", clause)
        if corrections:
            clause = corrected
        elif _NEGATED_TERM.search(clause) or (
            re.search(r"\d", clause) and _NUMERIC_NEGATION.search(clause)
        ):
            # Retain a separate explicit positive clause after a contrast. The
            # existing proposal-clause parser resolves its public numeric anchor.
            contrast = re.split(r":|\b(?:но|but)\b", clause, flags=re.IGNORECASE)
            positive = [part for part in contrast if not (
                _NEGATED_TERM.search(part) or
                (re.search(r"\d", part) and _NUMERIC_NEGATION.search(part))
            )]
            if not positive:
                continue
            clause = ": ".join(positive)
        reported = _REPORTED_POSITION.search(clause)
        if reported and (re.search(r"\d", clause) or reported.start() == 0) and not is_relative_change(clause):
            # Existing explicit "I can meet that price" references require this
            # adjacent public amount. Do not discard that established grammar.
            if not re.search(rf"\b(?:{_PROPOSAL_START})\b", clause, re.IGNORECASE):
                continue
        asserted.append(clause)
    return "; ".join(asserted), has_question
