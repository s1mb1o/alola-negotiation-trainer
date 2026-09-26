"""Windowed terminal interface for a human Player API session."""

from __future__ import annotations

import curses
import json
import textwrap
from typing import Any, Mapping
import unicodedata

from .api import (
    ApiError,
    NegotiationApiClient,
    new_idempotency_key,
    response_revision,
    response_status,
)
from .orchestrator import TERMINAL_STATUSES


TABS = ("offer", "brief", "coach")

COLOR_BASE = 1
COLOR_BORDER = 2
COLOR_USER = 3
COLOR_COUNTERPART = 4
COLOR_HEADING = 5
COLOR_ERROR = 6
COLOR_BAND = 7

LABELS = {
    "en": {
        "app": "NEGOTIATION TRAINER",
        "conversation": "Conversation",
        "offer": "Offer",
        "brief": "Brief",
        "coach": "Coach",
        "debug": "Debug API",
        "review": "Review",
        "message": "Message",
        "case": "CASE",
        "you": "You",
        "buyer": "Buyer",
        "seller": "Seller",
        "counterpart": "Counterpart",
        "no_messages": "No messages yet.",
        "by": "By",
        "incomplete": "Incomplete",
        "preliminary": "Preliminary",
        "not_final": "Not a final offer",
        "public_terms": "Public terms",
        "no_offer": "No current offer.",
        "no_brief": "No role brief.",
        "objectives": "Objectives",
        "context": "Context",
        "constraints": "Constraints",
        "priorities": "Priorities",
        "coaching": "Coaching",
        "signals": "Public signals",
        "hints": "Requested hints",
        "hints_left": "Hints left",
        "hint_command": "Type /hint to request one.",
        "no_coaching": "No coaching in this mode.",
        "agreement": "Agreement",
        "yes": "yes",
        "no": "no",
        "reason": "Reason",
        "reservation": "Reservation",
        "review_unavailable": "Review unavailable.",
        "footer": "Enter send | Tab panel | PgUp/Dn chat | F2 offer | F3 debug | /quit",
    },
    "ru": {
        "app": "ТРЕНАЖЕР ПЕРЕГОВОРОВ",
        "conversation": "Диалог",
        "offer": "Предложение",
        "brief": "Ваша роль",
        "coach": "Подсказки",
        "debug": "Отладка API",
        "review": "Разбор",
        "message": "Сообщение",
        "case": "СИТУАЦИЯ",
        "you": "Вы",
        "buyer": "Покупатель",
        "seller": "Продавец",
        "counterpart": "Собеседник",
        "no_messages": "Сообщений пока нет.",
        "by": "Автор",
        "incomplete": "Не заполнено",
        "preliminary": "Предварительное предложение",
        "not_final": "Не является окончательным предложением",
        "public_terms": "Открытые условия",
        "no_offer": "Активного предложения нет.",
        "no_brief": "Описание роли отсутствует.",
        "objectives": "Цели",
        "context": "Контекст",
        "constraints": "Ограничения",
        "priorities": "Приоритеты",
        "coaching": "Совет",
        "signals": "Открытые сигналы",
        "hints": "Полученные подсказки",
        "hints_left": "Осталось подсказок",
        "hint_command": "Введите /hint для подсказки.",
        "no_coaching": "В этом режиме нет советов.",
        "agreement": "Соглашение",
        "yes": "да",
        "no": "нет",
        "reason": "Причина",
        "reservation": "Резерв",
        "review_unavailable": "Разбор недоступен.",
        "footer": "Enter отправить | Tab панели | PgUp/Dn диалог | F2 | F3 отладка | /quit",
    },
}


def _label(current: Mapping[str, Any], key: str) -> str:
    language = current.get("language") or _observation(current).get("language")
    return LABELS["en" if language == "en" else "ru"][key]


def _tr(current: Mapping[str, Any], ru: str, en: str) -> str:
    language = current.get("language") or _observation(current).get("language")
    return en if language == "en" else ru


def _clean(value: Any) -> str:
    return "".join(
        character if character in "\n\t" or unicodedata.category(character) != "Cc" else " "
        for character in str(value)
    ).replace("\t", "    ")


def _width(character: str) -> int:
    if unicodedata.combining(character):
        return 0
    return 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1


def _clip(value: Any, width: int) -> str:
    result = ""
    used = 0
    for character in _clean(value).replace("\n", " "):
        size = _width(character)
        if used + size > width:
            break
        result += character
        used += size
    return result


