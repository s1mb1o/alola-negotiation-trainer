"""Transport-neutral chat adapter for a Telegram bot service.

This module intentionally has no Telegram framework dependency. A bot service owns
the chat mapping and forwards plain text through the public Player API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .api import ApiError, NegotiationApiClient, redact_secrets, response_revision
from .orchestrator import extract_participant_credentials


@dataclass(slots=True)
class ChatSessionBinding:
    chat_id: str
    session_id: str
    participant_token: str
    role: str


class ChatBindingStore(Protocol):
    def get(self, chat_id: str) -> ChatSessionBinding | None: ...
    def put(self, binding: ChatSessionBinding) -> None: ...
    def delete(self, chat_id: str) -> None: ...


class InMemoryChatBindingStore:
    """Example process-local store. Production services can provide another store."""

    def __init__(self) -> None:
        self._bindings: dict[str, ChatSessionBinding] = {}

    def get(self, chat_id: str) -> ChatSessionBinding | None:
        return self._bindings.get(str(chat_id))

    def put(self, binding: ChatSessionBinding) -> None:
        self._bindings[str(binding.chat_id)] = binding

    def delete(self, chat_id: str) -> None:
        self._bindings.pop(str(chat_id), None)


class TelegramNegotiationAdapter:
    """Map a Telegram chat to participant-scoped public API calls."""

    def __init__(self, api: NegotiationApiClient, store: ChatBindingStore) -> None:
        self.api = api
        self.store = store

    def start(
        self,
        chat_id: str | int,
        *,
        scenario_id: str,
        scenario_version: int = 1,
        language: str = "ru",
        role: str = "buyer",
        other_role: str = "seller",
        replace: bool = False,
    ) -> dict[str, Any]:
        """Start a session for the chat; an existing binding is kept unless ``replace`` is set."""

        existing = self.store.get(str(chat_id))
        if existing is not None and not replace:
            raise ApiError(
                "This chat is already bound to negotiation session "
                f"{existing.session_id!r}. Finish it or forget it before starting a new one, "
                "or start with replace=True to forget it explicitly."
            )
        created = self.api.create_session(
            scenario_id=scenario_id,
            scenario_version=scenario_version,
            language=language,
            participants=[
                {"role": role, "controller": "human"},
                {"role": other_role, "controller": "built_in_npc"},
            ],
            difficulty="normal",
            hints_enabled=True,
            run_mode="training",
        )
        session_id = created.get("session_id")
        if not isinstance(session_id, str):
            raise ApiError("Session creation did not return session_id")
        token = extract_participant_credentials(created).get(role)
        if not token:
            raise ApiError("Session creation did not deliver the chat participant credential")
        if existing is not None:
            # The old binding is forgotten only after the new session exists.
            self.store.delete(str(chat_id))
        self.store.put(
            ChatSessionBinding(
                chat_id=str(chat_id),
                session_id=session_id,
                participant_token=token,
                role=role,
            )
        )
        result = redact_secrets(created, (token,))
        if existing is not None:
            result["replaced_session_id"] = existing.session_id
        return result

    def handle_text(self, chat_id: str | int, text: str) -> dict[str, Any]:
        binding = self.store.get(str(chat_id))
        if binding is None:
            raise ApiError("No active negotiation is mapped to this chat")
        participant_api = self.api.with_participant_token(binding.participant_token)
        session = participant_api.get_session(binding.session_id)
        result = participant_api.submit_message(
            binding.session_id,
            text,
            expected_revision=response_revision(session),
        )
        return redact_secrets(result, (binding.participant_token,))

    def history(self, chat_id: str | int) -> Any:
        binding = self._required_binding(chat_id)
        return self.api.with_participant_token(binding.participant_token).history(
            binding.session_id
        )

    def review(self, chat_id: str | int) -> Any:
        binding = self._required_binding(chat_id)
        return self.api.with_participant_token(binding.participant_token).review(binding.session_id)

    def forget(self, chat_id: str | int) -> None:
        self.store.delete(str(chat_id))

    def _required_binding(self, chat_id: str | int) -> ChatSessionBinding:
        binding = self.store.get(str(chat_id))
        if binding is None:
            raise ApiError("No active negotiation is mapped to this chat")
        return binding
