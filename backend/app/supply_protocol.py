"""Opt-in preliminary package protocol. Storage remains owned by the service."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any
import uuid

from .dialogue import NpcDialogueRequest, redact_untrusted_credentials
from .dialogue_redirect import select_varied_fallback, topic_return_options
from .engine import ParsedAction, offer_is_acceptable, offer_is_bindable
from .reply_retrieval import retrieve_reply_examples
from .training import npc_training_context
from .scenarios import canonical_json, digest
from .supply import (
    is_supply_scenario,
    validate_supply_terms,
    unresolved_supply_terms,
    format_supply_terms,
    supply_financial_summary,
)
from .supply_language import parse_supply_message, decide_supply_action


def supply_current(state: dict) -> dict:
    return (
        state.get("preliminary_proposal")
        or state.get("active_offer")
        or state.get("agreement_offer")
        or {}
    )


def supply_envelope(scenario: dict, state: dict, participant_id: str) -> dict:
    if not is_supply_scenario(scenario):
        return {}
    result: dict[str, Any] = {"negotiation_contract_version": "supply-package-v1"}
    pending = state.get("pending_offer_publication") or {}
    result["pending_offer_publication"] = None
    result["pending_confirmation"] = None
    if pending.get("participant_id") == participant_id:
        result["confirmation_kind"] = "publish_offer"
        result["pending_offer_publication"] = {
            key: deepcopy(pending[key])
            for key in (
                "proposal_id",
                "proposal_revision",
                "terms",
                "snapshot_digest",
                "unresolved_required_terms",
            )
        }
    elif (state.get("pending_confirmation") or {}).get("participant_id") == participant_id:
        result["confirmation_kind"] = "accept_offer"
        acceptance = state["pending_confirmation"]
        result["pending_confirmation"] = {
            key: deepcopy(acceptance[key]) for key in ("offer_id", "offer_revision", "terms")
        }
        result["pending_confirmation"]["unresolved_required_terms"] = []
    return result


class SupplyProtocolMixin:
    def _supply_preextract(self, session_id, token, request, request_digest):
        if self.supply_extractor is None:
            return None
        with self.database.read_connection() as connection:
            session, participant = self._authenticated_rows(connection, session_id, token)
            if (
                session["status"] != "active"
                or session["revision"] != request.expected_revision
                or session["next_participant_id"] != participant["id"]
                or self._idempotency_result(
                    connection,
                    f"message:{session_id}:{participant['id']}",
                    request.idempotency_key,
                    request_digest,
                )
                is not None
                or self._pending_render_result(connection, session_id, int(session["revision"]))
                is not None
            ):
                return None
            scenario = self._scenario_source(connection, session)
            if not is_supply_scenario(scenario):
                return None
            state = json.loads(session["state_json"])
            if state.get("pending_confirmation") or state.get("pending_offer_publication"):
                return None
            message = redact_untrusted_credentials(
                request.message, token, *self._known_redaction_secrets
            )
            parsed = self._supply_parse(message, session, participant, state)
            if parsed.action != "inform" or parsed.clarification:
                return None
            current = supply_current(state)
        return self.supply_extractor.extract(
            message,
            session["language"],
            current.get("terms", {}),
            current.get("proposal_revision", current.get("offer_revision", 0)),
            scenario,
        )

    @staticmethod
    def _supply_initialize(state, participant_id, role, terms):
        state["active_offer"] = None
        state["pending_offer_publication"] = None
        state["preliminary_proposal"] = {
            "proposal_id": "proposal_" + uuid.uuid4().hex[:20],
            "proposal_revision": 1,
            "proposer_participant_id": participant_id,
            "proposer_role": role,
            "terms": deepcopy(terms),
            "status": "active",
            "source_event_ids": [],
        }

    @staticmethod
    def _supply_parse(message, session, participant, state):
        pending_kind = None
        if (state.get("pending_offer_publication") or {}).get("participant_id") == participant[
            "id"
        ]:
            pending_kind = "publish_offer"
        elif (state.get("pending_confirmation") or {}).get("participant_id") == participant["id"]:
            pending_kind = "accept_offer"
        current = supply_current(state)
        return parse_supply_message(
            message,
            session["language"],
            current.get("terms", {}),
            current.get("proposal_revision", current.get("offer_revision", 0)),
            pending_kind,
        )

    @staticmethod
    def _supply_observation(scenario, state):
        if not is_supply_scenario(scenario):
            return {}
        current = supply_current(state)
        proposals = []
        if (
            state.get("preliminary_proposal")
            and state["preliminary_proposal"]["status"] == "active"
        ):
            proposal = deepcopy(state["preliminary_proposal"])
            proposal["unresolved_required_terms"] = unresolved_supply_terms(
                scenario, proposal["terms"]
            )
            proposals.append(proposal)
        terms = current.get("terms", {})
        result = {
            "negotiation_contract_version": "supply-package-v1",
            "preliminary_proposals": proposals,
            "current_public_terms": deepcopy(terms),
            "unresolved_required_terms": unresolved_supply_terms(scenario, terms),
        }
        if not validate_supply_terms(scenario, terms, complete=True):
            result["financial_summary"] = supply_financial_summary(scenario, terms)
        return result

    def _supply_dialogue_request(
        self, connection, session, npc, scenario, speech_act, terms, player_message
    ):
        state = json.loads(session["state_json"])
        current = supply_current(state)
        role = current.get("proposer_role") or next(
            (
                role
                for role, pid in state["role_to_participant"].items()
                if pid == current.get("proposer_participant_id")
            ),
            None,
        )
        if speech_act in {"opening_offer", "opening_position"}:
            action = "opening"
            text = (
                "Добрый день. Предлагаю обсудить поставку промышленных компьютеров. Конфигурация вас устраивает?"
                if session["language"] == "ru"
                else "Hello. Let us discuss the industrial computer order. Does the configuration meet your needs?"
            )
        else:
            decision = decide_supply_action(
                scenario,
                npc["role"],
                current.get("terms", {}),
                player_message,
                session["language"],
                formal=bool(state.get("active_offer")),
                proposer_role=role,
            )
            action, text = decision.action, decision.text
        training_context = npc_training_context(state.get("training", {}), session["language"], player_message)
        context = self._dialogue_context(connection, session["id"], npc["id"])
        if action == "inform":
            # Use scalar topic aliases for wording only. The supply terms stay immutable.
            labels = (
                {"price": "цена", "prepayment_fraction": "условия оплаты", "delivery_weeks": "срок поставки"}
                if session["language"] == "ru" else
                {"price": "price", "prepayment_fraction": "payment terms", "delivery_weeks": "delivery timeline"}
            )
            options = topic_return_options(player_message, session["language"], labels, context, training_context)
            if options:
                text = select_varied_fallback(
                    options, player_message, [turn.text.split("\n\n", 1)[0] for turn in context if turn.speaker == "npc"],
                )
        block = format_supply_terms(scenario, terms, session["language"]) if terms else ""
        fallback = text + ("\n\n" + block if block else "")
        return NpcDialogueRequest(
            language=session["language"],
            currency=scenario["currency"],
            speech_act="acknowledge_information",
            approved_terms=tuple(sorted(deepcopy(terms).items())),
            public_interest_labels=(),
            participant_facing_terms=(),
            dialogue_context=context,
            approved_reply_options=(fallback,),
            fallback_text=fallback,
            retrieved_reply_examples=retrieve_reply_examples(
                scenario_id=str(scenario["id"]),
                npc_role=str(npc["role"]),
                language=str(session["language"]),
                speech_act="acknowledge_information",
                player_message=player_message,
                supply_action=action,
                training_context=training_context,
            ),
            scenario_title=scenario["title"],
            npc_role=npc["role"],
            difficulty=session["difficulty"],
            render_contract="supply-dialogue-v1",
            package_block=block,
            supply_action=action,
            training_context=training_context,
        )

    def _supply_commit_proposal(self, connection, session, actor, scenario, state, context, terms):
        previous = supply_current(state)
        source = {
            key: previous[key]
            for key in ("proposal_id", "proposal_revision", "offer_id", "offer_revision")
            if key in previous
        }
        if state.get("active_offer"):
            self._set_offer_status(connection, session["id"], state["active_offer"], "superseded")
        state["active_offer"] = None
        state["pending_confirmation"] = None
        state["pending_offer_publication"] = None
        state["pending_clarification"] = None
        proposal = {
            "proposal_id": previous.get("proposal_id", "proposal_" + uuid.uuid4().hex[:20]),
            "proposal_revision": previous.get("proposal_revision", 0) + 1,
            "proposer_participant_id": actor["id"],
            "proposer_role": actor["role"],
            "status": "active",
            "terms": deepcopy(terms),
            "source_event_ids": previous.get("source_event_ids", []),
        }
        event_id = self._insert_event(
            connection,
            session["id"],
            context.revision,
            actor["id"],
            "proposal.revised",
            {
                **proposal,
                "source": source,
                "source_revision": int(session["revision"]),
                "unresolved_required_terms": unresolved_supply_terms(scenario, terms),
            },
            {
                "term_delta": {
                    key: value
                    for key, value in terms.items()
                    if previous.get("terms", {}).get(key) != value
                }
            },
        )
        proposal["source_event_ids"] = [event_id]
        state["preliminary_proposal"] = proposal
        return event_id

    def _supply_publish(self, connection, session, actor, state, context, terms):
        if state.get("active_offer"):
            self._set_offer_status(connection, session["id"], state["active_offer"], "superseded")
        source = deepcopy(state.get("preliminary_proposal") or {})
        offer = {
            "offer_id": "offer_" + uuid.uuid4().hex[:20],
            "offer_revision": 1,
            "proposer_participant_id": actor["id"],
            "terms": deepcopy(terms),
            "status": "active",
        }
        connection.execute(
            "INSERT INTO offers(session_id, offer_id, offer_revision, proposer_participant_id, "
            "terms_json, status, created_session_revision) VALUES (?, ?, 1, ?, ?, 'active', ?)",
            (
                session["id"],
                offer["offer_id"],
                actor["id"],
                canonical_json(terms),
                context.revision,
            ),
        )
        state["active_offer"] = offer
        state["preliminary_proposal"] = None
        state["pending_offer_publication"] = None
        state["pending_confirmation"] = None
        return self._insert_event(
            connection,
            session["id"],
            context.revision,
            actor["id"],
            "offer.created",
            {
                **offer,
                "source_proposal_id": source.get("proposal_id"),
                "source_proposal_revision": source.get("proposal_revision"),
                "source_event_ids": source.get("source_event_ids", []),
                "unresolved_required_terms": [],
            },
            {},
        )

    def _apply_supply_action(
        self, connection, session, participant, scenario, state, message, parsed, initial_revision
    ):
        from .service import ServiceResult, TransitionContext

        def legacy(action, *, reason=None, details=None):
            return self._apply_participant_action(
                connection,
                session,
                participant,
                scenario,
                state,
                message,
                ParsedAction(action, reason_code=reason, details=details or {}),
                initial_revision,
                defer_builtin_npc=True,
                _supply_legacy=True,
            )

        def clarify(code, question=None):
            details = {
                "unresolved_required_terms": unresolved_supply_terms(
                    scenario, supply_current(state).get("terms", {})
                )
            }
            if question:
                details["question"] = question
            return legacy("clarification", reason=code, details=details)

        if parsed.clarification:
            return clarify(
                parsed.clarification_code or "ambiguous_composite_scope", parsed.clarification
            )
        current = supply_current(state)
        action = parsed.action
        if action in {"accept", "confirm_acceptance"}:
            if state.get("pending_offer_publication"):
                return clarify("ambiguous_composite_scope")
            return legacy("acceptance_intent" if action == "accept" else "confirm_acceptance")
        if action == "withdraw":
            state["preliminary_proposal"] = None
            state["pending_offer_publication"] = None
            return legacy("walk_away")
        context = TransitionContext(
            initial_revision,
            int(session["round"]),
            int(session["substantive_turn_count"]),
            str(session["status"]),
            participant["id"],
        )
        other = self._other_participant(connection, session["id"], participant["id"])
        control = False
        event_type = f"participant.{action}"
        payload: dict[str, Any] = {"topic": parsed.topic}
        result_name = "committed"
        if action == "amend":
            if parsed.source_revision != current.get(
                "proposal_revision", current.get("offer_revision", 0)
            ):
                return ServiceResult(
                    409, {"error": "proposal_not_active", "revision": initial_revision}
                )
            if not parsed.terms or validate_supply_terms(scenario, parsed.terms, complete=False):
                return clarify("invalid_composite_terms")
        elif action == "publish":
            terms = current.get("terms", {})
            if validate_supply_terms(scenario, terms, complete=True):
                return clarify("unresolved_composite_terms")
            if not offer_is_bindable(scenario, terms):
                return clarify("invalid_composite_terms")
            if current.get("proposer_participant_id") != participant["id"]:
                if other["controller"] != "built_in_npc":
                    return clarify("ambiguous_composite_scope")
                action = "question"  # Ask the NPC to present its package; this is not acceptance.
                event_type = "participant.question"
            elif not state.get("preliminary_proposal"):
                return clarify("ambiguous_composite_scope")
            else:
                state["pending_confirmation"] = None
                state["pending_offer_publication"] = {
                    "participant_id": participant["id"],
                    "proposal_id": current["proposal_id"],
                    "proposal_revision": current["proposal_revision"],
                    "terms": deepcopy(terms),
                    "snapshot_digest": digest(terms),
                    "unresolved_required_terms": [],
                }
                control, event_type, result_name = (
                    True,
                    "publication.confirmation_required",
                    "confirmation_required",
                )
                payload = {
                    key: value
                    for key, value in state["pending_offer_publication"].items()
                    if key != "participant_id"
                }
        elif action == "confirm_publication":
            pending = state.get("pending_offer_publication") or {}
            if (
                pending.get("participant_id") != participant["id"]
                or not state.get("preliminary_proposal")
                or pending.get("proposal_id") != current.get("proposal_id")
                or pending.get("proposal_revision") != current.get("proposal_revision")
                or pending.get("snapshot_digest") != digest(current.get("terms", {}))
            ):
                return ServiceResult(
                    409, {"error": "proposal_not_active", "revision": initial_revision}
                )
            if not offer_is_bindable(scenario, current["terms"]):
                return clarify("invalid_composite_terms")
        elif action == "cancel":
            state["pending_offer_publication"] = None
            state["pending_confirmation"] = None
            control, event_type, result_name = (
                True,
                "finalization.cancelled",
                "confirmation_cancelled",
            )
        elif state.get("pending_offer_publication") or state.get("pending_confirmation"):
            control = True  # A question does not abandon or transfer an actionable confirmation.
        context.revision += 1
        state["pending_clarification"] = None
        if action == "amend":
            event_id = self._supply_commit_proposal(
                connection, session, participant, scenario, state, context, parsed.terms
            )
        elif action == "confirm_publication":
            event_id = self._supply_publish(
                connection, session, participant, state, context, current["terms"]
            )
        else:
            event_id = self._insert_event(
                connection,
                session["id"],
                context.revision,
                participant["id"],
                event_type,
                payload,
                {},
            )
        self._insert_message(
            connection, session["id"], context.revision, participant, message, session["language"]
        )
        if control:
            count = self._record_protocol_control(state)
            if count >= self._protocol_control_limit(scenario):
                self._expire_protocol_controls(
                    connection,
                    session,
                    participant,
                    state,
                    context,
                    "protocol_control_limit_reached",
                    count,
                )
                state["pending_offer_publication"] = None
        else:
            state["consecutive_protocol_controls"] = 0
            context.substantive_turn_count += 1
            self._advance_round(state, participant["id"], context, scenario)
            context.next_participant_id = other["id"]
        if (
            context.status == "active"
            and state["completed_rounds"] >= scenario["protocol"]["max_rounds"]
        ):
            context.status, context.next_participant_id = "expired", None
            self._close_active_offer(connection, session["id"], state, "expired")
            state["pending_offer_publication"] = None
        self._persist_session(connection, session, state, context, initial_revision)
        if context.status != "active":
            self._generate_review(
                connection, self._session_row(connection, session["id"]), scenario, state
            )
        return ServiceResult(
            200,
            self._command_response(
                connection,
                session["id"],
                participant,
                scenario,
                state,
                context,
                result=result_name,
                extra={
                    "committed_actions": [
                        {
                            "participant_id": participant["id"],
                            "action": action,
                            "message": message,
                            "evidence_event_id": event_id,
                        }
                    ]
                },
            ),
        )

    def _commit_supply_npc(self, connection, session, npc, scenario, state, context, plan):
        action, terms = plan.action, dict(plan.request.approved_terms)
        active = state.get("active_offer")
        if action in {"publish", "accept"} and (
            not offer_is_bindable(scenario, terms)
            or not offer_is_acceptable(scenario, npc["role"], terms)
        ):
            raise ValueError("NPC attempted an invalid supply commitment")
        if action == "propose" and validate_supply_terms(scenario, terms, complete=False):
            raise ValueError("NPC attempted an invalid preliminary package")
        context.revision += 1
        context.substantive_turn_count += 1
        state["consecutive_protocol_controls"] = 0
        self._advance_round(state, npc["id"], context, scenario)
        context.next_participant_id = self._other_participant(connection, session["id"], npc["id"])[
            "id"
        ]
        if action == "propose":
            event_id = self._supply_commit_proposal(
                connection, session, npc, scenario, state, context, terms
            )
        elif action == "publish":
            event_id = self._supply_publish(connection, session, npc, state, context, terms)
        elif action == "accept":
            if (
                not active
                or active["proposer_participant_id"] == npc["id"]
                or active["terms"] != terms
            ):
                raise ValueError("NPC acceptance requires the current counterparty formal offer")
            self._set_offer_status(connection, session["id"], active, "accepted")
            state["agreement_offer"] = {**deepcopy(active), "status": "accepted"}
            state["active_offer"] = None
            state["preliminary_proposal"] = None
            state["pending_confirmation"] = None
            state["pending_offer_publication"] = None
            context.status, context.next_participant_id = "agreement_reached", None
            event_id = self._insert_event(
                connection,
                session["id"],
                context.revision,
                npc["id"],
                "agreement.reached",
                active,
                {},
            )
        else:
            if action == "reject" and active:
                self._set_offer_status(connection, session["id"], active, "rejected")
                state["active_offer"] = None
            event_id = self._insert_event(
                connection,
                session["id"],
                context.revision,
                npc["id"],
                f"participant.{action}",
                {"speech_act": plan.request.speech_act},
                {},
            )
        return {
            "participant_id": npc["id"],
            "action": action,
            "speech_act": plan.request.speech_act,
            "evidence_event_id": event_id,
        }