def _wrap(value: Any, width: int) -> list[str]:
    width = max(1, width)
    lines: list[str] = []
    for paragraph in _clean(value).split("\n"):
        if not paragraph:
            lines.append("")
            continue
        for line in textwrap.wrap(
            paragraph,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
        ):
            remaining = line
            while remaining:
                fragment = _clip(remaining, width)
                if not fragment:
                    fragment = remaining[0]
                lines.append(fragment)
                remaining = remaining[len(fragment) :]
    return lines or [""]


def _term_lines(terms: Any, prefix: str = "") -> list[str]:
    if not isinstance(terms, Mapping):
        return [f"{prefix}: {_clean(terms)}"] if prefix else []
    result: list[str] = []
    for key, value in terms.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            result.extend(_term_lines(value, name))
        elif isinstance(value, list):
            result.append(f"{name}: {json.dumps(value, ensure_ascii=False)}")
        else:
            result.append(f"{name}: {_clean(value)}")
    return result


def _observation(current: Mapping[str, Any]) -> Mapping[str, Any]:
    value = current.get("observation")
    return value if isinstance(value, Mapping) else {}


def conversation_lines(
    current: Mapping[str, Any], width: int, *, case_title: str | None = None
) -> list[str]:
    observation = _observation(current)
    entries = observation.get("conversation") or []
    lines: list[str] = []
    if case_title:
        lines.append(f"{_label(current, 'case')}: {case_title}")
        brief = observation.get("role_brief")
        if isinstance(brief, Mapping):
            if brief.get("summary"):
                lines.append(str(brief["summary"]))
            for objective in brief.get("objectives") or []:
                lines.append(f"{_label(current, 'objectives')}: {objective}")
            if brief.get("context"):
                lines.append(f"{_label(current, 'context')}: {brief['context']}")
        elif isinstance(brief, str):
            lines.append(brief)
        lines.append("")
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        own = entry.get("participant_id") == observation.get("participant_id")
        role = str(entry.get("role") or "counterpart")
        speaker = _label(
            current, "you" if own else role if role in {"buyer", "seller"} else "counterpart"
        )
        revision = entry.get("revision")
        lines.append(f"{speaker}  r{revision}" if revision is not None else speaker)
        for line in _wrap(entry.get("message", ""), width):
            lines.append(f"  {line}")
        lines.append("")
    return lines or [_label(current, "no_messages")]


def offer_lines(current: Mapping[str, Any]) -> list[str]:
    observation = _observation(current)
    offers = observation.get("active_offers") or []
    lines: list[str] = []
    for index, offer in enumerate(offers, 1):
        if not isinstance(offer, Mapping):
            continue
        lines.append(f"{_label(current, 'offer')} {index}  rev {offer.get('offer_revision', '?')}")
        proposer = str(offer.get("proposer_role") or "?")
        lines.append(
            f"{_label(current, 'by')}: {_label(current, proposer) if proposer in {'buyer', 'seller'} else proposer}"
        )
        lines.extend(_term_lines(offer.get("terms") or {}))
        unresolved = offer.get("unresolved_required_terms") or []
        if unresolved:
            lines.append(
                _label(current, "incomplete") + ": " + ", ".join(str(item) for item in unresolved)
            )
        lines.append("")
    if not lines:
        proposals = observation.get("preliminary_proposals") or []
        for proposal in proposals:
            if isinstance(proposal, Mapping) and proposal.get("status") == "active":
                lines.append(
                    f"{_label(current, 'preliminary')} rev {proposal.get('proposal_revision', '?')}"
                )
                lines.append(_label(current, "not_final"))
                lines.extend(_term_lines(proposal.get("terms") or {}))
                break
    if not lines:
        public_terms = observation.get("current_public_terms") or {}
        if public_terms:
            lines = [_label(current, "public_terms"), *_term_lines(public_terms)]
    return lines or [_label(current, "no_offer")]


def brief_lines(current: Mapping[str, Any]) -> list[str]:
    brief = _observation(current).get("role_brief") or {}
    if isinstance(brief, str):
        return [brief]
    if not isinstance(brief, Mapping):
        return [_label(current, "no_brief")]
    lines = [str(brief.get("summary") or brief.get("content") or "")]
    for key in ("objectives", "context"):
        value = brief.get(key)
        if value:
            lines.append("")
            lines.append(_label(current, key))
            if isinstance(value, list):
                lines.extend(str(item) for item in value)
            else:
                lines.append(str(value))
    if brief.get("batna"):
        lines.extend(("", "BATNA", str(brief["batna"])))
    for key in ("constraints", "priorities"):
        value = brief.get(key)
        if value:
            lines.extend(("", _label(current, key)))
            if isinstance(value, Mapping):
                lines.extend(_term_lines(value))
            elif isinstance(value, list):
                lines.extend(str(item) for item in value)
            else:
                lines.append(str(value))
    return lines


