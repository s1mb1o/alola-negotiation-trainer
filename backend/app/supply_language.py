"""Source-bound language actions and a bounded policy for the supply reference.

This module proposes actions. The service validates and commits them separately.
No text in this module confirms an agreement without the pending protocol state.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any


@dataclass(frozen=True, slots=True)
class SupplyAction:
    action: str
    terms: dict[str, Any] | None = None
    source_revision: int = 0
    clarification: str | None = None
    topic: str = "general"
    clarification_code: str | None = None


@dataclass(frozen=True, slots=True)
class SupplyDecision:
    action: str
    terms: dict[str, Any] | None = None
    text: str = ""
    topic: str = "general"


def _say(language: str, ru: str, en: str) -> str:
    return ru if language == "ru" else en


def _normal(message: str) -> str:
    return re.sub(r"\s+", " ", message.casefold().replace("ё", "е")).strip()


def _topic(text: str) -> str:
    if re.search(
        r"диагност|неисправ|аппаратн|hardware|diagnos|software|конфигурац|инфраструктур|ремонт|repair|сбой|сбои",
        text,
    ):
        return "diagnosis"
    if re.search(
        r"резерв|\bfoc\b|free of charge|reserve|запасн|брак|невостребован|неиспользован|unused|лишни.*устройств",
        text,
    ):
        return "reserve"
    if re.search(r"аванс|предоплат|prepay|advance|оплат|payment", text):
        return "payment"
    if re.search(r"постав|ноябр|november|delivery|\bddp\b|интеграц|integration", text):
        return "delivery"
    if re.search(r"цен|стоимост|бюджет|price|budget|cost|discount|скидк", text):
        return "price"
    return "general"


def _clarify(
    language: str, revision: int, topic: str, code: str = "ambiguous_composite_scope"
) -> SupplyAction:
    questions = {
        "payment": (
            "Уточните, к какой партии относится аванс и когда оплачивается остаток.",
            "Which delivery lot does the advance cover, and when is its balance payable?",
        ),
        "delivery": (
            "Уточните количество и даты для каждой партии. Остальные условия пока не меняю.",
            "Please specify the quantity and delivery dates for each lot. I have not changed the other terms.",
        ),
        "diagnosis": (
            "Уточним критерий: подтвержденная аппаратная неисправность или наш ремонт означают бесплатную замену, а подтвержденная причина на стороне покупателя — оплату резерва. Подходит ли такая логика?",
            "Let us clarify the criterion: a confirmed hardware defect or our repair means a free replacement; a confirmed buyer-side cause means the reserve is payable. Does that rule work for you?",
        ),
        "reserve": (
            "Уточните количество резерва, его поставку и правило оплаты неиспользованных устройств. Новое условие пока не зафиксировано.",
            "Please specify the reserve quantity, delivery lot, and payment rule for unused devices. The new condition has not been recorded.",
        ),
        "price": (
            "Уточните одну общую цену за основную партию в евро.",
            "Please specify one total price in euros for the main order.",
        ),
        "general": (
            "Не могу однозначно связать все части условия. Уточните их одним предложением; пакет пока не изменен.",
            "I cannot link every part of that condition unambiguously. Please clarify it; the package has not changed.",
        ),
    }
    return SupplyAction(
        "inform",
        source_revision=revision,
        clarification=_say(language, *questions.get(topic, questions["general"])),
        topic=topic,
        clarification_code=code,
    )


def _is_question(text: str) -> bool:
    if re.search(r"^(?:что если|а если|what if|suppose|допустим|предположим)\b", text):
        return True
    if re.search(r"(?:вы готовы|готовы ли вы|are you ready|would you|could you)", text):
        return True
    proposal = re.search(
        r"(?:предлага(?:ю|ем)|готов(?:ы|а)?|давайте|согласны|we (?:offer|propose|can pay|are ready)|i (?:offer|propose)|let['’]?s|we will pay)",
        text,
    )
    return bool(
        (
            "?" in text
            or re.search(
                r"^(?:како[ейв]|почему|насколько|сколько|можете|возможно ли|is it|can you|could you|how|which|what|would you)\b",
                text,
            )
        )
        and not proposal
    )


def _dates(text: str) -> list[tuple[int, int, str, str]]:
    found: list[tuple[int, int, str, str]] = []
    for match in re.finditer(r"2026-(?:11|12)-\d{2}", text):
        found.append((match.start(), match.end(), match[0], match[0]))
    patterns = [
        (r"(?:в\s+)?начал[оеа]\s+ноября|early\s+november", "2026-11-05", "2026-11-07"),
    ]
    for expression, start, end in patterns:
        for match in re.finditer(expression, text):
            found.append((match.start(), match.end(), start, end))
    for expression, month in (
        (r"(\d{1,2})(?:\s*[-–—]\s*(\d{1,2}))?\s*(?:ноябр[ья]|november)\b", 11),
        (r"(?:november)\s+(\d{1,2})(?:\s*[-–—]\s*(\d{1,2}))?\b", 11),
        (r"(\d{1,2})\s*(?:декабр[ья]|december)\b", 12),
        (r"december\s+(\d{1,2})\b", 12),
    ):
        for match in re.finditer(expression, text):
            if any(match.start() < right and match.end() > left for left, right, *_ in found):
                continue
            first = int(match[1])
            last = int(match[2]) if match.lastindex and match.lastindex > 1 and match[2] else first
            found.append(
                (
                    match.start(),
                    match.end(),
                    f"2026-{month:02}-{first:02}",
                    f"2026-{month:02}-{last:02}",
                )
            )
    return sorted(found)


def _price(text: str) -> list[int]:
    values = []
    pattern = (
        r"(?:(?:€|eur\b)\s*(\d[\d\s,.]*(?:\d)?)|(\d[\d\s,.]*(?:\d)?)\s*(?:eur\b|евро\b|euros?\b))"
    )
    for match in re.finditer(pattern, text):
        raw = (match[1] or match[2]).replace(" ", "")
        if re.fullmatch(r"\d{1,3}(?:[,.]\d{3})+", raw):
            raw = raw.replace(",", "").replace(".", "")
        elif "," in raw and "." not in raw:
            raw = raw.replace(",", ".")
        elif "," in raw and "." in raw:
            raw = raw.replace(",", "")
        try:
            number = Decimal(raw) * 100
            if number != number.to_integral_value():
                return [-1]
            values.append(int(number))
        except InvalidOperation:
            return [-1]
    return values


def _numbers_are_materialized(text: str, terms: dict[str, Any]) -> bool:
    """Reject source quantities that the typed amendment did not represent."""
    delivery_dates = {
        value
        for lot in terms.get("delivery_lots", [])
        for key, value in lot.items()
        if key in {"window_start", "window_end"}
    }
    reserve = terms.get("reserve_policy", {})
    delivery_dates.update(
        value for key, value in reserve.items() if key in {"use_cutoff", "unused_payable_on"}
    )
    spans: list[tuple[int, int]] = []
    for left, right, first, last in _dates(text):
        if first not in delivery_dates or last not in delivery_dates:
            return False
        spans.append((left, right))
    advance_values = {item.get("advance_bps") for item in terms.get("payment_schedule", [])}
    for left, right, value in _percentages(text):
        if value not in advance_values:
            return False
        spans.append((left, right))
    money_pattern = (
        r"(?:(?:€|eur\b)\s*(\d[\d\s,.]*(?:\d)?)|(\d[\d\s,.]*(?:\d)?)\s*(?:eur\b|евро\b|euros?\b))"
    )
    spans.extend((match.start(), match.end()) for match in re.finditer(money_pattern, text))
    quantities = {lot["quantity"] for lot in terms.get("delivery_lots", [])}
    quantities.add(sum(lot["quantity"] for lot in terms.get("delivery_lots", [])))
    if "quantity" in reserve:
        quantities.add(reserve["quantity"])
    quantity_pattern = r"(\d+)\s*(?:резервн\w*\s+)?(?:устройств\w*|единиц\w*|reserve\s+units?|devices?|units?)|(?:перв\w*|first|резерв|reserve)\s+(\d+)"
    for match in re.finditer(quantity_pattern, text):
        if int(match[1] or match[2]) not in quantities:
            return False
        spans.append((match.start(), match.end()))
    balance_days = {item.get("balance_days") for item in terms.get("payment_schedule", [])}
    for match in re.finditer(r"(\d+)\s*(?:дней|дня|день|days?)", text):
        if int(match[1]) not in balance_days:
            return False
        spans.append((match.start(), match.end()))
    covered = set()
    for left, right in spans:
        covered.update(range(left, right))
    return all(index in covered for index, character in enumerate(text) if character.isdigit())


def _percentages(text: str) -> list[tuple[int, int, int]]:
    return [
        (m.start(), m.end(), int(Decimal(m[1].replace(",", ".")) * 100))
        for m in re.finditer(r"(\d+(?:[.,]\d{1,2})?)\s*%", text)
    ]


def _entry(entries: list[dict[str, Any]], lot_id: str) -> dict[str, Any]:
    return next((entry for entry in entries if entry.get("lot_id") == lot_id), {"lot_id": lot_id})


def _supported_condition_clause(clause: str) -> bool:
    """Accept whole bounded clauses, not a recognized number inside unknown text."""
    normalized = clause.strip(" ,.;:!")
    for left, right, *_ in reversed(_dates(normalized)):
        normalized = normalized[:left] + " DATE " + normalized[right:]
    normalized = re.sub(r"\d+(?:[.,]\d{1,2})?\s*%", " PERCENT ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"\s+([,;.!])", r"\1", normalized)
    patterns = (
        # Delivery conditions retain the complete dependent promise.
        r"(?:что )?(?:мы )?(?:получим|(?:сможем|можем) получить|получить) (?:(?:их|устройства|единицы|партию|заказ) )?(?:ddp )?(?:(?:к|до|в|на) )?DATE(?:,? (?:тогда )?остальные (?:для нас )?приемлемо DATE)?",
        r"(?:что )?(?:поставка|доставка) (?:будет )?(?:ddp )?(?:(?:к|до|в|на) )?DATE",
        r"(?:that )?(?:we )?(?:can )?(?:receive|get) (?:(?:them|the devices|the units|the lot|the order) )?(?:ddp )?(?:(?:by|on|in) )?DATE",
        r"(?:that )?(?:delivery|shipment) (?:is |will be )?(?:ddp )?(?:(?:by|on|in) )?DATE",
        # Payment conditions cannot include a third party's approval or an option.
        r"(?:что )?(?:(?:мы|вы) )?(?:(?:внесем|внесете|вносим|вносите|предложим|предложите) )?PERCENT (?:аванс(?:а|ом)?|предоплат(?:а|ы|ой|у))(?: (?:за|по|для) (?:всю партию|весь заказ|всем партиям|первую партию|остальные партии))?",
        r"(?:that )?(?:(?:we|you) )?(?:(?:pay|offer|provide) )?PERCENT (?:advance|prepayment)(?: for (?:all lots|the first lot|the remaining lot|the whole order))?",
        # A reserve-use condition has one authored interpretation.
        r"(?:они )?(?:окажутся |останутся )?(?:невостребованными|неиспользованными)",
        r"(?:(?:they|the reserve units|the devices) )?(?:are |remain )?unused",
    )
    if any(re.fullmatch(pattern, normalized) for pattern in patterns):
        return True
    # Every member of a conjunction must be independently supported.
    clauses = re.split(r"\s+(?:and|и)\s+", normalized)
    return len(clauses) > 1 and all(_supported_condition_clause(item) for item in clauses)


def parse_supply_message(
    message: str,
    language: str,
    current_terms: dict[str, Any],
    source_revision: int,
    pending_kind: str | None = None,
) -> SupplyAction:
    """Extract the bounded reference grammar without committing a supported subset.

    The caller must provide the current public proposal or offer revision and must
    validate the returned complete materialization against its pinned scenario.
    """
    text = _normal(message)
    topic = _topic(text)
    base = {"source_revision": source_revision, "topic": topic}
    if re.fullmatch(
        r"(?:прекращаю переговоры|ухожу из переговоров|выхожу из переговоров|отказываюсь от сделки|"
        r"(?:i )?walk away|(?:i )?end negotiations|no deal)[.!]?", text
    ):
        return SupplyAction("withdraw", **base)
    if re.fullmatch(
        r"(?:отменяю подтверждение|i cancel confirmation|не подтверждаю(?: принятие предложения)?|i do not confirm(?: acceptance of the offer)?|отменяю принятие|cancel acceptance)[.!]?",
        text,
    ):
        return SupplyAction("cancel", **base)
    if re.fullmatch(
        r"(?:подтверждаю окончательное предложение|i confirm the final offer)[.!]?", text
    ):
        return SupplyAction(
            "confirm_publication" if pending_kind == "publish_offer" else "inform", **base
        )
    acceptance_confirmations = {
        "подтверждаю принятие полного предложения без дополнительных условий",
        "подтверждаю принятие полного предложения",
        "подтверждаю полное принятие предложения без дополнительных условий",
        "i confirm acceptance of the complete offer without additional conditions",
        "i fully confirm acceptance of the complete offer without additional conditions",
        "i confirm acceptance of the complete offer",
        "да, подтверждаю",
    }
    if text.rstrip(".!") in acceptance_confirmations or re.fullmatch(
        r"(?:подтверждаю(?: соглашение| сделку| принятие)?|i confirm(?: the agreement| acceptance)?|confirm)[.!]?",
        text,
    ):
        return SupplyAction(
            "confirm_acceptance" if pending_kind == "accept_offer" else "inform", **base
        )
    if re.search(r"^(?:отзываю (?:предложение|оферту)|i withdraw (?:my |the )?offer)\b", text):
        return SupplyAction("withdraw", **base)
    if re.fullmatch(
        r"(?:принима(?:ю|ем) (?:это |ваше )?(?:окончательное |финальное |полное )?предложение(?: без дополнительных условий)?|(?:i|we) accept (?:the |your )?(?:final |complete )?offer(?: without additional conditions)?)[.!]?",
        text,
    ):
        return SupplyAction("accept", **base)
    final_words = re.search(
        r"(?:окончательн(?:ое|ый) (?:предложение|пакет)|финальн(?:ое|ый) (?:предложение|пакет)|final (?:offer|package)|оформ(?:им|ите) (?:предложение|сделку)|публику(?:ю|ем|йте) (?:предложение|оферту))",
        text,
    )
    final_request = re.search(
        r"представ|покаж|подготов|запраш|публику|оформ|давайте|перейдем|готов|(?:present|show|prepare|request|publish|make|ready|let.s)\b",
        text,
    )
    if (
        final_words
        and (final_request or final_words[0] == text.rstrip(".!"))
        and not re.search(r"(?:не|not)\s+(?:готов|ready|публику)", text)
        and not re.search(r"\d|%|€", text)
    ):
        return SupplyAction("publish", **base)
    if _is_question(text):
        return SupplyAction("question", **base)
    if (
        topic == "reserve"
        and not re.search(r"\d", text)
        and re.search(r"обсуд|discuss|talk about", text)
    ):
        return SupplyAction("question", **base)
    if re.fullmatch(
        r"(?:да|yes|согласен|согласна|согласны|принимаю|принимаем|согласен с (?:этим|предложением)|i accept(?: the offer)?|we accept(?: the offer)?|agreed)[.!]?",
        text,
    ):
        return SupplyAction("accept", **base)
    if re.search(
        r"(?:не предлага|не готов|не соглас|not offering|not ready|do not offer|вы (?:предлагали|сказали)|you (?:offered|said)|раньше|previously)",
        text,
    ):
        return SupplyAction("inform", **base)
    if re.search(r"[«»\"]|(?:you said|вы сказали)", text):
        return SupplyAction("inform", **base)

    candidate = deepcopy(current_terms)
    changed = False
    dates = _dates(text)
    november = [item for item in dates if item[2].startswith("2026-11")]
    percentages = _percentages(text)
    amounts = _price(text)
    has_condition = bool(
        re.search(r"\b(?:если|при условии|только при|if|provided|conditional|unless)\b", text)
    )
    unsupported = bool(
        re.search(
            r"штраф|неустойк|penalt|arbitrat|арбитраж|валютн|exchange rate|вернет.*(?:аванс|предоплат)|refund|бессроч|unlimited|guaranteed uptime|монтаж|installation|реклам|advertis|обучени|training|эксклюзив|exclusiv",
            text,
        )
    )
    if unsupported or (
        has_condition
        and re.search(r"конкурент|competitor|market|рын(?:ок|ке)|продаж|resale|перепродаж", text)
    ):
        return _clarify(language, source_revision, topic, "unsupported_composite_semantics")
    if re.search(r"\busd\b|\bcny\b|\brub\b|рубл|доллар|юан|\$|₽|\b20(?:2[0-5789]|[3-9]\d)\b", text):
        return _clarify(language, source_revision, topic, "unsupported_composite_semantics")
    if amounts and re.search(
        r"(?:за|per)\s+(?:единицу|устройство|unit|device)|unit price\s+(?:is|of)?\s*(?:€|eur|\d)",
        text,
    ):
        return _clarify(language, source_revision, "price", "unsupported_composite_semantics")
    if percentages and topic == "price" and not re.search(r"аванс|предоплат|advance|prepay", text):
        return _clarify(language, source_revision, "price", "unsupported_composite_semantics")
    if re.search(r"\bunless\b", text):
        return _clarify(language, source_revision, topic, "unsupported_composite_semantics")
    if has_condition:
        conditions = re.split(
            r"\b(?:если|при условии|только при|if|provided|conditional|unless)\b", text
        )[1:]
        if not all(_supported_condition_clause(condition) for condition in conditions):
            return _clarify(language, source_revision, topic, "unsupported_composite_semantics")
    if len(amounts) > 1 or any(value < 0 for value in amounts):
        return _clarify(language, source_revision, "price")
    if amounts:
        candidate["base_price"] = {"currency": "EUR", "minor_units": amounts[0]}
        changed = True

    reserve_mentioned = bool(re.search(r"резерв|\bfoc\b|free of charge|reserve|запасн", text))
    reserve_request = reserve_mentioned or bool(
        re.search(r"лишни[ех].*устройств|unused.*(?:unit|device)|устройств.*невостребован", text)
    )
    reserve_none = bool(re.search(r"без резерва|резерв не нужен|no reserve|without reserve", text))
    reserve_only = reserve_request and not reserve_none
    diagnosis = topic == "diagnosis"
    if diagnosis:
        # A device replacement resolving an integration symptom is not a diagnosis.
        hardware = bool(
            re.search(
                r"(?:аппаратн|hardware|наш.*ремонт|our repair)[^;.]{0,100}(?:бесплат|free|foc)",
                text,
            )
        )
        buyer = bool(
            re.search(
                r"(?:\bпо\b|программ|конфигурац|инфраструктур|software|configuration|infrastructure|buyer.side|стороне покупателя)[^;.]{0,100}(?:оплат|pay|purchas)",
                text,
            )
        )
        paid = bool(re.search(r"оплат|pay|paid|purchas", text))
        free = bool(re.search(r"бесплат|\bfoc\b|free", text))
        inverted = bool(
            re.search(
                r"(?:сбой|проблема).{0,25}(?:остается|сохраняется).{0,20}(?:foc|бесплат)|(?:fault|problem).{0,20}(?:remains|persists).{0,20}free",
                text,
            )
        )
        if not (hardware and buyer and paid and free) or inverted:
            return _clarify(
                language, source_revision, "diagnosis", "unsupported_composite_semantics"
            )
        reserve = deepcopy(candidate.get("reserve_policy", {}))
        if reserve.get("mode") != "contingent":
            return _clarify(language, source_revision, "reserve")
        reserve["diagnosis_policy_id"] = "hardware-replacement-v1"
        candidate["reserve_policy"] = reserve
        changed = True

    if reserve_request and not diagnosis:
        if reserve_none:
            candidate["reserve_policy"] = {"mode": "none"}
            changed = True
        else:
            quantity = re.search(
                r"(?:резерв(?:а|ных)?|reserve|foc)\s*(?:из|of|:)?\s*(\d+)|(?<!\d)(\d+)\s*(?:резервн\w*|reserve|запасн\w*|устройств\w*|единиц\w*|devices?|units?)",
                text,
            )
            if quantity:
                reserve = deepcopy(candidate.get("reserve_policy", {}))
                reserve.update({"mode": "contingent", "quantity": int(quantity[1] or quantity[2])})
                if re.search(
                    r"с основной|вместе с|with (?:the )?(?:main|remaining|first|early)|alongside",
                    text,
                ):
                    lots = candidate.get("delivery_lots", [])
                    if lots:
                        first = bool(re.search(r"перв|first|early", text))
                        last = bool(re.search(r"основн|остальн|main|remaining", text))
                        if first and last:
                            return _clarify(language, source_revision, "reserve")
                        reserve["delivery_lot_id"] = lots[0 if first else -1]["lot_id"]
                if (
                    re.search(
                        r"(?:после|к|до|after|by|on)\s*(?:1\s*(?:декабр[ья]|december)|december\s+1)",
                        text,
                    )
                    and re.search(r"оплат|выкуп|pay|purchas|buy", text)
                    and re.search(r"невостребован|неиспользован|лишни|unused", text)
                ):
                    reserve["use_cutoff"] = "2026-12-01"
                    reserve["unused_payable_on"] = "2026-12-02"
                    if re.search(
                        r"той же.*цен|удельн.*цен|same.*unit price|contract.*unit price", text
                    ):
                        reserve["unit_price_rule"] = "base_unit_ceil"
                candidate["reserve_policy"] = reserve
                changed = True
            elif not changed:
                return SupplyAction("inform", **base)

    lots = deepcopy(candidate.get("delivery_lots", []))
    split = (
        not reserve_only
        and bool(re.search(r"остальн|remaining|the rest|split|раздел|разбить", text))
        and bool(
            re.search(r"10\s*(?:единиц|устройств|units?|devices?)|первых?\s+10|first\s+10", text)
        )
    )
    if split:
        quantities = [
            int(m[1])
            for m in re.finditer(r"(\d+)\s*(?:единиц\w*|устройств\w*|devices?|units?)", text)
        ]
        if any(quantity not in (10, 90, 100) for quantity in quantities) or len(november) != 2:
            return _clarify(language, source_revision, "delivery")
        old_payments = deepcopy(candidate.get("payment_schedule", []))
        main = _entry(old_payments, "main")
        early = _entry(old_payments, "early")
        remaining = _entry(old_payments, "remaining")
        for key, value in main.items():
            if key != "lot_id":
                early.setdefault(key, value)
                remaining.setdefault(key, value)
        lots = [
            {
                "lot_id": "early",
                "quantity": 10,
                "window_start": november[0][2],
                "window_end": november[0][3],
            },
            {
                "lot_id": "remaining",
                "quantity": 90,
                "window_start": november[1][2],
                "window_end": november[1][3],
            },
        ]
        if percentages:
            if len(percentages) > 2:
                return _clarify(language, source_revision, "payment")
            anchors = [
                (m.start(), "early")
                for m in re.finditer(
                    r"\b10\s*(?:единиц|устройств|units?|devices?)|перв\w*|\bfirst\b|\bearly\b", text
                )
            ]
            anchors += [
                (m.start(), "remaining")
                for m in re.finditer(r"остальн\w*|\bremaining\b|the rest", text)
            ]
            anchors.sort()
            assignments: dict[str, int] = {}
            for start, end, value in percentages:
                following = text[end : end + 40]
                if re.search(
                    r"^(?:\s|предоплат\w*|аванс\w*|advance|prepayment|for|за|the|first|перв\w*)*\s*10\s*(?:единиц|устройств|units?|devices?)",
                    following,
                ):
                    lot_id = "early"
                else:
                    previous = [anchor for anchor in anchors if anchor[0] < start]
                    lot_id = previous[-1][1] if previous else "early"
                if lot_id in assignments and assignments[lot_id] != value:
                    return _clarify(language, source_revision, "payment")
                assignments[lot_id] = value
            for lot_id, value in assignments.items():
                (early if lot_id == "early" else remaining)["advance_bps"] = value
        candidate["delivery_lots"] = lots
        candidate["payment_schedule"] = [early, remaining]
        reserve = candidate.get("reserve_policy", {})
        if reserve.get("delivery_lot_id") == "main":
            reserve["delivery_lot_id"] = "remaining"
        changed = True
    elif november and not reserve_only and not diagnosis:
        if len(november) != 1:
            return _clarify(language, source_revision, "delivery")
        selected = lots
        if len(lots) > 1:
            if re.search(r"остальн|remaining|the rest", text):
                selected = [lot for lot in lots if lot["lot_id"] == "remaining"]
            elif re.search(r"перв|early|first", text):
                selected = [lot for lot in lots if lot["lot_id"] == "early"]
            else:
                return _clarify(language, source_revision, "delivery")
        for lot in selected:
            lot["window_start"], lot["window_end"] = november[0][2:]
        candidate["delivery_lots"] = lots
        changed = True
    if "ddp" in text and not diagnosis:
        candidate["delivery_basis"] = {"basis": "DDP", "destination_id": "vector_site"}
        changed = True

    if percentages and not split and not reserve_only and not diagnosis:
        if len(percentages) != 1:
            return _clarify(language, source_revision, "payment")
        entries = deepcopy(candidate.get("payment_schedule", []))
        selected_ids = [lot["lot_id"] for lot in lots]
        if len(selected_ids) > 1:
            if re.search(r"остальн|remaining|the rest", text):
                selected_ids = ["remaining"]
            elif re.search(r"перв|first|early", text):
                selected_ids = ["early"]
            elif re.search(r"\b(?:всю|всей|все|всем|всех|общий|whole|all|every)\b", text):
                pass
            elif re.search(r"сохран|keep|maintain", text):
                selected_ids = [
                    entry["lot_id"]
                    for entry in entries
                    if entry.get("advance_bps") == percentages[0][2]
                ]
            else:
                return _clarify(language, source_revision, "payment")
        if not selected_ids:
            return _clarify(language, source_revision, "payment")
        for lot_id in selected_ids:
            entry = _entry(entries, lot_id)
            entry["advance_bps"] = percentages[0][2]
            if not any(existing.get("lot_id") == lot_id for existing in entries):
                entries.append(entry)
        candidate["payment_schedule"] = entries
        changed = True
    if re.search(r"остат(?:ок|ка)|balance|оставш.*оплат", text) and re.search(
        r"при получении|по поставке|после поставки|при поставке|on delivery|upon delivery|30\s*(?:дн|days)",
        text,
    ):
        days = 30 if re.search(r"30\s*(?:дн|days)", text) else 0
        entries = deepcopy(candidate.get("payment_schedule", []))
        balance_clauses = [
            part
            for part in re.split(r"[;,.]", text)
            if re.search(r"остат(?:ок|ка)|balance|оставш.*оплат", part)
        ]
        if len(balance_clauses) != 1:
            return _clarify(language, source_revision, "payment")
        balance_scope = balance_clauses[0]
        selected_lots = lots
        if len(lots) > 1:
            if re.search(r"перв|first|early", balance_scope) and re.search(
                r"остальн|remaining|the rest", balance_scope
            ):
                return _clarify(language, source_revision, "payment")
            elif re.search(r"перв|first|early", balance_scope):
                selected_lots = [lot for lot in lots if lot["lot_id"] == "early"]
            elif re.search(r"остальн|remaining|the rest", balance_scope):
                selected_lots = [lot for lot in lots if lot["lot_id"] == "remaining"]
        for lot in selected_lots:
            entry = _entry(entries, lot["lot_id"])
            entry["balance_days"] = days
            if not any(existing.get("lot_id") == lot["lot_id"] for existing in entries):
                entries.append(entry)
        candidate["payment_schedule"] = entries
        changed = True
    # A recognized amount must not swallow an unsupported dependent condition.
    if (
        has_condition
        and changed
        and not (november or split or reserve_request or diagnosis or percentages)
    ):
        return _clarify(language, source_revision, topic, "unsupported_composite_semantics")
    if changed:
        if not _numbers_are_materialized(text, candidate):
            return _clarify(language, source_revision, topic, "unsupported_composite_semantics")
        return SupplyAction("amend", candidate, **base)
    if re.search(r"\d|%|€", text) and topic != "general":
        return _clarify(language, source_revision, topic, "unsupported_composite_semantics")
    return SupplyAction("inform", **base)


def validate_supply_extraction(
    payload: dict[str, Any],
    message: str,
    language: str,
    current_terms: dict[str, Any],
    source_revision: int,
) -> SupplyAction:
    """Validate a candidate against the full source and the bounded grammar.

    This optional adapter does not extend the accepted language grammar. It is a
    fail-closed check for an injected extractor, not an LLM truth authority.
    Pending protocol confirmations always bypass extraction in the service.
    """
    failure = _clarify(
        language, source_revision, _topic(_normal(message)), "extraction_unavailable"
    )
    if not isinstance(payload, dict) or set(payload) != {
        "action",
        "terms",
        "source_revision",
        "source_text",
    }:
        return failure
    if (
        type(payload["source_revision"]) is not int
        or payload["source_revision"] != source_revision
        or payload["source_text"] != message
    ):
        return failure
    if payload["action"] not in {"amend", "inform", "question"}:
        return failure
    expected = parse_supply_message(message, language, current_terms, source_revision)
    if expected.clarification:
        return expected
    try:
        expected_terms = json.dumps(expected.terms, sort_keys=True, allow_nan=False)
        proposed_terms = json.dumps(payload["terms"], sort_keys=True, allow_nan=False)
    except (ValueError, TypeError):
        return failure
    if payload["action"] != expected.action or expected_terms != proposed_terms:
        return failure
    return expected


def _completion(scenario: dict[str, Any], terms: dict[str, Any]) -> dict[str, Any]:
    """Build an internal evaluation witness. Never return it as a public proposal."""
    candidate = deepcopy(terms)
    config = scenario["supply_model"]
    capabilities = config["capabilities"]
    candidate.setdefault(
        "delivery_basis",
        {"basis": capabilities["delivery_basis"], "destination_id": capabilities["destination_id"]},
    )
    candidate.setdefault("reserve_policy", {"mode": "none"})
    candidate.setdefault("payment_schedule", [])
    for lot in candidate.get("delivery_lots", []):
        entry = _entry(candidate["payment_schedule"], lot["lot_id"])
        entry.setdefault("advance_bps", 0)
        entry.setdefault("balance_days", 0)
        if not any(
            existing.get("lot_id") == lot["lot_id"] for existing in candidate["payment_schedule"]
        ):
            candidate["payment_schedule"].append(entry)
    return candidate


def _eligible(scenario: dict[str, Any], role: str, terms: dict[str, Any]) -> bool:
    from .supply import evaluate_supply_utility, supply_constraint_violations, validate_supply_terms

    if validate_supply_terms(scenario, terms, complete=True) or supply_constraint_violations(
        scenario, role, terms
    ):
        return False
    reservation = scenario["utility_model"]["role_models"][role]["reservation_utility"]
    try:
        return evaluate_supply_utility(scenario, role, terms) >= reservation
    except (ValueError, TypeError, KeyError):
        return False


def decide_supply_action(
    scenario: dict[str, Any],
    role: str,
    terms: dict[str, Any],
    last_message: str,
    language: str,
    formal: bool = False,
    proposer_role: str | None = None,
    *,
    cooperative: bool = False,
) -> SupplyDecision:
    """Select a legal action from authored economics and this actor's interests."""
    from .supply import unresolved_supply_terms, validate_supply_terms

    text = _normal(last_message)
    topic = _topic(text)
    parsed = parse_supply_message(last_message, language, terms, 0)
    config = scenario["supply_model"]
    capabilities = config["capabilities"]
    reserve_rules = config["reserve_rules"]
    pending = unresolved_supply_terms(scenario, terms)
    if formal and proposer_role != role and parsed.action != "question":
        if _eligible(scenario, role, terms):
            return SupplyDecision(
                "accept",
                deepcopy(terms),
                _say(
                    language,
                    "Принимаю представленное окончательное предложение.",
                    "I accept the published final offer.",
                ),
                topic,
            )
        return SupplyDecision(
            "reject",
            text=_say(
                language,
                "Этот окончательный пакет мне не подходит. Можем вернуться к обсуждению его условий.",
                "This final package does not work for me. We can return to discussing its terms.",
            ),
            topic=topic,
        )
    if parsed.action == "publish":
        if pending:
            return SupplyDecision(
                "inform",
                text=_say(
                    language,
                    "Перед окончательным предложением нужно уточнить незаполненные условия. Сейчас это предварительный пакет.",
                    "We need to resolve the missing terms before a final offer. This remains a preliminary package.",
                ),
                topic="finalization",
            )
        if _eligible(scenario, role, terms):
            return SupplyDecision(
                "publish",
                deepcopy(terms),
                _say(
                    language,
                    "Представляю окончательное предложение. Его принятие и подтверждение будут отдельными действиями.",
                    "Here is my final offer. Acceptance and confirmation remain separate actions.",
                ),
                "finalization",
            )
        return SupplyDecision(
            "inform",
            text=_say(
                language,
                "Пока не могу представить этот пакет как окончательное предложение. Нужно пересмотреть его условия.",
                "I cannot present this package as my final offer yet. We need to revisit its terms.",
            ),
            topic="finalization",
        )
    price_pressure = bool(
        re.search(
            r"бюджет|оптимиз|сниз|скидк|дешев|хорошей цене|budget|discount|reduc|lower|better price",
            text,
        )
    )
    if parsed.action == "question" and not (topic == "price" and price_pressure):
        answers = {
            "price": (
                "Готов обсудить стоимость в обмен на конкретные условия оплаты или график поставки. Какое изменение вам доступно?",
                "I can discuss the price in exchange for concrete payment or delivery terms. Which change can you offer?",
            ),
            "payment": (
                "Аванс уменьшает потребность в финансировании заказа. Важно уточнить, к какой партии он относится и когда оплачивается остаток.",
                "An advance reduces the financing needed for the order. We need to specify the covered lot and when the balance is payable.",
            ),
            "delivery": (
                "Можно обсудить отдельную раннюю партию для интеграции и более позднюю основную поставку. Какие устройства нужны вам раньше?",
                "We can discuss a separate early lot for integration and a later main delivery. Which devices do you need first?",
            ),
            "reserve": (
                "Резерв может защитить запуск без ожидания отдельной замены. Важно договориться об оплате неиспользованных устройств и критерии бесплатной замены.",
                "A reserve can protect the launch without waiting for another shipment. We should agree on unused-device payment and the criterion for a free replacement.",
            ),
            "diagnosis": (
                "Нестабильная работа системы сама по себе не доказывает аппаратный дефект. Нужна диагностика, которая отделяет неисправность оборудования от причины на стороне покупателя.",
                "System instability alone does not establish a hardware defect. Diagnosis must distinguish a hardware fault from a buyer-side cause.",
            ),
            "general": (
                "Для меня важна связь цены, оплаты и исполнимого графика. Давайте начнем с того, что для вас сейчас важнее всего.",
                "The connection between price, payment, and a feasible schedule matters to me. What is most important to you right now?",
            ),
        }
        return SupplyDecision("inform", text=_say(language, *answers[topic]), topic=topic)
    if (
        topic == "diagnosis"
        or parsed.clarification_code == "unsupported_composite_semantics"
        and topic == "diagnosis"
    ):
        proposal = deepcopy(terms)
        reserve = proposal.get("reserve_policy", {})
        if reserve.get("mode") == "contingent":
            reserve["diagnosis_policy_id"] = reserve_rules["diagnosis_policy_id"]
            return SupplyDecision(
                "propose",
                proposal,
                _say(
                    language,
                    "Сам механизм оперативной замены подходит. Уточню критерий: подтвержденный аппаратный дефект или наш ремонт означают бесплатную замену; подтвержденная причина на стороне покупателя означает оплату. Неокончательный диагноз сам по себе не создает платеж.",
                    "The immediate-replacement mechanism works. I would clarify the criterion: a confirmed hardware defect or our repair means a free replacement; a confirmed buyer-side cause means payment. An inconclusive diagnosis alone does not create a payment obligation.",
                ),
                topic,
            )
    if topic == "reserve":
        proposal = deepcopy(terms)
        reserve = proposal.get("reserve_policy", {})
        if reserve.get("mode") == "none":
            return SupplyDecision(
                "inform",
                text=_say(
                    language,
                    "Понял: резерв в этот предварительный пакет не включаем. Остальные условия сохраняются для дальнейшего обсуждения.",
                    "Understood: this preliminary package does not include a reserve. The other terms remain available for further discussion.",
                ),
                topic=topic,
            )
        if reserve.get("mode") == "contingent" and reserve.get("quantity"):
            reserve.setdefault("delivery_lot_id", proposal["delivery_lots"][-1]["lot_id"])
            for key in (
                "use_cutoff",
                "unused_payable_on",
                "unit_price_rule",
                "diagnosis_policy_id",
            ):
                reserve.setdefault(key, reserve_rules[key])
            if not validate_supply_terms(scenario, proposal, complete=False):
                return SupplyDecision(
                    "propose",
                    proposal,
                    _say(
                        language,
                        "Предлагаю такой механизм резерва: он поступает вместе с указанной партией; неиспользованные устройства выкупаются по цене единицы основного заказа. Бесплатная замена применяется к подтвержденной аппаратной неисправности или нашему ремонту. Это предварительное условие, его еще можно обсудить.",
                        "I suggest this reserve mechanism: it arrives with the specified lot; unused devices are purchased at the main-order unit price. Free replacement applies to a confirmed hardware fault or our repair. This is a preliminary term that we can still discuss.",
                    ),
                    topic,
                )
        return SupplyDecision(
            "inform",
            text=_say(
                language,
                "Резерв стоит рассмотреть отдельно от основной партии. Какое количество позволит вам быстро заменить неисправное устройство?",
                "We should consider the reserve separately from the main order. How many devices would let you replace a faulty one promptly?",
            ),
            topic=topic,
        )

    payments = terms.get("payment_schedule", [])
    lots = terms.get("delivery_lots", [])
    weighted_bps = (
        sum(lot["quantity"] * _entry(payments, lot["lot_id"]).get("advance_bps", 0) for lot in lots)
        / capabilities["main_quantity"]
    )
    npc_policy = config["npc_policy"]
    concrete_payment = topic in ("payment", "delivery") and any(
        "advance_bps" in entry for entry in payments
    )
    if (price_pressure or concrete_payment) and role == "seller":
        threshold = npc_policy["advance_threshold_bps"]
        tier = npc_policy["standard_price_index"]
        if weighted_bps >= threshold:
            tier = npc_policy["advance_price_index"]
        if (
            len(lots) == 2
            and _entry(payments, "early").get("advance_bps") == 10000
            and _entry(payments, "remaining").get("advance_bps", 0) >= threshold
        ):
            tier = npc_policy["split_price_index"]
        candidates = npc_policy["price_candidates_minor"]
        if cooperative:
            tier = len(candidates) - 1
        old_price = terms.get("base_price", {}).get("minor_units")
        for price in reversed(candidates[: min(tier + 1, len(candidates))]):
            if old_price is not None and price > old_price:
                continue
            proposal = deepcopy(terms)
            proposal["base_price"] = {"currency": "EUR", "minor_units": price}
            if not _eligible(scenario, role, _completion(scenario, proposal)):
                continue
            if proposal == terms:
                break
            if payments:
                for entry in proposal["payment_schedule"]:
                    entry.setdefault("balance_days", 0)
            return SupplyDecision(
                "propose",
                proposal,
                _say(
                    language,
                    "С учетом обсуждаемой структуры могу предложить эту цену. Для указанных партий предлагаю оплачивать остаток при поставке. Остальные незаполненные условия пока остаются открытыми.",
                    "Given the structure we are discussing, I can offer this price. For the specified lots, I propose paying the balance on delivery. Other unspecified terms remain open.",
                )
                if payments
                else _say(
                    language,
                    "Определенный запас для обсуждения стоимости есть. Предлагаю начать с этой цены; условия оплаты обсудим отдельно.",
                    "There is some room to discuss the price. I suggest starting here; we can discuss payment terms separately.",
                ),
                topic,
            )
    if parsed.action == "accept":
        return SupplyDecision(
            "inform",
            text=_say(
                language,
                "Понял. Предварительный пакет сохранен, но это еще не заключение сделки. Можно обсудить оставшиеся условия или запросить окончательное предложение.",
                "Understood. The preliminary package is retained, but this is not a concluded agreement. We can discuss remaining terms or request a final offer.",
            ),
            topic=topic,
        )
    if re.search(r"привет|добрый день|здравств|hello|good (?:morning|afternoon)|\bhi\b", text):
        return SupplyDecision(
            "inform",
            text=_say(
                language,
                "Добрый день. Рад обсудить поставку. Насколько предложенная конфигурация подходит для вашего проекта?",
                "Good day. I am glad to discuss the order. How well does the proposed configuration fit your project?",
            ),
            topic=topic,
        )
    if re.search(r"дурак|идиот|stupid|idiot", text):
        return SupplyDecision(
            "inform",
            text=_say(
                language,
                "Давайте вернемся к условиям поставки. Что именно в моем предложении вас не устраивает?",
                "Let us return to the delivery terms. What specifically does not work for you in my proposal?",
            ),
            topic=topic,
        )
    if not pending:
        return SupplyDecision(
            "inform",
            text=_say(
                language,
                "Пакет теперь содержит все обязательные условия. Он остается предварительным: можем еще обсудить детали или перейти к окончательному предложению.",
                "The package now contains all required terms. It remains preliminary: we can discuss details or move to a final offer.",
            ),
            topic=topic,
        )
    return SupplyDecision(
        "inform",
        text=_say(
            language,
            "Понял вашу позицию. Давайте уточним следующий открытый вопрос, не меняя уже обсужденные условия.",
            "I understand your position. Let us clarify the next open point while preserving the terms already discussed.",
        ),
        topic=topic,
    )
