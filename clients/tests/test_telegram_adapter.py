from __future__ import annotations

import unittest

from clients.api import ApiError
from clients.telegram_adapter import InMemoryChatBindingStore, TelegramNegotiationAdapter


class FakePublicApi:
    def __init__(self, calls=None, token=None, state=None):
        self.calls = calls if calls is not None else []
        self.token = token
        self.state = state if state is not None else {"created": 0, "fail_next_create": False}

    def create_session(self, **kwargs):
        self.calls.append(("create_session", kwargs))
        if self.state["fail_next_create"]:
            self.state["fail_next_create"] = False
            raise ApiError("backend unavailable", status=503, error="service_unavailable")
        self.state["created"] += 1
        return {
            "session_id": f"sess_chat_{self.state['created']}",
            "revision": 0,
            "participant_credentials": {"buyer": "chat-token"},
        }

    def with_participant_token(self, token):
        return FakePublicApi(self.calls, token, self.state)

    def get_session(self, session_id):
        self.calls.append(("get_session", {"session_id": session_id, "token": self.token}))
        return {"session_id": session_id, "revision": 3, "status": "active"}

    def submit_message(self, session_id, message, *, expected_revision, idempotency_key=None):
        self.calls.append(
            (
                "submit_message",
                {
                    "session_id": session_id,
                    "message": message,
                    "expected_revision": expected_revision,
                    "token": self.token,
                },
            )
        )
        return {"revision": 4, "status": "active", "next_actor": "participant_buyer"}


class TelegramAdapterTest(unittest.TestCase):
    def test_chat_state_stays_in_adapter_and_messages_use_public_api(self):
        api = FakePublicApi()
        adapter = TelegramNegotiationAdapter(api, InMemoryChatBindingStore())
        created = adapter.start(12345, scenario_id="saas_subscription_ru")
        result = adapter.handle_text(12345, "Предлагаю цену 1100000.")
        create_payload = api.calls[0][1]
        submit_payload = api.calls[-1][1]
        self.assertNotIn("chat_id", create_payload)
        self.assertNotIn("chat_id", submit_payload)
        self.assertEqual(submit_payload["message"], "Предлагаю цену 1100000.")
        self.assertEqual(submit_payload["expected_revision"], 3)
        self.assertNotIn("chat-token", repr(created))
        self.assertNotIn("chat-token", repr(result))

    def test_start_on_a_bound_chat_refuses_unless_replace_is_explicit(self):
        api = FakePublicApi()
        store = InMemoryChatBindingStore()
        adapter = TelegramNegotiationAdapter(api, store)
        adapter.start(1, scenario_id="saas_subscription_ru")

        with self.assertRaises(ApiError) as raised:
            adapter.start(1, scenario_id="saas_subscription_ru")
        self.assertIn("sess_chat_1", str(raised.exception))
        self.assertIn("replace=True", str(raised.exception))
        self.assertEqual(sum(call[0] == "create_session" for call in api.calls), 1)
        self.assertEqual(store.get("1").session_id, "sess_chat_1")

        replaced = adapter.start(1, scenario_id="saas_subscription_ru", replace=True)
        self.assertEqual(replaced["session_id"], "sess_chat_2")
        self.assertEqual(replaced["replaced_session_id"], "sess_chat_1")
        self.assertEqual(store.get("1").session_id, "sess_chat_2")
        self.assertNotIn("chat-token", repr(replaced))

    def test_failed_replacement_keeps_the_existing_binding(self):
        api = FakePublicApi()
        store = InMemoryChatBindingStore()
        adapter = TelegramNegotiationAdapter(api, store)
        adapter.start(7, scenario_id="saas_subscription_ru")
        api.state["fail_next_create"] = True
        with self.assertRaises(ApiError):
            adapter.start(7, scenario_id="saas_subscription_ru", replace=True)
        self.assertEqual(store.get("7").session_id, "sess_chat_1")

    def test_forget_allows_a_fresh_start(self):
        api = FakePublicApi()
        adapter = TelegramNegotiationAdapter(api, InMemoryChatBindingStore())
        adapter.start(9, scenario_id="saas_subscription_ru")
        adapter.forget(9)
        created = adapter.start(9, scenario_id="saas_subscription_ru")
        self.assertEqual(created["session_id"], "sess_chat_2")
        self.assertNotIn("replaced_session_id", created)


if __name__ == "__main__":
    unittest.main()