def coach_lines(current: Mapping[str, Any]) -> list[str]:
    observation = _observation(current)
    assistance = observation.get("assistance") or {}
    lines: list[str] = []
    if isinstance(assistance, Mapping):
        if assistance.get("coaching"):
            lines.extend((_label(current, "coaching"), str(assistance["coaching"]), ""))
        if assistance.get("detected_signals"):
            lines.extend(
                (_label(current, "signals"), ", ".join(assistance["detected_signals"]), "")
            )
    hints = observation.get("hints") or []
    if hints:
        lines.append(_label(current, "hints"))
        lines.extend(str(hint.get("text", "")) for hint in hints if isinstance(hint, Mapping))
    if current.get("hints_enabled"):
        lines.extend(
            (
                "",
                f"{_label(current, 'hints_left')}: {observation.get('remaining_hints', '?')}",
                _label(current, "hint_command"),
            )
        )
    return lines or [_label(current, "no_coaching")]


def debug_lines(current: Mapping[str, Any], history: Any = None) -> list[str]:
    """Show only values already present in the authenticated Player API projection."""

    observation = _observation(current)
    next_actor = current.get("next_actor")
    next_role = (
        _label(current, "you")
        if next_actor and next_actor == observation.get("participant_id")
        else _label(current, "counterpart")
        if next_actor
        else "-"
    )
    events = history.get("events") if isinstance(history, Mapping) else None
    events = events if isinstance(events, list) else []
    intent = next(
        (
            event
            for event in reversed(events)
            if isinstance(event, Mapping) and event.get("type") == "npc.intent.committed"
        ),
        {},
    )
    utterance = next(
        (
            event
            for event in reversed(events)
            if isinstance(event, Mapping)
            and event.get("type") in {"npc.utterance.delivered", "npc.greeting.delivered"}
        ),
        {},
    )
    intent_payload = intent.get("payload") if isinstance(intent, Mapping) else None
    intent_payload = intent_payload if isinstance(intent_payload, Mapping) else {}
    utterance_payload = utterance.get("payload") if isinstance(utterance, Mapping) else None
    utterance_payload = utterance_payload if isinstance(utterance_payload, Mapping) else {}
    renderer = utterance_payload.get("dialogue_renderer")
    renderer = renderer if isinstance(renderer, Mapping) else {}
    pending = (
        "acceptance"
        if current.get("pending_confirmation")
        else "publication"
        if current.get("pending_offer_publication")
        else "clarification"
        if current.get("clarification")
        else "none"
    )
    lines = [
        f"session_revision={response_revision(current)}",
        f"next_actor={next_role}",
        f"npc_action={intent_payload.get('action', '-')}",
        f"round={current.get('round', '-')}",
        f"substantive_turns={current.get('substantive_turn_count', '-')}",
        f"npc_speech_act={intent_payload.get('speech_act') or utterance_payload.get('speech_act') or '-'}",
        f"pending={pending}",
        f"renderer={renderer.get('mode', '-')}",
        f"status={response_status(current)}",
        f"difficulty={current.get('difficulty', '-')}",
        f"player_role={observation.get('role', '-')}",
        f"messages={len(observation.get('conversation') or [])}",
        f"hints_enabled={str(bool(current.get('hints_enabled'))).lower()}",
        f"scenario_id={current.get('scenario_id', '-')}",
        f"scenario_version={current.get('scenario_version', '-')}",
        "scope=player_visible",
    ]
    if intent:
        lines.append(f"npc_action_rev={intent.get('session_revision', '-')}")
    if utterance_payload.get("requested_term_id"):
        lines.append(f"requested_term={utterance_payload['requested_term_id']}")
    if renderer:
        lines.append(f"fallback={str(bool(renderer.get('fallback_used'))).lower()}")
    offers = observation.get("active_offers") or []
    if offers and isinstance(offers[0], Mapping):
        offer = offers[0]
        lines.append(f"active_offer_rev={offer.get('offer_revision', '-')}")
        unresolved = offer.get("unresolved_required_terms") or []
        lines.append("unresolved=" + (", ".join(str(item) for item in unresolved) or "none"))
    proposals = observation.get("preliminary_proposals") or []
    if proposals and isinstance(proposals[0], Mapping):
        lines.append(f"preliminary_rev={proposals[0].get('proposal_revision', '-')}")
    return lines


