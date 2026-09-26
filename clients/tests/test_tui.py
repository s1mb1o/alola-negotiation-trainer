from __future__ import annotations

import curses
import unittest
from unittest.mock import patch

from clients.api import ApiError
from clients.tui import (
    COLOR_BAND,
    COLOR_BASE,
    COLOR_HEADING,
    PlayTui,
    _confirmation_text,
    brief_lines,
    coach_lines,
    conversation_lines,
    debug_lines,
    offer_lines,
    run_play_tui,
)


def session(*, revision=3, pending=None):
    return {
        "session_id": "session-1",
        "scenario_id": "freight_contract_ru",
        "revision": revision,
        "status": "active",
        "language": "ru",
        "hints_enabled": True,
        "pending_confirmation": pending,
        "observation": {
            "participant_id": "buyer-id",
            "role": "buyer",
            "currency": "RUB",
            "conversation": [
                {
                    "participant_id": "seller-id",
                    "role": "seller",
                    "revision": 1,
                    "message": "Цена?",
                },
                {
                    "participant_id": "buyer-id",
                    "role": "buyer",
                    "revision": 2,
                    "message": "Обсудим.",
                },
            ],
            "role_brief": {"summary": "Вы покупатель.", "objectives": ["Снизить цену."]},
            "active_offers": [
                {
                    "offer_id": "offer-1",
                    "offer_revision": 2,
                    "proposer_role": "seller",
                    "terms": {"price": 1000},
                    "unresolved_required_terms": [],
                }
            ],
            "assistance": {"coaching": "Спросите об условиях."},
            "hints": [],
            "remaining_hints": 3,
        },
        "participant_credentials": {"buyer": "private-token"},
        "internal_state": {"seller_reservation_utility": 42},
    }


class FakeApi:
    def __init__(self, current):
        self.current = current
        self.submits = []
        self.hint_calls = []
        self.history_calls = 0

    def get_session(self, _session_id):
        return self.current

    def submit_message(self, _session_id, message, *, expected_revision, idempotency_key):
        self.submits.append((message, expected_revision, idempotency_key))
        self.current = {
            **self.current,
            "revision": expected_revision + 1,
            "status": "agreement_reached",
            "pending_confirmation": None,
            "pending_offer_publication": None,
        }
        return {**self.current, "result": "agreement_reached"}

    def request_hint(self, _session_id, *, expected_revision, idempotency_key):
        self.hint_calls.append(expected_revision)
        observation = {
            **self.current["observation"],
            "hints": [{"id": "hint_1", "text": "Проверьте интерес вопросом."}],
            "remaining_hints": 2,
        }
        self.current = {
            **self.current,
            "revision": expected_revision + 1,
            "observation": observation,
        }
        return {"revision": expected_revision + 1, "observation": observation}

    def review(self, _session_id):
        return {"outcome": {"agreement": True}, "outcome_score": 0.8}

    def history(self, _session_id):
        self.history_calls += 1
        return {
            "events": [
                {
                    "type": "npc.intent.committed",
                    "payload": {"action": "inform", "speech_act": "question"},
                },
                {
                    "type": "npc.utterance.delivered",
                    "payload": {
                        "speech_act": "question",
                        "dialogue_renderer": {"mode": "template", "fallback_used": False},
                    },
                },
            ]
        }


class FlakyApi(FakeApi):
    def submit_message(self, _session_id, message, *, expected_revision, idempotency_key):
        if not self.submits:
            self.submits.append((message, expected_revision, idempotency_key))
            raise ApiError("timed out", retryable=True)
        return super().submit_message(
            _session_id,
            message,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
        )


