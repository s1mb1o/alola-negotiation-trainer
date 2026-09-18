"""Bounded public presentation contracts. No private state or policy authority."""

from dataclasses import asdict, dataclass
from decimal import Decimal
import math
import re
from typing import Any

DIFFICULTY_PROFILES = {
    "guided": "Guide the discussion in small steps. Ask about one term at a time. Explain ordinary terms when asked.",
    "easy": "Be approachable and proactive. Ask one concrete question. Help the player keep track of unresolved terms.",
    "normal": "Be professional and concise. Ask for the reason behind a position when it matters. Seek reciprocal changes.",
    "expert": "Challenge unsupported positions politely. Ask for objective grounds and a reciprocal change. Do not coach the player.",
}
STYLE_PROFILES = {
    "pragmatic": "Use direct, plain language. Focus on a workable next step.",
    "analytical": "Use precise language. Ask about the basis of a claim. Do not invent calculations or evidence.",
    "relationship_focused": "Use a warm professional tone. Acknowledge concerns without promising concessions.",
}


@dataclass(frozen=True, slots=True)
class PublicNumericReference:
    slot_id: str
    offer_id: str
    offer_revision: int
    proposer_role: str
    term_id: str
    value: int | float
    currency: str
    display_text: str = ""
    format_version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.slot_id, str) or not re.fullmatch(r"quote_[a-l]", self.slot_id):
            raise ValueError("Invalid numeric reference slot")
        if not isinstance(self.offer_id, str) or not re.fullmatch(r"offer_[A-Za-z0-9]+", self.offer_id):
            raise ValueError("Invalid numeric reference offer")
        if type(self.offer_revision) is not int or self.offer_revision < 1:
            raise ValueError("Invalid numeric reference revision")
        if not isinstance(self.proposer_role, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", self.proposer_role):
            raise ValueError("Invalid numeric reference role")
        if not isinstance(self.term_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", self.term_id):
            raise ValueError("Invalid numeric reference term")
        if type(self.value) not in (int, float) or not math.isfinite(self.value):
            raise ValueError("Invalid numeric reference value")
        if not isinstance(self.currency, str) or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("Invalid numeric reference currency")
        if type(self.format_version) is not int or self.format_version != 1:
            raise ValueError("Unknown numeric reference formatter")
        if not isinstance(self.display_text, str) or len(self.display_text) > 400:
            raise ValueError("Invalid numeric reference display text")

    @property
    def token(self) -> str:
        return f"[[{self.slot_id}]]"

    def text(self, language: str, npc_role: str, labels: dict[str, str]) -> str:
        return self.display_text or self.expected_text(language, npc_role, labels)

    def expected_text(self, language: str, npc_role: str, labels: dict[str, str]) -> str:
        # Formatter version 1 is immutable. Keep exact decimal values; do not round
        # money to integers or percentages to a fixed significant-digit count.
        number = Decimal(str(self.value))
        if self.term_id == "prepayment_fraction":
            number *= 100
        rendered = format(number, ",f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        if language == "ru":
            rendered = rendered.replace(",", "\u00a0").replace(".", ",")
        if self.term_id in {"price", "annual_rent"}:
            rendered += " " + self.currency
        elif self.term_id == "prepayment_fraction":
            rendered += "%"
        elif self.term_id in {"delivery_weeks", "office_readiness_weeks"}:
            if self.value != int(self.value):
                raise ValueError("Numeric reference week value must be integral")
            count = int(self.value)
            unit = ("недель" if 11 <= count % 100 <= 14 else "неделя" if count % 10 == 1
                    else "недели" if count % 10 in {2, 3, 4} else "недель") if language == "ru" else ("week" if count == 1 else "weeks")
            rendered += " " + unit
        term = f"{labels[self.term_id]} {rendered}"
        if language == "ru":
            attribution = "В нашем предложении" if self.proposer_role == npc_role else "В вашем предложении"
        else:
            attribution = "Our offer states" if self.proposer_role == npc_role else "Your offer states"
        return f"{attribution}: {term}."

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def reference_texts(request: Any) -> dict[str, str]:
    return {slot.token: slot.text(request.language, request.npc_role, dict(request.participant_facing_terms))
            for slot in request.numeric_references}


def resolve_numeric_references(reply: str, request: Any, *, allow_resolved: bool = False) -> tuple[str, str]:
    """Return display text and text with exact engine quotes masked for validation."""
    display, masked = reply, reply
    for token, quoted in reference_texts(request).items():
        tokens = reply.count(token)
        resolved = reply.count(quoted) if allow_resolved else 0
        if tokens + resolved > 1:
            raise ValueError("Numeric reference repeated")
        if tokens:
            display = display.replace(token, quoted)
            masked = masked.replace(token, "PUBLIC_OFFER_REFERENCE")
        elif resolved:
            masked = masked.replace(quoted, "PUBLIC_OFFER_REFERENCE")
    if "[[" in masked or "]]" in masked:
        raise ValueError("Unknown numeric reference")
    return display, masked