def review_lines(review: Any, current: Mapping[str, Any]) -> list[str]:
    if not isinstance(review, Mapping):
        return [_label(current, "review_unavailable")]
    outcome = review.get("outcome") or {}
    lines = [_label(current, "review").upper()]
    if isinstance(outcome, Mapping):
        lines.append(
            _label(current, "agreement")
            + ": "
            + _label(current, "yes" if outcome.get("agreement") else "no")
        )
        if outcome.get("termination_reason"):
            lines.append(f"{_label(current, 'reason')}: {outcome['termination_reason']}")
        if outcome.get("reservation_comparison"):
            lines.append(f"{_label(current, 'reservation')}: {outcome['reservation_comparison']}")
    for key in ("outcome_score", "skill_score"):
        if review.get(key) is not None:
            lines.append(f"{key}: {review[key]}")
    for item in review.get("recommendations") or []:
        if isinstance(item, Mapping) and item.get("text"):
            lines.append(str(item["text"]))
    return lines


def _pending(current: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]] | None:
    publication = current.get("pending_offer_publication")
    if isinstance(publication, Mapping):
        return "publication", publication
    confirmation = current.get("pending_confirmation")
    if isinstance(confirmation, Mapping):
        return "acceptance", confirmation
    return None


def _confirmation_text(kind: str, language: str, *, confirm: bool) -> str:
    texts = {
        "publication": {
            "ru": ("Подтверждаю окончательное предложение", "Отменяю подтверждение"),
            "en": ("I confirm the final offer", "I cancel confirmation"),
        },
        "acceptance": {
            "ru": (
                "Подтверждаю принятие полного предложения без дополнительных условий.",
                "Не подтверждаю принятие предложения.",
            ),
            "en": (
                "I confirm acceptance of the complete offer without additional conditions.",
                "I do not confirm acceptance of the offer.",
            ),
        },
    }
    return texts[kind]["en" if language == "en" else "ru"][0 if confirm else 1]