class TuiViewTest(unittest.TestCase):
    def test_panels_project_only_actor_safe_fields(self):
        current = session()
        displayed = "\n".join(
            conversation_lines(current, 45)
            + offer_lines(current)
            + brief_lines(current)
            + coach_lines(current)
        )
        for expected in ("Цена?", "Обсудим.", "price: 1000", "Вы покупатель."):
            self.assertIn(expected, displayed)
        self.assertNotIn("private-token", displayed)
        self.assertNotIn("seller_reservation_utility", displayed)

    def test_case_description_precedes_the_dialogue(self):
        current = session()
        lines = conversation_lines(current, 45, case_title="Срочная грузовая перевозка")
        self.assertEqual(lines[0], "СИТУАЦИЯ: Срочная грузовая перевозка")
        self.assertIn("Вы покупатель.", lines)
        self.assertIn("Цели: Снизить цену.", lines)
        self.assertLess(lines.index("Цели: Снизить цену."), lines.index("Продавец  r1"))

    def test_session_uses_title_from_its_pinned_public_scenario(self):
        current = session()
        current["scenario_version"] = 2
        api = FakeApi(current)
        scenario_calls = []

        def get_scenario(scenario_id, version):
            scenario_calls.append((scenario_id, version))
            return {"title": "Срочная грузовая перевозка"}

        api.get_scenario = get_scenario
        with patch("clients.tui.curses.wrapper", return_value=0) as wrapper:
            self.assertEqual(run_play_tui(api, "session-1"), 0)
        self.assertEqual(scenario_calls, [("freight_contract_ru", 2)])
        self.assertEqual(
            wrapper.call_args.args[0].__self__.case_title, "Срочная грузовая перевозка"
        )

    def test_256_color_theme_uses_fixed_black_instead_of_ansi_black(self):
        current = session()
        tui = PlayTui(FakeApi(current), "session-1", current)
        with (
            patch("clients.tui.curses.has_colors", return_value=True),
            patch("clients.tui.curses.start_color"),
            patch("clients.tui.curses.init_pair") as init_pair,
            patch("clients.tui.curses.COLORS", 256, create=True),
            patch("clients.tui.curses.COLOR_PAIRS", 64, create=True),
        ):
            tui._init_colors()
        self.assertTrue(tui._colors_enabled)
        pairs = {call.args[0]: call.args[1:] for call in init_pair.call_args_list}
        self.assertEqual(pairs[COLOR_BASE][1], 16)
        self.assertEqual(pairs[COLOR_BAND][0], 16)

    def test_plain_text_keeps_fixed_black_background(self):
        current = session()
        tui = PlayTui(FakeApi(current), "session-1", current)
        tui._colors_enabled = True

        class RecordingWindow:
            def __init__(self):
                self.writes = []

            def addstr(self, *args):
                self.writes.append(args)

        window = RecordingWindow()
        with patch("clients.tui.curses.color_pair", side_effect=lambda pair: pair << 8):
            tui._write(window, 0, 0, "ordinary", 20)
            tui._write(window, 1, 0, "bold", 20, curses.A_BOLD)
            tui._write(window, 2, 0, "heading", 20, COLOR_HEADING << 8)

        self.assertEqual(window.writes[0][3] & curses.A_COLOR, COLOR_BASE << 8)
        self.assertEqual(window.writes[1][3] & curses.A_COLOR, COLOR_BASE << 8)
        self.assertEqual(window.writes[2][3] & curses.A_COLOR, COLOR_HEADING << 8)

    def test_debug_projection_uses_only_player_visible_fields(self):
        current = session()
        current.update(
            {
                "scenario_version": 2,
                "round": 3,
                "substantive_turn_count": 4,
                "difficulty": "normal",
                "next_actor": "buyer-id",
            }
        )
        history = FakeApi(current).history("session-1")
        displayed = "\n".join(debug_lines(current, history))
        self.assertIn("session_revision=3", displayed)
        self.assertIn("next_actor=Вы", displayed)
        self.assertIn("npc_action=inform", displayed)
        self.assertIn("npc_speech_act=question", displayed)
        self.assertIn("renderer=template", displayed)
        self.assertNotIn("private-token", displayed)
        self.assertNotIn("seller_reservation_utility", displayed)

    def test_debug_panel_occupies_lower_right(self):
        current = session()
        tui = PlayTui(FakeApi(current), "session-1", current, debug=True)

        class Window:
            def __init__(self, height, width):
                self.height = height
                self.width = width

            def getmaxyx(self):
                return self.height, self.width

            def __getattr__(self, _name):
                return lambda *_args: None

        screen = Window(40, 120)
        with (
            patch(
                "clients.tui.curses.newwin", side_effect=lambda h, w, _y, _x: Window(h, w)
            ) as newwin,
            patch("clients.tui.curses.curs_set"),
            patch("clients.tui.curses.doupdate"),
            patch.object(tui, "_background"),
            patch.object(tui, "_write"),
            patch.object(tui, "_pane") as pane,
        ):
            tui._draw(screen)

        body_height = 40 - 6
        side = newwin.call_args_list[1].args
        debug = newwin.call_args_list[3].args
        self.assertEqual(side[0] + debug[0], body_height)
        self.assertEqual(side[2] + side[0], debug[2])
        self.assertEqual(side[3], debug[3])
        self.assertEqual(pane.call_args_list[-1].kwargs["kind"], "debug")

    def test_debug_can_toggle_and_refresh_history(self):
        current = session()
        api = FakeApi(current)
        tui = PlayTui(api, "session-1", current)
        self.assertEqual(api.history_calls, 0)
        tui.draft = "/debug"
        self.assertTrue(tui._send_draft())
        self.assertTrue(tui.debug)
        self.assertEqual(api.history_calls, 1)
        tui._set_current(current)
        self.assertEqual(api.history_calls, 2)
        tui._toggle_debug()
        self.assertFalse(tui.debug)

    def test_incomplete_offer_is_labeled(self):
        current = session()
        current["observation"]["active_offers"][0]["unresolved_required_terms"] = ["delivery"]
        self.assertIn("Не заполнено: delivery", "\n".join(offer_lines(current)))

    def test_confirmation_rechecks_exact_revision_and_terms(self):
        pending = {"offer_id": "offer-1", "offer_revision": 2, "terms": {"price": 1000}}
        current = session(pending=pending)
        api = FakeApi(current)
        tui = PlayTui(api, "session-1", current)
        self.assertEqual(tui.modal[0], "acceptance")
        tui._confirm(True)
        self.assertEqual(len(api.submits), 1)
        self.assertEqual(api.submits[0][1], 3)
        self.assertEqual(
            api.submits[0][0],
            _confirmation_text("acceptance", "ru", confirm=True),
        )
        self.assertEqual(tui.current["status"], "agreement_reached")

    def test_changed_offer_cannot_be_confirmed(self):
        pending = {"offer_id": "offer-1", "offer_revision": 2, "terms": {"price": 1000}}
        current = session(pending=pending)
        api = FakeApi(current)
        tui = PlayTui(api, "session-1", current)
        api.current = session(revision=4, pending={**pending, "terms": {"price": 900}})
        tui._confirm(True)
        self.assertEqual(api.submits, [])
        self.assertIn("изменилось", tui.notice)

    def test_publication_confirmation_uses_the_authored_snapshot(self):
        current = session()
        current["pending_offer_publication"] = {
            "proposal_id": "proposal-1",
            "proposal_revision": 4,
            "snapshot_digest": "digest-1",
            "terms": {"price": 1000},
            "unresolved_required_terms": [],
        }
        api = FakeApi(current)
        tui = PlayTui(api, "session-1", current)
        tui._confirm(True)
        self.assertEqual(api.submits[0][0], "Подтверждаю окончательное предложение")
        self.assertEqual(api.submits[0][1], 3)

    def test_hint_uses_current_revision_and_updates_coach(self):
        current = session()
        api = FakeApi(current)
        tui = PlayTui(api, "session-1", current)
        tui._request_hint()
        self.assertEqual(api.hint_calls, [3])
        self.assertEqual(tui.current["revision"], 4)
        self.assertIn("Проверьте интерес вопросом.", "\n".join(coach_lines(tui.current)))

    def test_retry_after_uncertain_transport_result_uses_same_idempotency_key(self):
        current = session()
        api = FlakyApi(current)
        tui = PlayTui(api, "session-1", current)
        tui._submit("Сколько стоит доставка?")
        self.assertIn("timed out", tui.notice)
        tui._submit("Сколько стоит доставка?")
        self.assertEqual(api.submits[0][2], api.submits[1][2])


if __name__ == "__main__":
    unittest.main()