class PlayTui:
    def __init__(
        self,
        api: NegotiationApiClient,
        session_id: str,
        current: Mapping[str, Any],
        *,
        case_title: str | None = None,
        debug: bool = False,
    ) -> None:
        self.api = api
        self.session_id = session_id
        self.current = current
        self.case_title = case_title or str(current.get("scenario_id") or "")
        self.debug = debug
        self.debug_history: Mapping[str, Any] = {}
        self.debug_error = ""
        self.debug_scroll = 0
        self.tab = 0
        self.chat_scroll = 0
        self.side_scroll = 0
        self.modal_scroll = 0
        self.modal: tuple[str, Mapping[str, Any], int] | None = None
        self.draft = ""
        self.notice = ""
        self.review: Any = None
        self._screen: Any = None
        self._colors_enabled = False
        self._message_attempt: tuple[str, int, str] | None = None
        self._hint_attempt: tuple[int, str] | None = None
        self._terminal_review()
        self._open_pending()
        self._load_debug()

    def _load_debug(self) -> None:
        if not self.debug:
            return
        try:
            history = self.api.history(self.session_id)
        except ApiError:
            self.debug_history = {}
            self.debug_error = _tr(self.current, "История недоступна.", "History unavailable.")
            return
        self.debug_history = history if isinstance(history, Mapping) else {}
        self.debug_error = ""

    def _toggle_debug(self) -> None:
        self.debug = not self.debug
        self.debug_scroll = 0
        self._load_debug()

    def _show_progress(self, message: str) -> None:
        self.notice = message
        if self._screen is not None:
            self._draw(self._screen)

    def _terminal_review(self) -> None:
        if response_status(self.current) in TERMINAL_STATUSES and self.review is None:
            try:
                self.review = self.api.review(self.session_id)
            except ApiError as exc:
                self.notice = f"{_label(self.current, 'review_unavailable')} {exc}"

    def _open_pending(self) -> None:
        pending = _pending(self.current)
        if pending:
            self.modal = (pending[0], dict(pending[1]), response_revision(self.current))
            self.modal_scroll = 0

    def _set_current(self, current: Mapping[str, Any]) -> None:
        self.current = current
        self.chat_scroll = 0
        self._terminal_review()
        self._open_pending()
        self._load_debug()

    def _refresh(self) -> None:
        self._set_current(self.api.get_session(self.session_id))

    def _submit(self, message: str, *, clear_draft: bool = False) -> None:
        expected_revision = response_revision(self.current)
        if self._message_attempt is None or self._message_attempt[:2] != (
            message,
            expected_revision,
        ):
            self._message_attempt = (message, expected_revision, new_idempotency_key())
        attempt_key = self._message_attempt[2]
        self._show_progress(_tr(self.current, "Отправка сообщения...", "Sending message..."))
        try:
            response = self.api.submit_message(
                self.session_id,
                message,
                expected_revision=expected_revision,
                idempotency_key=attempt_key,
            )
            try:
                self._refresh()
            except ApiError:
                self._set_current({**self.current, **response})
            self.notice = str(
                response.get("result")
                or _tr(self.current, "Сообщение отправлено.", "Message sent.")
            )
            self._message_attempt = None
            if clear_draft:
                self.draft = ""
            self.modal = None
            self._open_pending()
        except ApiError as exc:
            self.notice = f"Error: {exc}"
            try:
                self._refresh()
            except ApiError:
                pass
            if not exc.retryable or response_revision(self.current) != expected_revision:
                self._message_attempt = None

    def _request_hint(self) -> None:
        expected_revision = response_revision(self.current)
        if self._hint_attempt is None or self._hint_attempt[0] != expected_revision:
            self._hint_attempt = (expected_revision, new_idempotency_key("hint"))
        self._show_progress(_tr(self.current, "Запрос подсказки...", "Requesting hint..."))
        try:
            response = self.api.request_hint(
                self.session_id,
                expected_revision=expected_revision,
                idempotency_key=self._hint_attempt[1],
            )
            try:
                self._refresh()
            except ApiError:
                self._set_current({**self.current, **response})
            self.tab = 2
            self.side_scroll = 0
            self.notice = _tr(self.current, "Подсказка получена.", "Hint received.")
            self._hint_attempt = None
        except ApiError as exc:
            self.notice = f"Error: {exc}"
            try:
                self._refresh()
            except ApiError:
                pass
            if not exc.retryable or response_revision(self.current) != expected_revision:
                self._hint_attempt = None

    def _review_offer(self) -> None:
        pending = _pending(self.current)
        if pending:
            self._open_pending()
            return
        offers = _observation(self.current).get("active_offers") or []
        if offers:
            self.modal = ("offer", dict(offers[0]), response_revision(self.current))
            self.modal_scroll = 0
        else:
            self.tab = 0
            self.notice = _tr(
                self.current,
                "Нет активного окончательного предложения.",
                "No current formal offer.",
            )

    def _confirm(self, confirm: bool) -> None:
        if not self.modal or self.modal[0] not in {"publication", "acceptance"}:
            return
        kind, payload, revision = self.modal
        try:
            latest = self.api.get_session(self.session_id)
        except ApiError as exc:
            self.notice = f"{_tr(self.current, 'Не удалось проверить предложение:', 'Cannot verify offer:')} {exc}"
            return
        pending = _pending(latest)
        if response_revision(latest) != revision or pending != (kind, payload):
            self._set_current(latest)
            self.modal = None
            self.notice = _tr(
                self.current,
                "Предложение изменилось. Проверьте новую редакцию перед подтверждением.",
                "Offer changed. Review the current revision before confirming.",
            )
            return
        if confirm and payload.get("unresolved_required_terms"):
            self.notice = _tr(
                self.current,
                "Предложение не заполнено и не может быть подтверждено.",
                "This offer is incomplete and cannot be confirmed.",
            )
            return
        language = str(latest.get("language") or _observation(latest).get("language") or "ru")
        self.modal = None
        self._submit(_confirmation_text(kind, language, confirm=confirm))

    def _send_draft(self) -> bool:
        message = self.draft.strip()
        if not message:
            return True
        if message in {"/quit", "/exit"}:
            return False
        if message == "/hint":
            self.draft = ""
            self._request_hint()
            return True
        if message == "/debug":
            self.draft = ""
            self._toggle_debug()
            return True
        if message in {"/offer", "/brief", "/coach"}:
            self.tab = {"/offer": 0, "/brief": 1, "/coach": 2}[message]
            self.side_scroll = 0
            self.draft = ""
            return True
        if message == "/help":
            self.modal = ("help", {}, response_revision(self.current))
            self.draft = ""
            return True
        if response_status(self.current) in TERMINAL_STATUSES:
            self.notice = _tr(
                self.current,
                "Сессия завершена. Введите /quit для выхода.",
                "Session complete. Type /quit to exit.",
            )
            return True
        self._submit(message, clear_draft=True)
        return True

    def _write(self, window: Any, y: int, x: int, value: Any, width: int, attr: int = 0) -> None:
        try:
            if width > 0:
                if self._colors_enabled and not (attr & curses.A_COLOR):
                    attr |= self._color(COLOR_BASE)
                window.addstr(y, x, _clip(value, width), attr)
        except curses.error:
            pass

    def _color(self, pair: int) -> int:
        return curses.color_pair(pair) if self._colors_enabled else 0

    def _background(self, window: Any) -> None:
        if self._colors_enabled:
            window.bkgd(" ", 0)
            window.erase()
            height, width = window.getmaxyx()
            for row in range(height):
                window.hline(row, 0, " ", width, self._color(COLOR_BASE))
        else:
            window.bkgd(" ", curses.A_REVERSE)
            window.erase()

    def _init_colors(self) -> None:
        if not curses.has_colors():
            return
        try:
            curses.start_color()
            if curses.COLORS < 8 or curses.COLOR_PAIRS <= COLOR_BAND:
                return
            # ANSI color 0 is configurable by the terminal and may be gray.
            # The 256-color cube defines color 16 as RGB 0,0,0.
            black = 16 if curses.COLORS >= 256 else curses.COLOR_BLACK
            for pair, foreground in (
                (COLOR_BASE, curses.COLOR_WHITE),
                (COLOR_BORDER, curses.COLOR_CYAN),
                (COLOR_USER, curses.COLOR_GREEN),
                (COLOR_COUNTERPART, curses.COLOR_MAGENTA),
                (COLOR_HEADING, curses.COLOR_YELLOW),
                (COLOR_ERROR, curses.COLOR_RED),
            ):
                curses.init_pair(pair, foreground, black)
            curses.init_pair(COLOR_BAND, black, curses.COLOR_CYAN)
        except curses.error:
            return
        self._colors_enabled = True

    def _line_style(self, kind: str, line: str) -> int:
        if kind == "conversation":
            if line.startswith(_label(self.current, "case") + ":"):
                return curses.A_BOLD | self._color(COLOR_HEADING)
            if line.startswith(_label(self.current, "you") + "  r"):
                return curses.A_BOLD | self._color(COLOR_USER)
            if any(
                line.startswith(_label(self.current, role) + "  r")
                for role in ("buyer", "seller", "counterpart")
            ):
                return curses.A_BOLD | self._color(COLOR_COUNTERPART)
        if kind == "offer":
            if line.startswith(_label(self.current, "incomplete")):
                return curses.A_BOLD | self._color(COLOR_ERROR)
            if any(
                line.startswith(_label(self.current, key))
                for key in ("offer", "preliminary", "public_terms")
            ):
                return curses.A_BOLD | self._color(COLOR_HEADING)
        if kind in {"brief", "coach", "review", "modal"} and line in {
            _label(self.current, key)
            for key in (
                "objectives",
                "context",
                "constraints",
                "priorities",
                "coaching",
                "signals",
                "hints",
            )
        }:
            return curses.A_BOLD | self._color(COLOR_HEADING)
        return 0

    def _pane(
        self,
        window: Any,
        title: str,
        lines: list[str],
        *,
        kind: str,
        scroll: int = 0,
        bottom: bool = False,
    ) -> None:
        self._background(window)
        window.attron(self._color(COLOR_HEADING if kind == "modal" else COLOR_BORDER))
        window.box()
        window.attroff(self._color(COLOR_HEADING if kind == "modal" else COLOR_BORDER))
        height, width = window.getmaxyx()
        self._write(
            window, 0, 2, f" {title} ", width - 4, curses.A_BOLD | self._color(COLOR_HEADING)
        )
        visible = max(0, height - 2)
        wrapped: list[tuple[str, int]] = []
        for line in lines:
            attr = self._line_style(kind, line)
            wrapped.extend((part, attr) for part in _wrap(line, width - 4))
        start = (
            max(0, len(wrapped) - visible - scroll)
            if bottom
            else min(max(0, scroll), max(0, len(wrapped) - visible))
        )
        for row, (line, attr) in enumerate(wrapped[start : start + visible], 1):
            self._write(window, row, 2, line, width - 4, attr)
        window.noutrefresh()

    def _modal_lines(self) -> list[str]:
        if not self.modal:
            return []
        kind, payload, _ = self.modal
        if kind == "help":
            if _tr(self.current, "ru", "en") == "ru":
                return [
                    "Enter: отправить сообщение",
                    "Tab: переключить правую панель",
                    "Page Up / Page Down: прокрутить диалог",
                    "F5 / F6: прокрутить правую панель",
                    "F2: открыть предложение или подтверждение",
                    "F3 или /debug: показать или скрыть отладку",
                    "F7 / F8: прокрутить отладку",
                    "/hint: запросить подсказку",
                    "/offer, /brief, /coach: выбрать панель",
                    "/quit: выйти из сессии",
                    "Esc: закрыть окно",
                ]
            return [
                "Enter: send message",
                "Tab: switch Offer / Brief / Coach",
                "Page Up / Page Down: scroll conversation",
                "F5 / F6: scroll side panel",
                "F2: review current offer or pending confirmation",
                "F3 or /debug: show or hide debug state",
                "F7 / F8: scroll debug state",
                "/hint: request a coaching hint",
                "/offer, /brief, /coach: select side panel",
                "/quit: leave this session",
                "Esc: close this window",
            ]
        if kind == "publication":
            lines = [
                f"{_label(self.current, 'preliminary')} rev {payload.get('proposal_revision', '?')}",
                _tr(
                    self.current,
                    "Подтверждение опубликует эту редакцию окончательного предложения.",
                    "Confirm to publish this exact final offer.",
                ),
            ]
        elif kind == "acceptance":
            lines = [
                f"{_label(self.current, 'offer')} rev {payload.get('offer_revision', '?')}",
                _tr(
                    self.current,
                    "Подтверждение примет эту редакцию полного предложения.",
                    "Confirm to accept this exact complete offer.",
                ),
            ]
        else:
            lines = [f"{_label(self.current, 'offer')} rev {payload.get('offer_revision', '?')}"]
        lines.extend(("", *_term_lines(payload.get("terms") or {})))
        unresolved = payload.get("unresolved_required_terms") or []
        if unresolved:
            lines.extend(
                (
                    "",
                    _label(self.current, "incomplete")
                    + ": "
                    + ", ".join(str(item) for item in unresolved),
                )
            )
        if kind in {"publication", "acceptance"}:
            lines.extend(
                (
                    "",
                    _tr(
                        self.current,
                        "Enter/Y: подтвердить  C: отменить  Esc: назад",
                        "Enter/Y: confirm  C: cancel  Esc: return",
                    ),
                )
            )
        else:
            lines.extend(("", _tr(self.current, "Esc: назад", "Esc: return")))
        return lines

    def _draw(self, screen: Any) -> None:
        self._background(screen)
        height, width = screen.getmaxyx()
        if height < 16 or width < 72:
            self._write(
                screen,
                0,
                0,
                _tr(self.current, "Увеличьте терминал до 72 x 16.", "Resize terminal to 72 x 16."),
                width - 1,
            )
            self._write(
                screen,
                1,
                0,
                _tr(self.current, "Ctrl+C: выход.", "Ctrl+C: exit."),
                width - 1,
            )
            screen.noutrefresh()
            curses.doupdate()
            return
        observation = _observation(self.current)
        scenario = self.current.get("scenario_id") or "Negotiation"
        role = observation.get("role") or "player"
        status = response_status(self.current)
        header = f" {_label(self.current, 'app')} | {scenario} | {role} | r{response_revision(self.current)} | {status}"
        band = self._color(COLOR_BAND) if self._colors_enabled else curses.A_BOLD
        self._write(screen, 0, 0, " " * (width - 1), width - 1, band)
        self._write(screen, 0, 0, header, width - 1, band | curses.A_BOLD)
        footer = self.notice or _label(self.current, "footer")
        footer_style = (
            self._color(COLOR_ERROR)
            if self.notice.startswith("Error:")
            else self._color(COLOR_HEADING)
            if self.notice
            else band
        )
        self._write(screen, height - 1, 0, " " * (width - 1), width - 1, footer_style)
        self._write(screen, height - 1, 0, footer, width - 1, footer_style | curses.A_BOLD)
        screen.noutrefresh()
        body_height = height - 6
        left_width = max(45, int(width * 0.66))
        right_width = width - left_width
        conversation = curses.newwin(body_height, left_width, 1, 0)
        debug_height = min(max(6, body_height // 3), body_height - 5) if self.debug else 0
        side_height = body_height - debug_height
        side = curses.newwin(side_height, right_width, 1, left_width)
        composer = curses.newwin(4, width, height - 5, 0)
        self._pane(
            conversation,
            _label(self.current, "conversation"),
            conversation_lines(self.current, left_width - 6, case_title=self.case_title),
            kind="conversation",
            scroll=self.chat_scroll,
            bottom=True,
        )
        if self.review is not None:
            title, lines = _label(self.current, "review"), review_lines(self.review, self.current)
        else:
            title = _label(self.current, TABS[self.tab])
            lines = (offer_lines, brief_lines, coach_lines)[self.tab](self.current)
        self._pane(
            side,
            title + "  [Tab]",
            lines,
            kind="review" if self.review else TABS[self.tab],
            scroll=self.side_scroll,
        )
        if self.debug:
            debug_window = curses.newwin(debug_height, right_width, 1 + side_height, left_width)
            lines = debug_lines(self.current, self.debug_history)
            if self.debug_error:
                lines.insert(0, self.debug_error)
            self._pane(
                debug_window,
                _label(self.current, "debug") + " [F3]",
                lines,
                kind="debug",
                scroll=self.debug_scroll,
            )
        self._background(composer)
        composer.attron(self._color(COLOR_BORDER))
        composer.box()
        composer.attroff(self._color(COLOR_BORDER))
        self._write(
            composer,
            0,
            2,
            f" {_label(self.current, 'message')} ",
            width - 4,
            curses.A_BOLD | self._color(COLOR_HEADING),
        )
        draft_lines = _wrap("> " + self.draft, width - 4)[-2:]
        for row, line in enumerate(draft_lines, 1):
            self._write(composer, row, 2, line, width - 4, self._color(COLOR_USER))
        try:
            curses.curs_set(0 if self.modal else 1)
            composer.move(
                len(draft_lines),
                min(width - 2, 2 + sum(_width(character) for character in draft_lines[-1])),
            )
        except curses.error:
            pass
        composer.noutrefresh()
        if self.modal:
            modal_height = min(height - 4, max(10, int(height * 0.75)))
            modal_width = min(width - 4, max(54, int(width * 0.8)))
            modal = curses.newwin(
                modal_height, modal_width, (height - modal_height) // 2, (width - modal_width) // 2
            )
            kind = self.modal[0]
            title = (
                _tr(self.current, "Справка", "Help")
                if kind == "help"
                else _tr(self.current, "Подтверждение", "Confirmation")
                if kind != "offer"
                else _tr(self.current, "Условия предложения", "Offer details")
            )
            self._pane(modal, title, self._modal_lines(), kind="modal", scroll=self.modal_scroll)
        curses.doupdate()

    def _main(self, screen: Any) -> int:
        self._screen = screen
        self._init_colors()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        screen.keypad(True)
        while True:
            self._draw(screen)
            try:
                key = screen.get_wch()
            except curses.error:
                continue
            if key == curses.KEY_RESIZE:
                continue
            if key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
                delta = 8 if key == curses.KEY_PPAGE else -8
                if self.modal:
                    self.modal_scroll = max(0, self.modal_scroll - delta)
                else:
                    self.chat_scroll = max(0, self.chat_scroll + delta)
                continue
            if self.modal:
                if key == "\x1b":
                    self.modal = None
                elif self.modal[0] in {"publication", "acceptance"}:
                    if key in ("\n", "\r", curses.KEY_ENTER, "y", "Y"):
                        self._confirm(True)
                    elif key in ("c", "C"):
                        self._confirm(False)
                continue
            if key == curses.KEY_F2:
                self._review_offer()
            elif key == curses.KEY_F3:
                self._toggle_debug()
            elif key == curses.KEY_F5:
                self.side_scroll = max(0, self.side_scroll - 5)
            elif key == curses.KEY_F6:
                self.side_scroll += 5
            elif key == curses.KEY_F7 and self.debug:
                self.debug_scroll = max(0, self.debug_scroll - 5)
            elif key == curses.KEY_F8 and self.debug:
                self.debug_scroll += 5
            elif key == "\t":
                self.tab = (self.tab + 1) % len(TABS)
                self.side_scroll = 0
            elif key in ("\n", "\r", curses.KEY_ENTER):
                if not self._send_draft():
                    return 0
            elif key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                self.draft = self.draft[:-1]
            elif key == "\x15":
                self.draft = ""
            elif key == "\x0e":
                self.draft += "\n"
            elif key == "\x03":
                return 0
            elif (
                key == "q" and response_status(self.current) in TERMINAL_STATUSES and not self.draft
            ):
                return 0
            elif isinstance(key, str) and key.isprintable() and len(self.draft) < 10_000:
                self.draft += key


def run_play_tui(
    api: NegotiationApiClient,
    session_id: str,
    *,
    debug: bool = False,
) -> int:
    """Open the terminal UI after authentication, without displaying creation credentials."""

    current = api.get_session(session_id)
    case_title = str(current.get("scenario_id") or "")
    if case_title and current.get("scenario_version") is not None:
        try:
            scenario = api.get_scenario(case_title, int(current["scenario_version"]))
            case_title = str(scenario.get("title") or case_title)
        except ApiError:
            pass
    app = PlayTui(api, session_id, current, case_title=case_title, debug=debug)
    try:
        return curses.wrapper(app._main)
    except KeyboardInterrupt:
        return 0
