from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from statistics import fmean
from typing import Any

from .conversation import (
    build_conversation_memory,
    detected_conditional_exchange,
    detected_term_signals,
    detected_topic_directive,
    mentioned_term_ids,
)
from .db import Database
from .dialogue import (
    MAX_CONTEXT_TURNS,
    OPENING_NAME_TOKEN,
    OPENING_POSITION_TOKEN,
    OPENING_TITLE_TOKEN,
    GroundedOpeningRequest,
    NpcDialogueRenderer,
    NpcDialogueRequest,
    NpcDialogueResult,
    NpcUtterancePlan,
    PublicDialogueTurn,
    TemplateNpcDialogueRenderer,
    bounded_dialogue_context,
    redact_untrusted_credentials,
    stable_render_id,
    template_dialogue_result,
    template_opening_result,
    utterance_plan_from_payload,
    utterance_plan_payload,
    validated_dialogue_result,
    validated_grounded_opening_result,
)
from .dialogue_contracts import PublicNumericReference
from .dialogue_quality import build_dialogue_quality
from .dialogue_redirect import select_varied_fallback, topic_return_options
from .engine import (
    ParseContext,
    ParsedAction,
    clarification_text,
    classify_npc_speech_act,
    format_terms,
    npc_message_options,
    offer_is_acceptable,
    offer_is_bindable,
    offer_is_complete,
    parse_message,
    participant_term_labels,
    requests_npc_public_position,
    role_label,
)
from .methodology import VERSION as METHODOLOGY_VERSION
from .models import (
    TERMINAL_STATUSES,
    CloseSessionRequest,
    CreateSessionRequest,
    HintRequest,
    SubmitMessageRequest,
)
from .negotiation_policy import select_counterproposal
from .reply_retrieval import retrieve_reply_examples
from .scenarios import (
    authored_opening,
    canonical_json,
    constraint_violations,
    digest,
    evaluate_utility,
    validate_terms,
)
from .supply import is_supply_scenario, supply_financial_summary
from .supply_extraction import VERSION as SUPPLY_EXTRACTOR_VERSION
from .supply_protocol import SupplyProtocolMixin, supply_current, supply_envelope
from .training import apply_social, initialize_training, npc_training_context, training_observation
from .training_service import TrainingServiceMixin

RELATIONSHIP_GREETING_VERSION = "relationship-greeting-v1"

SUCCESSFUL_HISTORY_GREETINGS = {
    "ru": (
        (
            "Добрый день. Рад снова быть с вами на связи. В этот раз предлагаю "
            "обсудить «{title}». С чего вам было бы удобно начать?"
        ),
        (
            "Здравствуйте. Приятно снова встретиться. Предлагаю перейти к теме "
            "«{title}». Что вы хотели бы обозначить вначале?"
        ),
        (
            "Рад снова вас приветствовать. У нас новая тема — «{title}». "
            "Как вы предлагаете начать разговор?"
        ),
        (
            "Добрый день. Рад продолжить наше сотрудничество. Теперь предлагаю "
            "обсудить «{title}». Я вас слушаю."
        ),
        (
            "Здравствуйте. Хорошо, что мы снова на связи. Давайте начнём с темы "
            "«{title}». Что для вас важно обсудить в первую очередь?"
        ),
        (
            "Рад снова вас видеть. Предлагаю вместе посмотреть на тему «{title}». "
            "С чего начнём?"
        ),
    ),
    "en": (
        (
            'Good to speak with you again. This time, I suggest we discuss "{title}". '
            "Where would you like to begin?"
        ),
        (
            'Hello again. It is good to meet you again. Let us turn to "{title}". '
            "What would you like to address first?"
        ),
        (
            'Good to see you again. We have a new topic: "{title}". '
            "How would you like to start?"
        ),
        (
            'Hello. I am glad to continue our work together. I suggest we discuss "{title}". '
            "Please go ahead."
        ),
        (
            'It is good to be in touch again. Let us start with "{title}". '
            "What is most important for you to address first?"
        ),
        (
            'Good to meet with you again. Let us look at "{title}" together. '
            "Where shall we begin?"
        ),
    ),
}


@dataclass(frozen=True, slots=True)
class ServiceResult:
    status_code: int
    payload: dict[str, Any]


@dataclass(slots=True)
class TransitionContext:
    revision: int
    round: int
    substantive_turn_count: int
    status: str
    next_participant_id: str | None


class AuthenticationError(PermissionError):
    pass


class MissingResourceError(LookupError):
    pass


class SessionLockPool:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def for_session(self, session_id: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(session_id, threading.RLock())


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return canonical_json(value)


def _loads(value: str) -> Any:
    return json.loads(value)


CONVERSATIONAL_SPEECH_ACTS = frozenset(
    {
        "qualitative_interest_answer",
        "greeting",
        "abusive_language_boundary",
        "general_answer",
        "acknowledge_information",
    }
)

_KEY_MOMENT_TITLES = {
    "ru": {
        "proposal.created": "Первоначальная позиция",
        "proposal.revised": "Изменение обсуждаемого пакета",
        "offer.created": "Первое предложение",
        "offer.countered": "Встречное предложение",
        "agreement.reached": "Соглашение",
        "session.walked_away": "Выход из переговоров",
        "session.expired": "Лимит раундов",
    },
    "en": {
        "proposal.created": "Opening position",
        "proposal.revised": "Preliminary package revision",
        "offer.created": "First offer",
        "offer.countered": "Counteroffer",
        "agreement.reached": "Agreement",
        "session.walked_away": "Walk-away",
        "session.expired": "Round limit",
    },
}


def _key_moment_summary(
    language: str,
    event_type: str,
    role: str | None,
    payload: dict[str, Any],
    scenario: dict[str, Any],
) -> str:
    terms = payload.get("terms") or {}
    package = format_terms(terms, scenario=scenario, language=language) if terms else ""
    if is_supply_scenario(scenario):
        package = package.rstrip(".")
    actor = (
        role_label(role, language)
        if role
        else ("Участник" if language == "ru" else "A participant")
    )
    labels = participant_term_labels(scenario, language)
    unresolved = [
        labels.get(term_id, term_id) for term_id in payload.get("unresolved_required_terms") or []
    ]
    if language == "ru":
        if event_type in {"proposal.created", "proposal.revised"}:
            summary = f"{actor} предложил для обсуждения: {package}."
        elif event_type == "offer.created":
            summary = f"{actor} сделал первое предложение: {package}."
        elif event_type == "offer.countered":
            summary = f"{actor} сделал встречное предложение: {package}."
        elif event_type == "agreement.reached":
            summary = f"Соглашение достигнуто: {package}."
        elif event_type == "session.walked_away":
            summary = f"{actor} прекратил переговоры."
        elif event_type == "session.expired":
            summary = "Лимит раундов исчерпан без соглашения."
        else:
            summary = f"Зафиксировано событие {event_type}."
        if unresolved:
            summary += f" Не согласовано: {', '.join(unresolved)}."
        return summary
    if event_type in {"proposal.created", "proposal.revised"}:
        summary = f"{actor} proposed for discussion: {package}."
    elif event_type == "offer.created":
        summary = f"{actor} made the first offer: {package}."
    elif event_type == "offer.countered":
        summary = f"{actor} countered: {package}."
    elif event_type == "agreement.reached":
        summary = f"Agreement reached: {package}."
    elif event_type == "session.walked_away":
        summary = f"{actor} walked away."
    elif event_type == "session.expired":
        summary = "The round limit expired without agreement."
    else:
        summary = f"The session recorded {event_type}."
    if unresolved:
        summary += f" Still open: {', '.join(unresolved)}."
    return summary


def _review_recommendations(
    language: str,
    *,
    status: str,
    skills: dict[str, float],
    agreement: bool,
    utility: float,
    reservation: float,
    walked_away_self: bool,
) -> list[dict[str, str]]:
    texts = {
        "ru": {
            "probing": "Задайте больше открытых вопросов об интересах партнёра до того, как менять цену.",
            "conditional_trading": "Связывайте уступки с встречными условиями: «готовы на X, если вы …».",
            "package_design": "Предлагайте полный пакет сразу: все условия вместе, а не по одному.",
            "clarity": "Формулируйте одно полное предложение в сообщении, без нескольких альтернатив.",
            "outcome_below_reservation": "Сделка ниже вашего порога приемлемости: сравнивайте пакет с альтернативой (BATNA) до принятия.",
            "outcome_expired": "Переговоры истекли по лимиту раундов: раньше переходите к полному пакету условий.",
            "outcome_walked_away": "Партнёр вышел из переговоров: проверяйте, остаётся ли ваше предложение в зоне возможного соглашения.",
        },
        "en": {
            "probing": "Ask more open questions about the counterpart's interests before moving on price.",
            "conditional_trading": "Tie each concession to a condition: 'we can do X if you …'.",
            "package_design": "Propose the complete package at once instead of one term at a time.",
            "clarity": "State one complete offer per message, without several alternatives.",
            "outcome_below_reservation": "The deal is below your reservation level: compare the package with your BATNA before accepting.",
            "outcome_expired": "The session expired on the round limit: move to a complete package earlier.",
            "outcome_walked_away": "The counterpart walked away: check whether your proposal stays inside the zone of possible agreement.",
        },
    }[language if language in {"ru", "en"} else "en"]
    recommendations: list[dict[str, str]] = []
    if agreement and utility < reservation:
        recommendations.append({"skill": "outcome", "text": texts["outcome_below_reservation"]})
    elif status == "expired":
        recommendations.append({"skill": "outcome", "text": texts["outcome_expired"]})
    elif status == "walked_away" and not walked_away_self:
        recommendations.append({"skill": "outcome", "text": texts["outcome_walked_away"]})
    thresholds = {
        "probing": 50.0,
        "conditional_trading": 50.0,
        "package_design": 100.0,
        "clarity": 100.0,
    }
    for skill, threshold in thresholds.items():
        if float(skills.get(skill, 0.0)) < threshold:
            recommendations.append({"skill": skill, "text": texts[skill]})
    return recommendations


def _event_id() -> str:
    return "evt_" + uuid.uuid4().hex


class NegotiationService(TrainingServiceMixin, SupplyProtocolMixin):
    MAX_HINTS_PER_PARTICIPANT = 3
    MIN_PUBLIC_STATS_GROUP_SIZE = 2

    def __init__(
        self,
        database: Database,
        *,
        dialogue_renderer: NpcDialogueRenderer | None = None,
        known_redaction_secrets: tuple[str, ...] = (),
        supply_extractor=None,
        social_provider=None,
        review_provider=None,
        player_assist_provider=None,
    ):
        self.database = database
        self.locks = SessionLockPool()
        self.dialogue_renderer = dialogue_renderer or TemplateNpcDialogueRenderer()
        self.supply_extractor = supply_extractor
        self.social_provider = social_provider
        self.review_provider = review_provider
        self.player_assist_provider = player_assist_provider
        self._known_redaction_secrets = tuple(secret for secret in known_redaction_secrets if secret)

    # Scenario reads -----------------------------------------------------

    def list_scenarios(self, language: str | None = None) -> list[dict[str, Any]]:
        with self.database.read_connection() as connection:
            if language is None:
                rows = connection.execute(
                    "SELECT current.public_json, current.source_json FROM scenario_versions AS current "
                    "JOIN ("
                    "SELECT scenario_id, MAX(version) AS version "
                    "FROM scenario_versions GROUP BY scenario_id"
                    ") AS latest "
                    "ON current.scenario_id = latest.scenario_id "
                    "AND current.version = latest.version "
                    "ORDER BY current.scenario_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT current.public_json, current.source_json FROM scenario_versions AS current "
                    "JOIN ("
                    "SELECT scenario_id, MAX(version) AS version "
                    "FROM scenario_versions GROUP BY scenario_id"
                    ") AS latest "
                    "ON current.scenario_id = latest.scenario_id "
                    "AND current.version = latest.version "
                    "WHERE current.language = ? ORDER BY current.scenario_id",
                    (language,),
                ).fetchall()
        return [self._scenario_training_metadata(row) for row in rows]

    @staticmethod
    def _scenario_training_metadata(row):
        public = _loads(row["public_json"])
        source = _loads(row["source_json"])
        labels = participant_term_labels(source, source["language"])
        public["training_terms"] = [{"term_id": key, "label": labels.get(key, key)}
            for key, definition in source["terms"]["definitions"].items()
            if definition.get("value_schema", {}).get("type") in {"number", "integer"}]
        return public

    def get_scenario(self, scenario_id: str, version: int | None = None) -> dict[str, Any]:
        with self.database.read_connection() as connection:
            if version is None:
                row = connection.execute(
                    "SELECT public_json, source_json FROM scenario_versions WHERE scenario_id = ? "
                    "ORDER BY version DESC LIMIT 1",
                    (scenario_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT public_json, source_json FROM scenario_versions "
                    "WHERE scenario_id = ? AND version = ?",
                    (scenario_id, version),
                ).fetchone()
        if row is None:
            raise MissingResourceError("Scenario version was not found")
        return self._scenario_training_metadata(row)

    # Session creation --------------------------------------------------

    def create_session(self, request: CreateSessionRequest) -> ServiceResult:
        lock = self.locks.for_session(f"create:{request.idempotency_key}")
        with lock:
            return self._create_session(request)

    def _create_session(self, request: CreateSessionRequest) -> ServiceResult:
        request_data = request.model_dump(mode="json")
        request_digest = digest(request_data)
        scope = "create_session"
        session_id = "sess_" + uuid.uuid4().hex[:24]
        prepared_opening: NpcDialogueResult | None = None

        # The provider call happens before the write transaction. The create lock
        # preserves idempotency for this process, and the write path checks it again.
        with self.database.read_connection() as connection:
            repeated = self._idempotency_result(
                connection, scope, request.idempotency_key, request_digest
            )
            if repeated is not None:
                return repeated
            scenario_row = connection.execute(
                "SELECT * FROM scenario_versions WHERE scenario_id = ? AND version = ?",
                (request.scenario_id, request.scenario_version),
            ).fetchone()
            if scenario_row is not None and request.language == scenario_row["language"]:
                scenario = _loads(scenario_row["source_json"])
                scenario_roles = list(scenario["roles"])
                requested_roles = [participant.role for participant in request.participants]
                if set(requested_roles) == set(scenario_roles):
                    spec_by_role = {item.role: item for item in request.participants}
                    human_roles = [
                        role for role in scenario_roles
                        if spec_by_role[role].controller == "human"
                    ]
                    npc_roles = [
                        role for role in scenario_roles
                        if spec_by_role[role].controller == "built_in_npc"
                    ]
                    opening_role, _opening_kind, opening_terms = authored_opening(scenario)
                    if (
                        str(request.run_mode) == "training"
                        and len(human_roles) == 1
                        and len(npc_roles) == 1
                        and npc_roles[0] == opening_role
                    ):
                        opening_request = self._grounded_opening_request(
                            scenario,
                            npc_roles[0],
                            opening_terms,
                            request.language,
                            request.training,
                        )
                        if opening_request is not None:
                            render_opening = getattr(self.dialogue_renderer, "render_opening", None)
                            if render_opening is None:
                                prepared_opening = template_opening_result(opening_request)
                            else:
                                from .llm_trace import trace_session

                                trace_token = trace_session.set(session_id)
                                try:
                                    try:
                                        prepared_opening = render_opening(opening_request)
                                    except Exception:
                                        prepared_opening = template_opening_result(
                                            opening_request,
                                            provider=getattr(self.dialogue_renderer, "provider", None),
                                            model=getattr(self.dialogue_renderer, "model", None),
                                            fallback_used=True,
                                            failure_reason="renderer_failure",
                                        )
                                finally:
                                    trace_session.reset(trace_token)
                            prepared_opening = validated_grounded_opening_result(
                                opening_request, prepared_opening
                            )
        with self.database.write_transaction() as connection:
            repeated = self._idempotency_result(
                connection, scope, request.idempotency_key, request_digest
            )
            if repeated is not None:
                return repeated

            scenario_row = connection.execute(
                "SELECT * FROM scenario_versions WHERE scenario_id = ? AND version = ?",
                (request.scenario_id, request.scenario_version),
            ).fetchone()
            if scenario_row is None:
                result = ServiceResult(
                    404,
                    {"error": "scenario_not_found", "message": "Scenario version was not found"},
                )
                self._save_idempotency(
                    connection, scope, request.idempotency_key, request_digest, result
                )
                return result

            scenario = _loads(scenario_row["source_json"])
            if request.language != scenario_row["language"]:
                result = ServiceResult(
                    422,
                    {
                        "error": "scenario_language_mismatch",
                        "message": "Session language must match the immutable scenario version",
                        "scenario_language": scenario_row["language"],
                    },
                )
                self._save_idempotency(
                    connection, scope, request.idempotency_key, request_digest, result
                )
                return result
            scenario_roles = list(scenario["roles"])
            requested_roles = [participant.role for participant in request.participants]
            if set(requested_roles) != set(scenario_roles):
                result = ServiceResult(
                    422,
                    {
                        "error": "participant_roles_invalid",
                        "message": "Participant roles must match the scenario roles",
                        "expected_roles": scenario_roles,
                    },
                )
                self._save_idempotency(
                    connection, scope, request.idempotency_key, request_digest, result
                )
                return result

            participant_records: list[dict[str, Any]] = []
            role_to_participant: dict[str, str] = {}
            credentials: list[dict[str, str]] = []
            spec_by_role = {item.role: item for item in request.participants}
            opening_role, opening_kind, opening_terms = authored_opening(scenario)
            next_role = next(role for role in scenario_roles if role != opening_role)
            human_roles = [
                role for role in scenario_roles if spec_by_role[role].controller == "human"
            ]
            npc_roles = [
                role for role in scenario_roles if spec_by_role[role].controller == "built_in_npc"
            ]
            human_npc_training = (
                str(request.run_mode) == "training"
                and len(scenario_roles) == 2
                and len(human_roles) == 1
                and len(npc_roles) == 1
            )
            if human_npc_training:
                next_role = human_roles[0]
            for role in scenario_roles:
                spec = spec_by_role[role]
                participant_id = f"participant_{session_id[5:]}_{role}"
                token: str | None = None
                token_hash: str | None = None
                if spec.controller != "built_in_npc":
                    token = "nt_" + secrets.token_urlsafe(32)
                    token_hash = _token_hash(token)
                    credentials.append(
                        {"participant_id": participant_id, "role": role, "token": token}
                    )
                provenance = {
                    "provider": spec.provider,
                    "model": spec.model,
                    "prompt_version": spec.prompt_version,
                }
                participant_records.append(
                    {
                        "id": participant_id,
                        "role": role,
                        "controller": str(spec.controller),
                        "token_hash": token_hash,
                        "provenance": provenance,
                    }
                )
                role_to_participant[role] = participant_id

            opening_participant = role_to_participant[opening_role]
            next_participant = role_to_participant[next_role]
            offer_id = "offer_" + uuid.uuid4().hex[:20]
            active_offer = {
                "offer_id": offer_id,
                "offer_revision": 1,
                "proposer_participant_id": opening_participant,
                "terms": opening_terms,
                "status": "active",
            }
            delivered_distractors: dict[str, list[str]] = {
                record["id"]: [] for record in participant_records
            }
            if str(request.difficulty) == "expert":
                for distractor in scenario.get("distractors", []):
                    audience = role_to_participant.get(distractor["audience_role"])
                    if audience is not None:
                        delivered_distractors[audience].append(distractor["id"])

            state = {
                "participant_order": [role_to_participant[role] for role in scenario_roles],
                "role_to_participant": role_to_participant,
                "opening_participant_id": opening_participant,
                "opening_kind": opening_kind,
                "opening_terms": opening_terms,
                "active_offer": active_offer,
                "pending_confirmation": None,
                "pending_clarification": None,
                "consecutive_clarifications": 0,
                "consecutive_protocol_controls": 0,
                "agreement_offer": None,
                "round_actor_ids": [],
                "completed_rounds": 0,
                "delivered_distractors": delivered_distractors,
            }
            if request.training is not None:
                try:
                    state["training"] = initialize_training(
                        request.training, role_to_participant[human_roles[0]], scenario,
                        lambda text: redact_untrusted_credentials(text, *self._known_redaction_secrets),
                    )
                except ValueError as exc:
                    return ServiceResult(422, {"error": "invalid_training_target", "message": str(exc)})
            if is_supply_scenario(scenario):
                self._supply_initialize(state, opening_participant, opening_role, opening_terms)
            run_metadata = {
                "benchmark_run_id": request.benchmark_run_id,
                "trial_id": request.trial_id,
                "benchmark_expected_trials": request.benchmark_expected_trials,
                "seed": request.seed,
            }
            connection.execute(
                """
                INSERT INTO sessions(
                    id, scenario_id, scenario_version, scenario_content_digest,
                    scenario_compiler_version, compiled_scenario_digest, status,
                    revision, round, substantive_turn_count, next_participant_id,
                    difficulty, language, run_mode, hints_enabled, run_metadata_json,
                    state_json
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', 0, 1, 0, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    request.scenario_id,
                    request.scenario_version,
                    scenario_row["content_digest"],
                    scenario_row["compiler_version"],
                    scenario_row["compiled_digest"],
                    next_participant,
                    str(request.difficulty),
                    request.language,
                    str(request.run_mode),
                    int(request.hints_enabled),
                    _json(run_metadata),
                    _json(state),
                ),
            )
            for record in participant_records:
                connection.execute(
                    """
                    INSERT INTO participants(
                        id, session_id, role, controller, token_hash, provenance_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        session_id,
                        record["role"],
                        record["controller"],
                        record["token_hash"],
                        _json(record["provenance"]),
                    ),
                )
            if not is_supply_scenario(scenario):
                connection.execute(
                    "INSERT INTO offers(session_id, offer_id, offer_revision, proposer_participant_id, "
                    "terms_json, status, created_session_revision) VALUES (?, ?, 1, ?, ?, 'active', 0)",
                    (session_id, offer_id, opening_participant, _json(opening_terms)),
                )
            self._insert_event(
                connection,
                session_id,
                0,
                None,
                "session.created",
                {"status": "active", "next_actor": next_participant},
                {"run_metadata": run_metadata},
            )
            self._insert_event(
                connection,
                session_id,
                0,
                opening_participant,
                "proposal.created" if is_supply_scenario(scenario) else "offer.created",
                {
                    **({"proposal_id": state["preliminary_proposal"]["proposal_id"],
                        "proposal_revision": 1, "source_revision": 0} if is_supply_scenario(scenario) else {}),
                    "offer_id": offer_id,
                    "offer_revision": 1,
                    "terms": opening_terms,
                    "unresolved_required_terms": [
                        term
                        for term in scenario["terms"]["required_term_ids"]
                        if term not in opening_terms
                    ],
                },
                {},
            )
            if is_supply_scenario(scenario):
                event = connection.execute("SELECT event_id FROM events WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
                state["preliminary_proposal"]["source_event_ids"] = [event["event_id"]]
                connection.execute("UPDATE sessions SET state_json = ? WHERE id = ?", (_json(state), session_id))
            if str(request.difficulty) == "expert":
                for distractor in scenario.get("distractors", []):
                    audience = role_to_participant.get(distractor["audience_role"])
                    if audience is None:
                        continue
                    self._insert_event(
                        connection,
                        session_id,
                        0,
                        None,
                        "distractor.delivered",
                        {
                            "audience_participant_id": audience,
                            "distractor_id": distractor["id"],
                            "content": distractor["content"],
                        },
                        {"truth_note": distractor["truth_note"]},
                    )

            session_row = self._session_row(connection, session_id)
            next_actor_row = self._participant_row(connection, next_participant)
            initial_actions: list[dict[str, Any]] = []
            opening_actor_row = self._participant_row(connection, opening_participant)
            if human_npc_training:
                npc_row = self._participant_row(connection, role_to_participant[npc_roles[0]])
                relationship = str(
                    state.get("training", {})
                    .get("setup", {})
                    .get("relationship", "first_meeting")
                )
                if prepared_opening is not None:
                    greeting = prepared_opening.text
                    greeting_speech_act = "grounded_opening"
                    greeting_renderer = prepared_opening.public_metadata()
                else:
                    greeting = self._initial_npc_greeting(
                        scenario["title"],
                        request.language,
                        session_id=session_id,
                        relationship=relationship,
                    )
                    greeting_speech_act = "greeting"
                    greeting_renderer = None
                self._insert_message(
                    connection, session_id, 0, npc_row, greeting, request.language
                )
                self._insert_event(
                    connection,
                    session_id,
                    0,
                    npc_row["id"],
                    "npc.greeting.delivered",
                    {
                        "speech_act": greeting_speech_act,
                        "substantive": False,
                        **(
                            {"dialogue_renderer": greeting_renderer}
                            if greeting_renderer is not None
                            else {}
                        ),
                    },
                    {},
                )
            if (
                str(request.difficulty) == "easy"
                and str(request.run_mode) == "training"
                and opening_actor_row["controller"] == "built_in_npc"
                and next_actor_row["controller"] == "external_agent"
            ):
                opening_request = self._build_dialogue_request(
                    connection,
                    session_row,
                    opening_actor_row,
                    scenario,
                    speech_act=opening_kind,
                    terms=opening_terms,
                    player_message="",
                )
                rendered = template_dialogue_result(
                    opening_request,
                    provider=getattr(self.dialogue_renderer, "provider", None),
                    model=getattr(self.dialogue_renderer, "model", None),
                )
                rendered = self._safe_renderer_delivery(opening_request, rendered)
                self._insert_message(
                    connection,
                    session_id,
                    0,
                    opening_actor_row,
                    rendered.text,
                    request.language,
                )
                self._insert_event(
                    connection,
                    session_id,
                    0,
                    opening_actor_row["id"],
                    "npc.opening_utterance.delivered",
                    {
                        "speech_act": opening_kind,
                        "opening_kind": opening_kind,
                        "substantive": False,
                        "offer_id": offer_id,
                        "offer_revision": 1,
                        "dialogue_renderer": rendered.public_metadata(),
                    },
                    {},
                )
            if next_actor_row["controller"] == "built_in_npc":
                action, speech_act, terms = self._npc_decision(
                    scenario,
                    state,
                    next_actor_row,
                    "",
                    "counter_offer",
                )
                plan = self._build_utterance_plan(
                    connection,
                    session_row,
                    next_actor_row,
                    scenario,
                    intent_revision=1,
                    action=action,
                    speech_act=speech_act,
                    terms=terms,
                    player_message="",
                )
                context = TransitionContext(
                    revision=0,
                    round=1,
                    substantive_turn_count=0,
                    status="active",
                    next_participant_id=next_participant,
                )
                npc_action = self._commit_npc_authoritative_action(
                    connection,
                    session_row,
                    next_actor_row,
                    scenario,
                    state,
                    context,
                    plan,
                )
                self._insert_event(
                    connection,
                    session_id,
                    context.revision,
                    next_actor_row["id"],
                    "npc.intent.committed",
                    {
                        "render_id": plan.render_id,
                        "action": plan.action,
                        "speech_act": plan.request.speech_act,
                        "approved_terms": dict(plan.request.approved_terms),
                    },
                    {},
                )
                rendered = template_dialogue_result(
                    plan.request,
                    provider=getattr(self.dialogue_renderer, "provider", None),
                    model=getattr(self.dialogue_renderer, "model", None),
                )
                rendered = self._safe_renderer_delivery(plan.request, rendered)
                self._insert_message(
                    connection,
                    session_id,
                    context.revision,
                    next_actor_row,
                    rendered.text,
                    request.language,
                )
                renderer_metadata = rendered.public_metadata()
                self._insert_event(
                    connection,
                    session_id,
                    context.revision,
                    next_actor_row["id"],
                    "npc.utterance.delivered",
                    {
                        "render_id": plan.render_id,
                        "speech_act": plan.request.speech_act,
                        "dialogue_renderer": renderer_metadata,
                        "requested_term_id": plan.request.requested_term_id,
                    },
                    {},
                )
                npc_action["message"] = rendered.text
                npc_action["dialogue_renderer"] = renderer_metadata
                initial_actions.append(npc_action)
                self._persist_session(connection, session_row, state, context, 0)
                session_row = self._session_row(connection, session_id)
                if context.status in TERMINAL_STATUSES:
                    self._generate_review(connection, session_row, scenario, state)

            observer_record = next(
                record for record in participant_records if record["controller"] != "built_in_npc"
            )
            observer_row = self._participant_row(connection, observer_record["id"])
            self._capture_training_checkpoint(connection, session_row, state)
            response = {
                "session_id": session_id,
                "revision": session_row["revision"],
                "scenario_version": request.scenario_version,
                "scenario_content_digest": scenario_row["content_digest"],
                "scenario_compiler_version": scenario_row["compiler_version"],
                "compiled_scenario_digest": scenario_row["compiled_digest"],
                "status": session_row["status"],
                "round": session_row["round"],
                "substantive_turn_count": session_row["substantive_turn_count"],
                "next_actor": session_row["next_participant_id"],
                "language": request.language,
                "participants": [
                    {
                        "participant_id": record["id"],
                        "role": record["role"],
                        "controller": record["controller"],
                    }
                    for record in participant_records
                ],
                "participant_credentials": credentials,
                "participant_token": credentials[0]["token"] if len(credentials) == 1 else None,
                "run_metadata": run_metadata,
                "committed_actions": initial_actions,
                **supply_envelope(scenario, state, observer_row["id"]),
                "observation": self._observation(
                    connection, session_row, observer_row, scenario, state
                ),
            }
            result = ServiceResult(201, response)
            self._save_idempotency(
                connection,
                scope,
                request.idempotency_key,
                request_digest,
                result,
                contains_credentials=True,
            )
            return result

    # Authenticated reads ----------------------------------------------

    def get_session(self, session_id: str, token: str) -> dict[str, Any]:
        with self.database.read_connection() as connection:
            session, participant = self._authenticated_rows(connection, session_id, token)
            scenario = self._scenario_source(connection, session)
            state = _loads(session["state_json"])
            pending = state.get("pending_confirmation") or {}
            pending_confirmation = None
            if pending.get("participant_id") == participant["id"]:
                pending_confirmation = {
                    "offer_id": pending["offer_id"],
                    "offer_revision": pending["offer_revision"],
                    "terms": pending["terms"],
                    "unresolved_required_terms": [],
                }
            pending_clarification = state.get("pending_clarification") or {}
            clarification = None
            if pending_clarification.get("participant_id") == participant["id"]:
                details = {
                    key: value
                    for key, value in pending_clarification.items()
                    if key != "participant_id"
                }
                clarification = {
                    **details,
                    "question": details.get("question") or clarification_text(
                        str(session["language"]),
                        str(details.get("reason_code", "ambiguous_message")),
                        expected_currency=details.get("expected_currency"),
                    ),
                }
            return {
                "session_id": session_id,
                "scenario_id": session["scenario_id"],
                "scenario_version": session["scenario_version"],
                "status": session["status"],
                "revision": session["revision"],
                "round": session["round"],
                "substantive_turn_count": session["substantive_turn_count"],
                "next_actor": session["next_participant_id"],
                "language": session["language"],
                "difficulty": session["difficulty"],
                "run_mode": session["run_mode"],
                "hints_enabled": bool(session["hints_enabled"]),
                "pending_confirmation": pending_confirmation,
                "clarification": clarification,
                **supply_envelope(scenario, state, participant["id"]),
                "observation": self._observation(connection, session, participant, scenario, state),
            }

    def get_observation(self, session_id: str, token: str) -> dict[str, Any]:
        with self.database.read_connection() as connection:
            session, participant = self._authenticated_rows(connection, session_id, token)
            scenario = self._scenario_source(connection, session)
            return self._observation(
                connection,
                session,
                participant,
                scenario,
                _loads(session["state_json"]),
            )

    def get_messages(self, session_id: str, token: str) -> dict[str, Any]:
        with self.database.read_connection() as connection:
            session, _participant = self._authenticated_rows(connection, session_id, token)
            rows = connection.execute(
                "SELECT session_revision, participant_id, role, content, language, created_at "
                "FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            return {
                "session_id": session_id,
                "revision": session["revision"],
                "messages": [dict(row) for row in rows],
            }

    def get_events(self, session_id: str, token: str) -> dict[str, Any]:
        with self.database.read_connection() as connection:
            session, participant = self._authenticated_rows(connection, session_id, token)
            rows = connection.execute(
                "SELECT event_id, session_revision, participant_id, type, "
                "public_payload_json, created_at FROM events "
                "WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            events: list[dict[str, Any]] = []
            for row in rows:
                payload = _loads(row["public_payload_json"])
                audience = payload.get("audience_participant_id")
                if audience is not None and audience != participant["id"]:
                    continue
                events.append(
                    {
                        "event_id": row["event_id"],
                        "session_revision": row["session_revision"],
                        "participant_id": row["participant_id"],
                        "type": row["type"],
                        "payload": payload,
                        "created_at": row["created_at"],
                    }
                )
            return {"session_id": session_id, "revision": session["revision"], "events": events}

    def get_history(self, session_id: str, token: str) -> dict[str, Any]:
        with self.database.read_connection() as connection:
            session, participant = self._authenticated_rows(connection, session_id, token)
            message_rows = connection.execute(
                "SELECT session_revision, participant_id, role, content, language, created_at "
                "FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            event_rows = connection.execute(
                "SELECT event_id, session_revision, participant_id, type, "
                "public_payload_json, created_at FROM events "
                "WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            events: list[dict[str, Any]] = []
            for row in event_rows:
                payload = _loads(row["public_payload_json"])
                audience = payload.get("audience_participant_id")
                if audience is not None and audience != participant["id"]:
                    continue
                events.append(
                    {
                        "event_id": row["event_id"],
                        "session_revision": row["session_revision"],
                        "participant_id": row["participant_id"],
                        "type": row["type"],
                        "payload": payload,
                        "created_at": row["created_at"],
                    }
                )
            return {
                "session_id": session_id,
                "revision": session["revision"],
                "messages": [dict(row) for row in message_rows],
                "events": events,
            }

    # Administrative reads --------------------------------------------

    def list_admin_sessions(
        self,
        *,
        status: str | None = None,
        scenario_id: str | None = None,
        language: str | None = None,
        run_mode: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        conditions: list[str] = []
        parameters: list[Any] = []
        for column, value in (
            ("session.status", status),
            ("session.scenario_id", scenario_id),
            ("session.language", language),
            ("session.run_mode", run_mode),
        ):
            if value is not None:
                conditions.append(f"{column} = ?")
                parameters.append(value)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self.database.read_connection() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) AS count FROM sessions AS session {where}",
                    parameters,
                ).fetchone()["count"]
            )
            session_rows = connection.execute(
                f"""
                SELECT
                    session.id,
                    session.scenario_id,
                    session.scenario_version,
                    scenario.title AS scenario_title,
                    json_extract(scenario.public_json, '$.currency') AS currency,
                    session.status,
                    session.revision,
                    session.round,
                    session.substantive_turn_count,
                    session.next_participant_id,
                    session.difficulty,
                    session.language,
                    session.run_mode,
                    session.hints_enabled,
                    session.run_metadata_json,
                    session.created_at,
                    session.updated_at,
                    (SELECT COUNT(*) FROM messages
                        WHERE messages.session_id = session.id) AS message_count,
                    (SELECT COUNT(*) FROM events
                        WHERE events.session_id = session.id) AS event_count,
                    (SELECT COUNT(*) FROM offers
                        WHERE offers.session_id = session.id) AS offer_revision_count
                FROM sessions AS session
                JOIN scenario_versions AS scenario
                  ON scenario.scenario_id = session.scenario_id
                 AND scenario.version = session.scenario_version
                {where}
                ORDER BY session.created_at DESC, session.id DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()
            session_ids = [row["id"] for row in session_rows]
            participant_rows: list[sqlite3.Row] = []
            review_session_ids: set[str] = set()
            if session_ids:
                placeholders = ",".join("?" for _ in session_ids)
                participant_rows = list(
                    connection.execute(
                        "SELECT id, session_id, role, controller, provenance_json "
                        f"FROM participants WHERE session_id IN ({placeholders}) "
                        "ORDER BY session_id, created_at, id",
                        session_ids,
                    ).fetchall()
                )
                review_session_ids = {
                    row["session_id"]
                    for row in connection.execute(
                        f"SELECT session_id FROM reviews WHERE session_id IN ({placeholders})",
                        session_ids,
                    ).fetchall()
                }
            run_sessions = list(
                connection.execute(
                    "SELECT id, status, run_mode, run_metadata_json FROM sessions"
                ).fetchall()
            )

        participants_by_session: dict[str, list[dict[str, Any]]] = {}
        for row in participant_rows:
            participants_by_session.setdefault(row["session_id"], []).append(
                self._admin_participant(row)
            )
        items = []
        for row in session_rows:
            review_state, _release = self._admin_review_state(
                row,
                run_sessions,
                row["id"] in review_session_ids,
            )
            items.append(
                self._admin_session_summary(
                    row,
                    participants_by_session.get(row["id"], []),
                    review_state,
                )
            )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def get_admin_session(self, session_id: str) -> dict[str, Any]:
        with self.database.read_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    session.id,
                    session.scenario_id,
                    session.scenario_version,
                    scenario.title AS scenario_title,
                    json_extract(scenario.public_json, '$.currency') AS currency,
                    session.status,
                    session.revision,
                    session.round,
                    session.substantive_turn_count,
                    session.next_participant_id,
                    session.difficulty,
                    session.language,
                    session.run_mode,
                    session.hints_enabled,
                    session.run_metadata_json,
                    session.created_at,
                    session.updated_at,
                    (SELECT COUNT(*) FROM messages
                        WHERE messages.session_id = session.id) AS message_count,
                    (SELECT COUNT(*) FROM events
                        WHERE events.session_id = session.id) AS event_count,
                    (SELECT COUNT(*) FROM offers
                        WHERE offers.session_id = session.id) AS offer_revision_count
                FROM sessions AS session
                JOIN scenario_versions AS scenario
                  ON scenario.scenario_id = session.scenario_id
                 AND scenario.version = session.scenario_version
                WHERE session.id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                raise MissingResourceError("Session was not found")

            participant_rows = connection.execute(
                "SELECT id, session_id, role, controller, provenance_json "
                "FROM participants WHERE session_id = ? ORDER BY created_at, id",
                (session_id,),
            ).fetchall()
            message_rows = connection.execute(
                "SELECT session_revision, participant_id, role, content, language, created_at "
                "FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            event_rows = connection.execute(
                "SELECT event_id, session_revision, participant_id, type, "
                "public_payload_json, created_at FROM events "
                "WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            offer_rows = connection.execute(
                "SELECT offer_id, offer_revision, proposer_participant_id, terms_json, "
                "status, created_session_revision FROM offers "
                "WHERE session_id = ? ORDER BY created_session_revision, offer_id, offer_revision",
                (session_id,),
            ).fetchall()
            review_row = connection.execute(
                "SELECT public_json FROM reviews WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            run_sessions = list(
                connection.execute(
                    "SELECT id, status, run_mode, run_metadata_json FROM sessions"
                ).fetchall()
            )

        participants = [self._admin_participant(item) for item in participant_rows]
        review_state, release = self._admin_review_state(
            row,
            run_sessions,
            review_row is not None,
        )
        response = self._admin_session_summary(row, participants, review_state)
        response.update(
            messages=[dict(item) for item in message_rows],
            events=[
                {
                    "event_id": item["event_id"],
                    "session_revision": item["session_revision"],
                    "participant_id": item["participant_id"],
                    "type": item["type"],
                    "payload": _loads(item["public_payload_json"]),
                    "created_at": item["created_at"],
                }
                for item in event_rows
            ],
            offers=[
                {
                    "offer_id": item["offer_id"],
                    "offer_revision": item["offer_revision"],
                    "proposer_participant_id": item["proposer_participant_id"],
                    "terms": _loads(item["terms_json"]),
                    "status": item["status"],
                    "created_session_revision": item["created_session_revision"],
                }
                for item in offer_rows
            ],
            review=_loads(review_row["public_json"])
            if review_state == "available" and review_row is not None
            else None,
            benchmark_run=release,
        )
        response["dialogue_quality"] = build_dialogue_quality(
            response["messages"], response["events"],
            npc_participant_ids=[item["participant_id"] for item in participants if item["controller"] == "built_in_npc"],
        )
        return response

    @staticmethod
    def _admin_participant(row: sqlite3.Row) -> dict[str, Any]:
        provenance = _loads(row["provenance_json"])
        return {
            "participant_id": row["id"],
            "role": row["role"],
            "controller": row["controller"],
            "provider": provenance.get("provider"),
            "model": provenance.get("model"),
            "prompt_version": provenance.get("prompt_version"),
        }

    @staticmethod
    def _admin_run_metadata(value: str) -> dict[str, Any]:
        source = _loads(value)
        return {
            key: source[key]
            for key in (
                "benchmark_run_id",
                "trial_id",
                "benchmark_expected_trials",
                "seed",
            )
            if source.get(key) is not None
        }

    def _admin_session_summary(
        self,
        row: sqlite3.Row,
        participants: list[dict[str, Any]],
        review_state: str,
    ) -> dict[str, Any]:
        return {
            "session_id": row["id"],
            "scenario_id": row["scenario_id"],
            "scenario_version": row["scenario_version"],
            "scenario_title": row["scenario_title"],
            "currency": row["currency"],
            "status": row["status"],
            "revision": row["revision"],
            "round": row["round"],
            "substantive_turn_count": row["substantive_turn_count"],
            "next_actor": row["next_participant_id"],
            "difficulty": row["difficulty"],
            "language": row["language"],
            "run_mode": row["run_mode"],
            "hints_enabled": bool(row["hints_enabled"]),
            "run_metadata": self._admin_run_metadata(row["run_metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": row["message_count"],
            "event_count": row["event_count"],
            "offer_revision_count": row["offer_revision_count"],
            "participants": participants,
            "review_state": review_state,
        }

    def _admin_review_state(
        self,
        session: sqlite3.Row,
        run_sessions: list[sqlite3.Row],
        review_exists: bool,
    ) -> tuple[str, dict[str, Any] | None]:
        if session["status"] not in TERMINAL_STATUSES:
            return "not_ready", None
        release: dict[str, Any] | None = None
        if session["run_mode"] == "benchmark":
            release = self._benchmark_release_state(
                run_sessions,
                _loads(session["run_metadata_json"]),
            )
            if not release["release_ready"]:
                return "sealed", release
        return ("available" if review_exists else "not_ready"), release

    # Message command ---------------------------------------------------

    def submit_message(
        self, session_id: str, token: str, request: SubmitMessageRequest
    ) -> ServiceResult:
        lock = self.locks.for_session(session_id)
        with lock:
            request_digest = digest(request.model_dump(mode="json"))
            # Optional semantic normalization runs outside a SQLite write transaction.
            # The transaction below rechecks authentication, revision, turn, and idempotency.
            extracted = self._supply_preextract(session_id, token, request, request_digest)
            social_events = self._training_preclassify(session_id, token, request, request_digest)
            pending_payload: dict[str, Any] | None = None
            scope = ""
            with self.database.write_transaction() as connection:
                session, participant = self._authenticated_rows(connection, session_id, token)
                scope = f"message:{session_id}:{participant['id']}"
                repeated = self._idempotency_result(
                    connection, scope, request.idempotency_key, request_digest
                )
                if repeated is not None:
                    if repeated.payload.get("_internal_result") != "npc_render_pending":
                        return repeated
                    pending_payload = repeated.payload
                else:
                    pending_render = self._pending_render_result(
                        connection, session_id, int(session["revision"])
                    )
                    if pending_render is not None:
                        return pending_render
                    initial_revision = int(session["revision"])
                    if request.expected_revision != initial_revision:
                        result = ServiceResult(
                            409,
                            {
                                "error": "revision_conflict",
                                "message": "expected_revision does not match the session revision",
                                "revision": initial_revision,
                            },
                        )
                        self._save_idempotency(
                            connection,
                            scope,
                            request.idempotency_key,
                            request_digest,
                            result,
                        )
                        return result
                    if session["status"] in TERMINAL_STATUSES:
                        result = ServiceResult(
                            409,
                            {
                                "error": "session_terminal",
                                "message": "A terminal session cannot accept messages",
                                "revision": initial_revision,
                            },
                        )
                        self._save_idempotency(
                            connection,
                            scope,
                            request.idempotency_key,
                            request_digest,
                            result,
                        )
                        return result
                    if session["next_participant_id"] != participant["id"]:
                        result = ServiceResult(
                            409,
                            {
                                "error": "not_your_turn",
                                "message": "The authenticated participant is not next_actor",
                                "revision": initial_revision,
                                "next_actor": session["next_participant_id"],
                            },
                        )
                        self._save_idempotency(
                            connection,
                            scope,
                            request.idempotency_key,
                            request_digest,
                            result,
                        )
                        return result

                    scenario = self._scenario_source(connection, session)
                    state = _loads(session["state_json"])
                    self._capture_training_checkpoint(connection, session, state)
                    pending = state.get("pending_confirmation")
                    safe_message = redact_untrusted_credentials(
                        request.message, token, *self._known_redaction_secrets
                    )
                    parsed = self._supply_parse(safe_message, session, participant, state) if is_supply_scenario(scenario) else parse_message(
                        safe_message,
                        scenario["terms"]["definitions"],
                        pending_confirmation=bool(
                            pending and pending.get("participant_id") == participant["id"]
                        ),
                        scenario_currency=scenario["currency"],
                        context=self._parse_context(connection, session, participant, scenario, state),
                    )
                    if extracted is not None:
                        parsed = extracted
                    result = self._apply_participant_action(
                        connection,
                        session,
                        participant,
                        scenario,
                        state,
                        safe_message,
                        parsed,
                        initial_revision,
                        defer_builtin_npc=True,
                    )
                    current = self._session_row(connection, session_id)
                    if int(current["revision"]) > initial_revision and state.get("training"):
                        committed_state = _loads(current["state_json"])
                        changes = apply_social(committed_state["training"], initial_revision + 1, social_events)
                        if changes:
                            self._insert_event(connection, session_id, initial_revision + 1, participant["id"],
                                "training.social.updated", {}, {"changes": changes, "source_revision": initial_revision + 1})
                        connection.execute("UPDATE sessions SET state_json = ? WHERE id = ?",
                                           (_json(committed_state), session_id))
                    if extracted is not None and int(current["revision"]) > initial_revision:
                        self._insert_event(connection, session_id, int(current["revision"]), participant["id"],
                            "message.extracted", {"extractor_version": SUPPLY_EXTRACTOR_VERSION,
                            "source_revision": initial_revision, "action": parsed.action,
                            "validation_category": parsed.clarification_code or "validated"}, {})
                    next_participant_id = current["next_participant_id"]
                    next_is_npc = False
                    if current["status"] == "active" and next_participant_id is not None:
                        next_participant = self._participant_row(
                            connection, str(next_participant_id)
                        )
                        next_is_npc = next_participant["controller"] == "built_in_npc"
                    if result.status_code != 200 or not next_is_npc:
                        self._save_idempotency(
                            connection,
                            scope,
                            request.idempotency_key,
                            request_digest,
                            result,
                        )
                        return result
                    pending_payload = {
                        "_internal_result": "npc_render_pending",
                        "session_id": session_id,
                        "participant_revision": int(current["revision"]),
                        "response_participant_id": participant["id"],
                        "player_action": parsed.action,
                        "prior_actions": result.payload.get("committed_actions", []),
                    }
                    self._save_idempotency(
                        connection,
                        scope,
                        request.idempotency_key,
                        request_digest,
                        ServiceResult(202, pending_payload),
                    )

            assert pending_payload is not None
            plan = self._ensure_npc_intent(
                session_id=session_id,
                command_scope=scope,
                idempotency_key=request.idempotency_key,
                request_digest=request_digest,
                pending_payload=pending_payload,
            )
            unclaimed_result = self._claim_npc_render(plan)
            if unclaimed_result is not None:
                return unclaimed_result
            rendered = self._render_npc_plan(plan)
            return self._deliver_npc_render(plan, rendered)

    def request_hint(self, session_id: str, token: str, request: HintRequest) -> ServiceResult:
        lock = self.locks.for_session(session_id)
        with lock, self.database.write_transaction() as connection:
            session, participant = self._authenticated_rows(connection, session_id, token)
            request_digest = digest(request.model_dump(mode="json"))
            scope = f"hint:{session_id}:{participant['id']}"
            repeated = self._idempotency_result(
                connection, scope, request.idempotency_key, request_digest
            )
            if repeated is not None:
                return repeated
            current_revision = int(session["revision"])
            pending_render = self._pending_render_result(connection, session_id, current_revision)
            if pending_render is not None:
                return pending_render
            if request.expected_revision != current_revision:
                result = ServiceResult(
                    409,
                    {
                        "error": "revision_conflict",
                        "message": "expected_revision does not match the session revision",
                        "revision": current_revision,
                    },
                )
                self._save_idempotency(
                    connection, scope, request.idempotency_key, request_digest, result
                )
                return result
            if (
                session["status"] != "active"
                or not bool(session["hints_enabled"])
                or session["run_mode"] == "benchmark"
            ):
                result = ServiceResult(
                    409,
                    {
                        "error": "hints_not_available",
                        "message": "Hints are disabled for this session",
                        "revision": current_revision,
                    },
                )
                self._save_idempotency(
                    connection, scope, request.idempotency_key, request_digest, result
                )
                return result
            if session["next_participant_id"] != participant["id"]:
                result = ServiceResult(
                    409,
                    {
                        "error": "not_your_turn",
                        "message": "Hints are available only to next_actor",
                        "revision": current_revision,
                    },
                )
                self._save_idempotency(
                    connection, scope, request.idempotency_key, request_digest, result
                )
                return result

            delivered = connection.execute(
                "SELECT COUNT(*) FROM events WHERE session_id = ? AND type = 'hint.delivered' "
                "AND json_extract(public_payload_json, '$.audience_participant_id') = ?",
                (session_id, participant["id"]),
            ).fetchone()[0]
            if int(delivered) >= self.MAX_HINTS_PER_PARTICIPANT:
                result = ServiceResult(
                    409,
                    {
                        "error": "hints_exhausted",
                        "message": "The participant hint budget is exhausted",
                        "revision": current_revision,
                    },
                )
                self._save_idempotency(
                    connection, scope, request.idempotency_key, request_digest, result
                )
                return result
            level = min(int(delivered) + 1, 3)
            language = session["language"]
            texts = {
                "ru": {
                    1: "Обратите внимание, к каким условиям собеседник возвращается чаще всего.",
                    2: "Проверьте вопросом, какое условие имеет для собеседника наибольшую ценность.",
                    3: "Сформулируйте условный обмен: ваша уступка только в обмен на встречное условие.",
                },
                "en": {
                    1: "Notice which terms the counterparty returns to most often.",
                    2: "Ask which term creates the most value for the counterparty.",
                    3: "Make a conditional trade: give your concession only for a return condition.",
                },
            }
            hint = {
                "id": f"hint_{level}_{delivered + 1}",
                "level": level,
                "text": texts[language][level],
            }
            context = TransitionContext(
                revision=current_revision + 1,
                round=int(session["round"]),
                substantive_turn_count=int(session["substantive_turn_count"]),
                status=session["status"],
                next_participant_id=session["next_participant_id"],
            )
            state = _loads(session["state_json"])
            event_id = self._insert_event(
                connection,
                session_id,
                context.revision,
                None,
                "hint.delivered",
                {"audience_participant_id": participant["id"], **hint},
                {},
            )
            hint["event_id"] = event_id
            self._persist_session(connection, session, state, context, current_revision)
            current = self._session_row(connection, session_id)
            scenario = self._scenario_source(connection, current)
            result = ServiceResult(
                200,
                {
                    "session_id": session_id,
                    "revision": context.revision,
                    "hint": hint,
                    "observation": self._observation(
                        connection, current, participant, scenario, state
                    ),
                },
            )
            self._save_idempotency(
                connection, scope, request.idempotency_key, request_digest, result
            )
            return result

    def close_session(self, session_id: str, request: CloseSessionRequest) -> ServiceResult:
        lock = self.locks.for_session(session_id)
        with lock, self.database.write_transaction() as connection:
            session = self._session_row(connection, session_id)
            request_digest = digest(request.model_dump(mode="json"))
            scope = f"admin-close:{session_id}"
            repeated = self._idempotency_result(
                connection, scope, request.idempotency_key, request_digest
            )
            if repeated is not None:
                return repeated
            current_revision = int(session["revision"])
            pending_render = self._pending_render_result(connection, session_id, current_revision)
            if pending_render is not None:
                return pending_render
            if request.expected_revision != current_revision:
                result = ServiceResult(
                    409,
                    {
                        "error": "revision_conflict",
                        "message": "expected_revision does not match the session revision",
                        "revision": current_revision,
                    },
                )
                self._save_idempotency(
                    connection, scope, request.idempotency_key, request_digest, result
                )
                return result
            if session["status"] in TERMINAL_STATUSES:
                result = ServiceResult(
                    409,
                    {
                        "error": "session_terminal",
                        "message": "A terminal session cannot be closed again",
                        "revision": current_revision,
                    },
                )
                self._save_idempotency(
                    connection, scope, request.idempotency_key, request_digest, result
                )
                return result
            state = _loads(session["state_json"])
            scenario = self._scenario_source(connection, session)
            context = TransitionContext(
                revision=current_revision + 1,
                round=int(session["round"]),
                substantive_turn_count=int(session["substantive_turn_count"]),
                status="aborted",
                next_participant_id=None,
            )
            self._close_active_offer(connection, session_id, state, "closed_by_termination")
            state["pending_confirmation"] = None
            state["pending_clarification"] = None
            self._insert_event(
                connection,
                session_id,
                context.revision,
                None,
                "session.aborted",
                {"reason": request.reason},
                {"administrative": True},
            )
            self._persist_session(connection, session, state, context, current_revision)
            terminal_session = self._session_row(connection, session_id)
            self._generate_review(connection, terminal_session, scenario, state)
            result = ServiceResult(
                200,
                {
                    "session_id": session_id,
                    "revision": context.revision,
                    "status": context.status,
                    "next_actor": None,
                    "terminal_reason": request.reason,
                },
            )
            self._save_idempotency(
                connection, scope, request.idempotency_key, request_digest, result
            )
            return result

    def _apply_participant_action(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        participant: sqlite3.Row,
        scenario: dict[str, Any],
        state: dict[str, Any],
        message: str,
        parsed: Any,
        initial_revision: int,
        *,
        defer_builtin_npc: bool = False,
        _supply_legacy: bool = False,
    ) -> ServiceResult:
        if is_supply_scenario(scenario) and not _supply_legacy:
            return self._apply_supply_action(connection, session, participant, scenario, state, message, parsed, initial_revision)
        context = TransitionContext(
            revision=initial_revision,
            round=int(session["round"]),
            substantive_turn_count=int(session["substantive_turn_count"]),
            status=str(session["status"]),
            next_participant_id=str(session["next_participant_id"]),
        )
        active_offer = state.get("active_offer")

        if (
            parsed.action == "counter_offer"
            and active_offer
            and active_offer["status"] == "active"
            and active_offer["proposer_participant_id"] != participant["id"]
        ):
            restated = dict(active_offer["terms"])
            restated.update(parsed.terms_delta)
            if restated == active_offer["terms"] and offer_is_complete(scenario, restated):
                # Restating the counterpart's own package is an acceptance intent, not a new
                # offer: a human or external agent binds only through the confirmation step.
                parsed = ParsedAction("acceptance_intent")

        if parsed.action == "clarification":
            context.revision += 1
            reason = parsed.reason_code or "ambiguous_message"
            clarification_count = int(state.get("consecutive_clarifications", 0)) + 1
            state["consecutive_clarifications"] = clarification_count
            protocol_control_count = self._record_protocol_control(state)
            state["pending_clarification"] = {
                "participant_id": participant["id"],
                "reason_code": reason,
                **parsed.details,
            }
            self._insert_message(
                connection,
                session["id"],
                context.revision,
                participant,
                message,
                session["language"],
            )
            clarification_payload = {"reason_code": reason, **parsed.details}
            event_id = self._insert_event(
                connection,
                session["id"],
                context.revision,
                participant["id"],
                "clarification.required",
                clarification_payload,
                {"parser_action": parsed.action, **parsed.details},
            )
            maximum = self._protocol_control_limit(scenario)
            terminal_reason: str | None = None
            if protocol_control_count >= maximum:
                terminal_reason = (
                    "clarification_limit_reached"
                    if clarification_count >= maximum
                    else "protocol_control_limit_reached"
                )
                self._expire_protocol_controls(
                    connection,
                    session,
                    participant,
                    state,
                    context,
                    terminal_reason,
                    protocol_control_count,
                )
            self._persist_session(connection, session, state, context, initial_revision)
            if context.status == "expired":
                terminal_session = self._session_row(connection, session["id"])
                self._generate_review(connection, terminal_session, scenario, state)
                return ServiceResult(
                    200,
                    self._command_response(
                        connection,
                        session["id"],
                        participant,
                        scenario,
                        state,
                        context,
                        result="expired",
                        extra={"terminal_reason": terminal_reason},
                    ),
                )
            response = self._command_response(
                connection,
                session["id"],
                participant,
                scenario,
                state,
                context,
                result="clarification_required",
                extra={
                    "clarification": {
                        **clarification_payload,
                        "question": parsed.details.get("question") or clarification_text(
                            session["language"],
                            reason,
                            expected_currency=parsed.details.get("expected_currency"),
                        ),
                        "evidence_event_id": event_id,
                    }
                },
            )
            return ServiceResult(200, response)

        state["consecutive_clarifications"] = 0

        if parsed.action == "acceptance_intent":
            if (
                not active_offer
                or active_offer["status"] != "active"
                or active_offer["proposer_participant_id"] == participant["id"]
            ):
                return self._failed_transition(
                    connection,
                    session,
                    participant,
                    scenario,
                    state,
                    context,
                    initial_revision,
                    message,
                    "offer_not_active",
                    "There is no active counterparty offer to accept",
                    409,
                )
            violations = self._binding_violations(scenario, active_offer["terms"])
            if violations:
                return self._failed_transition(
                    connection,
                    session,
                    participant,
                    scenario,
                    state,
                    context,
                    initial_revision,
                    message,
                    "offer_not_bindable",
                    "The active offer is incomplete or violates a hard constraint",
                    422,
                    {"violation_codes": violations},
                )
            context.revision += 1
            pending = {
                "participant_id": participant["id"],
                "offer_id": active_offer["offer_id"],
                "offer_revision": active_offer["offer_revision"],
                "terms": active_offer["terms"],
                "created_session_revision": context.revision,
            }
            state["pending_confirmation"] = pending
            state["pending_clarification"] = None
            self._insert_message(
                connection,
                session["id"],
                context.revision,
                participant,
                message,
                session["language"],
            )
            self._insert_event(
                connection,
                session["id"],
                context.revision,
                participant["id"],
                "acceptance.confirmation_required",
                {
                    "offer_id": active_offer["offer_id"],
                    "offer_revision": active_offer["offer_revision"],
                    "terms": active_offer["terms"],
                },
                {},
            )
            protocol_control_count = self._record_protocol_control(state)
            if protocol_control_count >= self._protocol_control_limit(scenario):
                self._expire_protocol_controls(
                    connection,
                    session,
                    participant,
                    state,
                    context,
                    "protocol_control_limit_reached",
                    protocol_control_count,
                )
            self._persist_session(connection, session, state, context, initial_revision)
            if context.status == "expired":
                terminal_session = self._session_row(connection, session["id"])
                self._generate_review(connection, terminal_session, scenario, state)
                return ServiceResult(
                    200,
                    self._command_response(
                        connection,
                        session["id"],
                        participant,
                        scenario,
                        state,
                        context,
                        result="expired",
                        extra={"terminal_reason": "protocol_control_limit_reached"},
                    ),
                )
            response = self._command_response(
                connection,
                session["id"],
                participant,
                scenario,
                state,
                context,
                result="confirmation_required",
                extra={
                    "pending_confirmation": {
                        "offer_id": active_offer["offer_id"],
                        "offer_revision": active_offer["offer_revision"],
                        "terms": active_offer["terms"],
                        "unresolved_required_terms": [],
                    }
                },
            )
            return ServiceResult(200, response)

        if parsed.action == "cancel_acceptance":
            context.revision += 1
            state["pending_confirmation"] = None
            state["pending_clarification"] = None
            self._insert_message(
                connection,
                session["id"],
                context.revision,
                participant,
                message,
                session["language"],
            )
            self._insert_event(
                connection,
                session["id"],
                context.revision,
                participant["id"],
                "acceptance.cancelled",
                {},
                {},
            )
            protocol_control_count = self._record_protocol_control(state)
            if protocol_control_count >= self._protocol_control_limit(scenario):
                self._expire_protocol_controls(
                    connection,
                    session,
                    participant,
                    state,
                    context,
                    "protocol_control_limit_reached",
                    protocol_control_count,
                )
            self._persist_session(connection, session, state, context, initial_revision)
            if context.status == "expired":
                terminal_session = self._session_row(connection, session["id"])
                self._generate_review(connection, terminal_session, scenario, state)
                return ServiceResult(
                    200,
                    self._command_response(
                        connection,
                        session["id"],
                        participant,
                        scenario,
                        state,
                        context,
                        result="expired",
                        extra={"terminal_reason": "protocol_control_limit_reached"},
                    ),
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
                    result="confirmation_cancelled",
                ),
            )

        if parsed.action == "confirm_acceptance":
            pending = state.get("pending_confirmation")
            active_offer = state.get("active_offer")
            if (
                not pending
                or not active_offer
                or active_offer["status"] != "active"
                or pending["offer_id"] != active_offer["offer_id"]
                or pending["offer_revision"] != active_offer["offer_revision"]
            ):
                return self._failed_transition(
                    connection,
                    session,
                    participant,
                    scenario,
                    state,
                    context,
                    initial_revision,
                    message,
                    "offer_not_active",
                    "The confirmed offer revision is not active",
                    409,
                )
            violations = self._binding_violations(scenario, active_offer["terms"])
            if violations:
                return self._failed_transition(
                    connection,
                    session,
                    participant,
                    scenario,
                    state,
                    context,
                    initial_revision,
                    message,
                    "offer_not_bindable",
                    "The confirmed offer is not bindable",
                    422,
                    {"violation_codes": violations},
                )
            context.revision += 1
            context.status = "agreement_reached"
            context.next_participant_id = None
            active_offer["status"] = "accepted"
            state["agreement_offer"] = dict(active_offer)
            state["active_offer"] = None
            state["pending_confirmation"] = None
            state["pending_clarification"] = None
            connection.execute(
                "UPDATE offers SET status = 'accepted' WHERE session_id = ? "
                "AND offer_id = ? AND offer_revision = ?",
                (session["id"], active_offer["offer_id"], active_offer["offer_revision"]),
            )
            self._insert_message(
                connection,
                session["id"],
                context.revision,
                participant,
                message,
                session["language"],
            )
            self._insert_event(
                connection,
                session["id"],
                context.revision,
                participant["id"],
                "agreement.reached",
                {
                    "offer_id": active_offer["offer_id"],
                    "offer_revision": active_offer["offer_revision"],
                    "terms": active_offer["terms"],
                },
                {},
            )
            self._persist_session(connection, session, state, context, initial_revision)
            terminal_session = self._session_row(connection, session["id"])
            self._generate_review(connection, terminal_session, scenario, state)
            return ServiceResult(
                200,
                self._command_response(
                    connection,
                    session["id"],
                    participant,
                    scenario,
                    state,
                    context,
                    result="agreement_reached",
                ),
            )

        if parsed.action == "walk_away":
            context.revision += 1
            context.substantive_turn_count += 1
            context.status = "walked_away"
            context.next_participant_id = None
            self._advance_round(state, participant["id"], context, scenario, terminal=True)
            self._close_active_offer(connection, session["id"], state, "closed_by_termination")
            state["pending_confirmation"] = None
            state["pending_clarification"] = None
            self._insert_message(
                connection,
                session["id"],
                context.revision,
                participant,
                message,
                session["language"],
            )
            self._insert_event(
                connection,
                session["id"],
                context.revision,
                participant["id"],
                "session.walked_away",
                {"role": participant["role"]},
                {},
            )
            self._persist_session(connection, session, state, context, initial_revision)
            terminal_session = self._session_row(connection, session["id"])
            self._generate_review(connection, terminal_session, scenario, state)
            return ServiceResult(
                200,
                self._command_response(
                    connection,
                    session["id"],
                    participant,
                    scenario,
                    state,
                    context,
                    result="walked_away",
                ),
            )

        committed_actions: list[dict[str, Any]] = []
        if parsed.action == "counter_offer":
            result = self._commit_counter_offer(
                connection,
                session,
                participant,
                scenario,
                state,
                context,
                message,
                parsed.terms_delta,
            )
            if isinstance(result, ServiceResult):
                return result
            committed_actions.append(result)
        elif parsed.action in {"reject", "withdraw"}:
            if not active_offer or active_offer["status"] != "active":
                return self._failed_transition(
                    connection,
                    session,
                    participant,
                    scenario,
                    state,
                    context,
                    initial_revision,
                    message,
                    "offer_not_active",
                    "There is no active offer for this action",
                    409,
                )
            if (
                parsed.action == "withdraw"
                and active_offer["proposer_participant_id"] != participant["id"]
            ):
                return self._failed_transition(
                    connection,
                    session,
                    participant,
                    scenario,
                    state,
                    context,
                    initial_revision,
                    message,
                    "offer_not_owned",
                    "Only the proposer can withdraw an active offer",
                    409,
                )
            if (
                parsed.action == "reject"
                and active_offer["proposer_participant_id"] == participant["id"]
            ):
                return self._failed_transition(
                    connection,
                    session,
                    participant,
                    scenario,
                    state,
                    context,
                    initial_revision,
                    message,
                    "offer_not_owned",
                    "Only the recipient can reject an active offer; withdraw your own offer",
                    409,
                )
            lifecycle = "withdrawn" if parsed.action == "withdraw" else "rejected"
            self._set_offer_status(connection, session["id"], active_offer, lifecycle)
            state["active_offer"] = None
            committed_actions.append(
                self._commit_public_action(
                    connection,
                    session,
                    participant,
                    scenario,
                    state,
                    context,
                    message,
                    parsed.action,
                    {
                        "offer_id": active_offer["offer_id"],
                        "offer_revision": active_offer["offer_revision"],
                    },
                )
            )
        else:
            committed_actions.append(
                self._commit_public_action(
                    connection,
                    session,
                    participant,
                    scenario,
                    state,
                    context,
                    message,
                    parsed.action,
                    {},
                )
            )

        state["pending_confirmation"] = None
        state["pending_clarification"] = None
        if context.status == "active":
            next_row = self._participant_row(connection, str(context.next_participant_id))
            if next_row["controller"] == "built_in_npc" and not defer_builtin_npc:
                raise RuntimeError("Built-in NPC actions require the durable render-job path")

        if (
            context.status == "active"
            and state["completed_rounds"] >= scenario["protocol"]["max_rounds"]
        ):
            context.status = "expired"
            context.next_participant_id = None
            self._close_active_offer(connection, session["id"], state, "expired")
            self._insert_event(
                connection,
                session["id"],
                context.revision,
                None,
                "session.expired",
                {"max_rounds": scenario["protocol"]["max_rounds"]},
                {},
            )

        self._persist_session(connection, session, state, context, initial_revision)
        current_session = self._session_row(connection, session["id"])
        if context.status in TERMINAL_STATUSES:
            self._generate_review(connection, current_session, scenario, state)
        response_actor = participant
        return ServiceResult(
            200,
            self._command_response(
                connection,
                session["id"],
                response_actor,
                scenario,
                state,
                context,
                result=context.status if context.status != "active" else "turn_committed",
                extra={"committed_actions": committed_actions},
            ),
        )

    def _commit_counter_offer(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        participant: sqlite3.Row,
        scenario: dict[str, Any],
        state: dict[str, Any],
        context: TransitionContext,
        message: str,
        terms_delta: dict[str, Any],
    ) -> dict[str, Any] | ServiceResult:
        active_offer = state.get("active_offer")
        terms = dict(active_offer["terms"] if active_offer else {})
        terms.update(terms_delta)
        violations = validate_terms(scenario, terms, complete=False)
        if violations:
            return self._failed_transition(
                connection,
                session,
                participant,
                scenario,
                state,
                context,
                int(session["revision"]),
                message,
                "offer_invalid",
                "The proposed terms do not match the compiled scenario grammar",
                422,
                {"violation_codes": violations},
            )

        state["consecutive_protocol_controls"] = 0
        if active_offer:
            offer_id = active_offer["offer_id"]
            offer_revision = int(active_offer["offer_revision"]) + 1
            self._set_offer_status(connection, session["id"], active_offer, "superseded")
        else:
            offer_id = "offer_" + uuid.uuid4().hex[:20]
            offer_revision = 1
        context.revision += 1
        context.substantive_turn_count += 1
        new_offer = {
            "offer_id": offer_id,
            "offer_revision": offer_revision,
            "proposer_participant_id": participant["id"],
            "terms": terms,
            "status": "active",
        }
        state["active_offer"] = new_offer
        connection.execute(
            """
            INSERT INTO offers(
                session_id, offer_id, offer_revision, proposer_participant_id,
                terms_json, status, created_session_revision
            ) VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                session["id"],
                offer_id,
                offer_revision,
                participant["id"],
                _json(terms),
                context.revision,
            ),
        )
        self._advance_round(state, participant["id"], context, scenario)
        other = self._other_participant(connection, session["id"], participant["id"])
        context.next_participant_id = other["id"]
        self._insert_message(
            connection, session["id"], context.revision, participant, message, session["language"]
        )
        event_id = self._insert_event(
            connection,
            session["id"],
            context.revision,
            participant["id"],
            "offer.countered" if active_offer else "offer.created",
            {
                "offer_id": offer_id,
                "offer_revision": offer_revision,
                "terms": terms,
                "unresolved_required_terms": [
                    term for term in scenario["terms"]["required_term_ids"] if term not in terms
                ],
            },
            {"term_delta": terms_delta},
        )
        return {
            "participant_id": participant["id"],
            "action": "counter_offer" if active_offer else "offer",
            "message": message,
            "offer": {"offer_id": offer_id, "offer_revision": offer_revision},
            "evidence_event_id": event_id,
        }

    def _commit_public_action(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        participant: sqlite3.Row,
        scenario: dict[str, Any],
        state: dict[str, Any],
        context: TransitionContext,
        message: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        state["consecutive_protocol_controls"] = 0
        context.revision += 1
        context.substantive_turn_count += 1
        self._advance_round(state, participant["id"], context, scenario)
        other = self._other_participant(connection, session["id"], participant["id"])
        context.next_participant_id = other["id"]
        self._insert_message(
            connection, session["id"], context.revision, participant, message, session["language"]
        )
        event_id = self._insert_event(
            connection,
            session["id"],
            context.revision,
            participant["id"],
            f"participant.{action}",
            payload,
            {},
        )
        return {
            "participant_id": participant["id"],
            "action": action,
            "message": message,
            "evidence_event_id": event_id,
        }

    @staticmethod
    def _npc_decision(
        scenario: dict[str, Any],
        state: dict[str, Any],
        npc: sqlite3.Row,
        player_message: str,
        player_action: str,
        recent_messages: tuple[str, ...] = (),
    ) -> tuple[str, str, dict[str, Any]]:
        if is_supply_scenario(scenario):
            from .supply_language import decide_supply_action
            current = supply_current(state)
            decision = decide_supply_action(scenario, npc["role"], current.get("terms", {}), player_message,
                                           scenario.get("language", "ru"), formal=bool(state.get("active_offer")),
                                           proposer_role=current.get("proposer_role") or next((role for role, pid in state["role_to_participant"].items() if pid == current.get("proposer_participant_id")), None))
            return decision.action, "acknowledge_information", decision.terms or {}
        conversational = classify_npc_speech_act(player_message, player_action)
        public_position: dict[str, Any] = {}
        active_offer = state.get("active_offer")
        if active_offer and active_offer.get("proposer_participant_id") == npc["id"]:
            public_position = dict(active_offer.get("terms") or {})
        elif state.get("npc_counter_terms"):
            public_position = dict(state["npc_counter_terms"])
        elif state.get("opening_participant_id") == npc["id"]:
            public_position = dict(state.get("opening_terms") or {})
        if (
            conversational != "qualitative_interest_answer"
            and public_position
            and requests_npc_public_position(
                player_message,
                recent_messages=recent_messages,
            )
            and (
                not mentioned_term_ids(
                    player_message, scenario["terms"]["definitions"]
                )
                or not re.search(
                    r"\b(?:почему|зачем|why)\b", player_message, re.IGNORECASE
                )
            )
        ):
            return "inform", "public_position_restatement", public_position
        directive = detected_topic_directive(player_message, scenario["terms"]["definitions"])
        term_signals = detected_term_signals(
            player_message, scenario["terms"]["definitions"]
        )
        conditional_exchange = detected_conditional_exchange(
            player_message, scenario["terms"]["definitions"]
        )
        if term_signals["concern"] and conversational in {
            "greeting",
            "acknowledge_information",
        }:
            conversational = "focused_discussion"
        if conditional_exchange and conversational in {
            "greeting",
            "acknowledge_information",
            "general_answer",
        }:
            conversational = "focused_discussion"
        if directive.get("focus") and conversational in {"request_complete_offer", "acknowledge_information", "greeting"}:
            conversational = "focused_discussion"
        if player_action in {"question", "inform"} and conversational in CONVERSATIONAL_SPEECH_ACTS | {"focused_discussion"}:
            return "inform", conversational, {}
        if active_offer and active_offer["proposer_participant_id"] != npc["id"]:
            active_terms = dict(active_offer["terms"])
            if not offer_is_complete(scenario, active_terms):
                if player_action == "counter_offer" and conversational not in {
                    "abusive_language_boundary", "general_answer", "qualitative_interest_answer",
                }:
                    return "inform", "acknowledge_partial_offer", {}
                if conversational in CONVERSATIONAL_SPEECH_ACTS or conversational == "focused_discussion":
                    # Answer the question first; the missing terms stay visible on the offer
                    # card and the next complete-offer prompt names them.
                    return "inform", conversational, {}
                return "inform", "request_complete_offer", {}
            if offer_is_acceptable(scenario, npc["role"], active_terms) and offer_is_bindable(
                scenario, active_terms
            ):
                return "accept", "offer_acceptance", active_terms
            counter = select_counterproposal(
                scenario,
                npc["role"],
                active_terms,
                state["opening_terms"],
                previous_counter_terms=state.get("npc_counter_terms"),
            )
            if counter is not None:
                return "counter_offer", "complete_counteroffer", counter.terms
            return "reject", "offer_rejection", {}
        return (
            "inform",
            conversational,
            {},
        )

    @staticmethod
    def _priority_labels(scenario: dict[str, Any], npc_role: str, language: str) -> tuple[str, ...]:
        interests = scenario["roles"][npc_role].get("interests", {})
        ordered = sorted(
            interests,
            key=lambda term_id: (
                interests[term_id].get("weight", 0) if isinstance(interests[term_id], dict) else 0
            ),
            reverse=True,
        )
        labels = participant_term_labels(scenario, language)
        return tuple(labels[term_id] for term_id in ordered if term_id in labels)

    def _dialogue_context(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        npc_participant_id: str,
    ) -> tuple[PublicDialogueTurn, ...]:
        rows = connection.execute(
            "SELECT participant_id, content FROM messages "
            "WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, MAX_CONTEXT_TURNS),
        ).fetchall()
        turns = [
            PublicDialogueTurn(
                "npc" if row["participant_id"] == npc_participant_id else "player",
                redact_untrusted_credentials(str(row["content"]), *self._known_redaction_secrets),
            )
            for row in reversed(rows)
        ]
        return bounded_dialogue_context(turns)

    def _build_dialogue_request(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        npc: sqlite3.Row,
        scenario: dict[str, Any],
        *,
        speech_act: str,
        terms: dict[str, Any],
        player_message: str,
    ) -> NpcDialogueRequest:
        if is_supply_scenario(scenario):
            return self._supply_dialogue_request(connection, session, npc, scenario, speech_act, terms, player_message)
        labels = participant_term_labels(scenario, str(session["language"]))
        memory = self._public_conversation_memory(connection, session, npc, scenario, labels)
        directive = detected_topic_directive(player_message, labels)
        term_signals = detected_term_signals(player_message, labels)
        conditional_exchange = detected_conditional_exchange(player_message, labels)
        current_topic = memory.get("current_topic") or {}
        focus = (
            (conditional_exchange[1] if conditional_exchange else None)
            or
            next(iter(term_signals["concern"]), None)
            or directive.get("focus")
            or current_topic.get("term_id")
        )
        mentioned = mentioned_term_ids(player_message, labels)
        focused_terms = (focus,) if focus in labels else mentioned[:1]
        disclosed_reasons = self._disclosed_dialogue_reasons(connection, session, npc, scenario)
        disclosed_ids = {reason_id for reason_id, _, _ in disclosed_reasons}
        approved_reasons: tuple[tuple[str, str], ...] = ()
        if speech_act in {"general_answer", "qualitative_interest_answer"}:
            # Only a short explanation follow-up inherits the previous topic.
            # An unrelated question must not disclose reasons for that topic.
            contextual_why = re.fullmatch(
                r"(?:а\s+)?(?:почему|зачем)(?:\s+(?:так|это|именно так|это важно|"
                r"для вас это важно|это для вас важно))?[?!. ]*|(?:and\s+)?why"
                r"(?:\s+(?:is that|does that matter(?: to you)?|is that important|so))?[?!. ]*",
                player_message.strip().casefold(),
            )
            question_terms = mentioned or (focused_terms if contextual_why else ())
            approved_reasons = tuple(
                (reason["id"], reason["text"])
                for reason in scenario["roles"][npc["role"]].get("dialogue_reasons", [])
                if reason["disclose_when"] == "on_topic_question" and reason["term_id"] in question_terms
                and reason["id"] not in disclosed_ids
            )[:2]
        priority_labels = (
            self._priority_labels(scenario, str(npc["role"]), str(session["language"]))
            if speech_act == "qualitative_interest_answer"
            else ()
        )
        active_offer = (_loads(session["state_json"]) or {}).get("active_offer") or {}
        offer_terms = active_offer.get("terms") or {}
        requested_term_id = None
        if (
            speech_act == "focused_discussion"
            and len(focused_terms) == 1
            and not term_signals["favorable_surprise"]
            and not conditional_exchange
        ):
            requested_term_id = focused_terms[0]
        if speech_act == "request_complete_offer":
            requested_term_id = next((term_id for term_id in scenario["terms"]["required_term_ids"]
                                      if term_id not in offer_terms and term_id in labels), None)
        missing_labels = tuple(
            labels[term_id]
            for term_id in scenario["terms"]["required_term_ids"]
            if term_id not in offer_terms and term_id in labels
        )
        references: list[PublicNumericReference] = []
        public_active = next((offer for offer in memory.get("offers", [])
                              if offer["status"] == "active" and offer["offer_id"] == active_offer.get("offer_id")
                              and offer["offer_revision"] == active_offer.get("offer_revision")), None)
        if public_active:
            proposer = self._participant_row(connection, active_offer["proposer_participant_id"])
            for term_id, value in public_active["terms"].items():
                if term_id in labels and type(value) in (int, float) and math.isfinite(value) and len(references) < 12:
                    references.append(PublicNumericReference(
                        slot_id="quote_" + chr(ord("a") + len(references)), offer_id=public_active["offer_id"],
                        offer_revision=public_active["offer_revision"], proposer_role=proposer["role"],
                        term_id=term_id, value=value, currency=scenario["currency"],
                    ))
        exchange_labels: tuple[str, ...] = ()
        if speech_act == "complete_counteroffer":
            # Explain only a visible package change. Never expose either role's utility.
            prior = next((offer for offer in reversed(memory.get("offers", [])) if offer["speaker"] == "player"), None)
            if prior:
                counter = select_counterproposal(scenario, npc["role"], prior["terms"],
                                                  (_loads(session["state_json"]) or {}).get("opening_terms", {}),
                                                  previous_counter_terms=(_loads(session["state_json"]) or {}).get("npc_counter_terms"))
                if counter and counter.reason_code == "conditional_exchange" and counter.terms == terms:
                    exchange_labels = tuple(labels[term_id] for term_id in counter.trade_term_ids if term_id in labels)
        options = npc_message_options(
            str(session["language"]),
            speech_act,
            terms,
            scenario=scenario,
            priority_labels=priority_labels,
            missing_labels=missing_labels,
            focused_labels=tuple(labels[term] for term in focused_terms),
            reason_texts=tuple(text for _, text in approved_reasons),
            difficulty=str(session["difficulty"]),
            conversation_style=scenario["roles"][npc["role"]].get("conversation_style", "pragmatic"),
            requested_label=labels.get(requested_term_id),
            exchange_labels=exchange_labels,
        )
        signal_options: tuple[str, ...] = ()
        if speech_act == "focused_discussion" and conditional_exchange:
            offered_label = labels[conditional_exchange[0]]
            requested_label = labels[conditional_exchange[1]]
            if session["language"] == "ru":
                options = (
                    f"Понял: вы предлагаете связать условия «{offered_label}» и "
                    f"«{requested_label}». Какой вариант по условию «{offered_label}» "
                    "вы готовы рассмотреть?",
                    f"Рассмотрим ваш вариант обмена между условиями «{offered_label}» и "
                    f"«{requested_label}». Что именно вы готовы изменить в условии "
                    f"«{offered_label}»?",
                    f"Вы готовы обсуждать условие «{offered_label}» ради изменения условия "
                    f"«{requested_label}». Какую позицию по условию «{offered_label}» "
                    "вы предлагаете?",
                )
            else:
                options = (
                    f"I understand that you propose linking {offered_label} and "
                    f"{requested_label}. What change to {offered_label} would you consider?",
                    f"Let us examine your proposed trade between {offered_label} and "
                    f"{requested_label}. What would you change about {offered_label}?",
                    f"You are willing to discuss {offered_label} in return for a change to "
                    f"{requested_label}. What position do you propose on {offered_label}?",
                )
        if (
            speech_act == "focused_discussion"
            and term_signals["concern"]
            and term_signals["favorable_surprise"]
        ):
            concern_label = labels[term_signals["concern"][0]]
            favorable_label = labels[term_signals["favorable_surprise"][0]]
            if session["language"] == "ru":
                signal_options = (
                    f"Я понял, что сейчас вас беспокоит условие «{concern_label}». "
                    f"Готовы ли вы обсуждать обмен с изменением условия «{favorable_label}»?",
                    f"Сосредоточимся на условии «{concern_label}». Можно ли рассматривать "
                    f"гибкость по условию «{favorable_label}» как часть обмена?",
                    f"Правильно понимаю: основной вопрос — «{concern_label}», а условие "
                    f"«{favorable_label}» можно обсуждать в составе обмена?",
                )
            else:
                signal_options = (
                    f"I understand that {concern_label} is your current concern. "
                    f"Would you discuss a trade that changes {favorable_label}?",
                    f"Let us focus on {concern_label}. Can flexibility on "
                    f"{favorable_label} be part of a trade?",
                    f"Is my understanding correct: {concern_label} is the main issue, "
                    f"and {favorable_label} can be discussed as part of a trade?",
                )
            options = signal_options + options
        dialogue_context = self._dialogue_context(
            connection,
            str(session["id"]),
            str(npc["id"]),
        )
        session_state = _loads(session["state_json"])
        training = session_state.get("training", {})
        training_context = npc_training_context(
            training, str(session["language"]), player_message,
        )
        strategy = scenario["roles"][npc["role"]].get("dialogue_strategy", {})
        shared_context_parts = [strategy.get("shared_context", "")]
        if (
            training.get("setup", {}).get("relationship") == "successful_history"
            and strategy.get("successful_history_context")
        ):
            shared_context_parts.append(strategy["successful_history_context"])
        shared_scenario_context = " ".join(
            part.strip() for part in shared_context_parts if part.strip()
        )
        if speech_act in {"general_answer", "acknowledge_information"} and not approved_reasons:
            options = topic_return_options(
                player_message, str(session["language"]), labels, dialogue_context,
                training_context, focus,
            ) or options
        fallback = select_varied_fallback(
            signal_options or options,
            player_message,
            [turn.text for turn in dialogue_context if turn.speaker == "npc"],
        )
        return NpcDialogueRequest(
            language=str(session["language"]),
            currency=str(scenario["currency"]),
            speech_act=speech_act,
            approved_terms=tuple((term_id, terms[term_id]) for term_id in sorted(terms)),
            public_interest_labels=priority_labels,
            participant_facing_terms=tuple(labels.items()),
            dialogue_context=dialogue_context,
            approved_reply_options=options,
            fallback_text=fallback,
            retrieved_reply_examples=retrieve_reply_examples(
                scenario_id=str(scenario["id"]),
                npc_role=str(npc["role"]),
                language=str(session["language"]),
                speech_act=speech_act,
                player_message=player_message,
                focused_term_ids=focused_terms,
                approved_reasons=approved_reasons,
                training_context=training_context,
            ),
            scenario_title=str(scenario["title"]),
            npc_role=str(npc["role"]),
            missing_term_labels=missing_labels,
            focused_term_ids=focused_terms,
            player_concern_term_ids=term_signals["concern"],
            player_favorable_surprise_term_ids=term_signals["favorable_surprise"],
            conversation_memory=memory,
            approved_reasons=approved_reasons,
            disclosed_reasons=disclosed_reasons,
            difficulty=str(session["difficulty"]),
            conversation_style=scenario["roles"][npc["role"]].get("conversation_style", "pragmatic"),
            requested_term_id=requested_term_id,
            numeric_references=tuple(references),
            training_context=training_context,
            shared_scenario_context=shared_scenario_context,
            conversation_goal=str(strategy.get("conversation_goal", "")),
            methodology_version=METHODOLOGY_VERSION,
        )

    def _parse_context(self, connection: sqlite3.Connection, session: sqlite3.Row,
                       participant: sqlite3.Row, scenario: dict[str, Any], state: dict[str, Any]) -> ParseContext:
        opponent = connection.execute("SELECT * FROM participants WHERE session_id = ? AND id != ? LIMIT 1",
                                      (session["id"], participant["id"])).fetchone()
        labels = participant_term_labels(scenario, str(session["language"]))
        memory = self._public_conversation_memory(connection, session, opponent, scenario, labels) if opponent else {}
        active = state.get("active_offer") or {}
        public = [offer for offer in memory.get("offers", []) if offer["status"] == "active"]
        unique = len(public) == 1 and public[0]["offer_id"] == active.get("offer_id") and public[0]["offer_revision"] == active.get("offer_revision")
        expected = None
        last_message = connection.execute("SELECT participant_id, session_revision FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                                          (session["id"],)).fetchone()
        if opponent and last_message and last_message["participant_id"] == opponent["id"]:
            delivered = connection.execute("SELECT public_payload_json FROM events WHERE session_id = ? AND participant_id = ? "
                                           "AND session_revision = ? AND type = 'npc.utterance.delivered' ORDER BY id DESC LIMIT 1",
                                           (session["id"], opponent["id"], last_message["session_revision"])).fetchone()
            if delivered:
                requested = _loads(delivered["public_payload_json"]).get("requested_term_id")
                expected = requested if requested in labels else None
        return ParseContext(
            active_offer_id=active.get("offer_id") if unique else None,
            active_offer_revision=active.get("offer_revision") if unique else None,
            active_offer_terms={term: value for term, value in active.get("terms", {}).items()
                                if term in labels and type(value) in (int, float) and math.isfinite(value)} if unique else {},
            active_offer_currency=scenario["currency"] if unique else None,
            focused_term_id=(memory.get("current_topic") or {}).get("term_id"),
            expected_term_id=expected, ambiguous_offer_reference=len(public) > 1,
        )

    def _public_conversation_memory(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        npc: sqlite3.Row,
        scenario: dict[str, Any],
        labels: dict[str, str],
    ) -> dict[str, Any]:
        messages = [dict(row) for row in connection.execute(
            "SELECT id, session_revision, participant_id, content FROM messages "
            "WHERE session_id = ? ORDER BY id", (session["id"],),
        )]
        for message in messages:
            message["content"] = redact_untrusted_credentials(
                message["content"], *self._known_redaction_secrets,
            )
        events = [
            {"event_id": row["event_id"], "session_revision": row["session_revision"],
             "participant_id": row["participant_id"], "type": row["type"],
             "payload": _loads(row["public_payload_json"])}
            for row in connection.execute(
                "SELECT event_id, session_revision, participant_id, type, public_payload_json "
                "FROM events WHERE session_id = ? AND type IN "
                "('offer.created', 'offer.countered', 'participant.reject', 'participant.withdraw', "
                "'agreement.reached', 'session.expired', 'session.walked_away', 'session.aborted') "
                "ORDER BY id", (session["id"],),
            )
        ]
        return build_conversation_memory(
            messages, events, npc_participant_id=str(npc["id"]), term_labels=labels,
            required_term_ids=scenario["terms"]["required_term_ids"],
        )

    @staticmethod
    def _disclosed_dialogue_reasons(
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        npc: sqlite3.Row,
        scenario: dict[str, Any],
    ) -> tuple[tuple[str, str, str], ...]:
        authored = {item["id"]: item["text"] for item in
                    scenario["roles"][npc["role"]].get("dialogue_reasons", [])}
        disclosed: dict[str, tuple[str, str, str]] = {}
        for row in connection.execute(
            "SELECT event_id, public_payload_json FROM events WHERE session_id = ? "
            "AND participant_id = ? AND type = 'npc.utterance.delivered' ORDER BY id",
            (session["id"], npc["id"]),
        ):
            for reason_id in _loads(row["public_payload_json"]).get("disclosed_reason_ids", []):
                if reason_id in authored:
                    disclosed[reason_id] = (reason_id, authored[reason_id], row["event_id"])
        return tuple(disclosed.values())[:6]

    def _build_utterance_plan(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        npc: sqlite3.Row,
        scenario: dict[str, Any],
        *,
        intent_revision: int,
        action: str,
        speech_act: str,
        terms: dict[str, Any],
        player_message: str,
    ) -> NpcUtterancePlan:
        request = self._build_dialogue_request(
            connection,
            session,
            npc,
            scenario,
            speech_act=speech_act,
            terms=terms,
            player_message=player_message,
        )
        return NpcUtterancePlan(
            render_id=stable_render_id(str(session["id"]), intent_revision),
            session_id=str(session["id"]),
            intent_revision=intent_revision,
            npc_participant_id=str(npc["id"]),
            action=action,
            request=request,
        )

    def _commit_npc_authoritative_action(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        npc: sqlite3.Row,
        scenario: dict[str, Any],
        state: dict[str, Any],
        context: TransitionContext,
        plan: NpcUtterancePlan,
    ) -> dict[str, Any]:
        if is_supply_scenario(scenario):
            return self._commit_supply_npc(connection, session, npc, scenario, state, context, plan)
        state["consecutive_protocol_controls"] = 0
        active_offer = state.get("active_offer")
        action = plan.action
        terms = dict(plan.request.approved_terms)
        context.revision += 1
        context.substantive_turn_count += 1
        self._advance_round(state, npc["id"], context, scenario)

        if action == "accept" and active_offer:
            context.status = "agreement_reached"
            context.next_participant_id = None
            self._set_offer_status(connection, session["id"], active_offer, "accepted")
            state["agreement_offer"] = dict(active_offer)
            state["agreement_offer"]["status"] = "accepted"
            state["active_offer"] = None
            event_id = self._insert_event(
                connection,
                session["id"],
                context.revision,
                npc["id"],
                "agreement.reached",
                {
                    "offer_id": active_offer["offer_id"],
                    "offer_revision": active_offer["offer_revision"],
                    "terms": active_offer["terms"],
                },
                {"npc_utility": evaluate_utility(scenario, npc["role"], active_offer["terms"])},
            )
            return {
                "participant_id": npc["id"],
                "action": action,
                "speech_act": plan.request.speech_act,
                "evidence_event_id": event_id,
            }

        if action == "counter_offer" and active_offer:
            self._set_offer_status(connection, session["id"], active_offer, "superseded")
            offer_revision = int(active_offer["offer_revision"]) + 1
            new_offer = {
                "offer_id": active_offer["offer_id"],
                "offer_revision": offer_revision,
                "proposer_participant_id": npc["id"],
                "terms": terms,
                "status": "active",
            }
            state["active_offer"] = new_offer
            state["npc_counter_terms"] = dict(terms)
            connection.execute(
                """
                INSERT INTO offers(
                    session_id, offer_id, offer_revision, proposer_participant_id,
                    terms_json, status, created_session_revision
                ) VALUES (?, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    session["id"],
                    new_offer["offer_id"],
                    offer_revision,
                    npc["id"],
                    _json(terms),
                    context.revision,
                ),
            )
            other = self._other_participant(connection, session["id"], npc["id"])
            context.next_participant_id = other["id"]
            event_id = self._insert_event(
                connection,
                session["id"],
                context.revision,
                npc["id"],
                "offer.countered",
                {
                    "offer_id": new_offer["offer_id"],
                    "offer_revision": offer_revision,
                    "terms": terms,
                },
                {"npc_utility": evaluate_utility(scenario, npc["role"], terms)},
            )
            return {
                "participant_id": npc["id"],
                "action": action,
                "speech_act": plan.request.speech_act,
                "offer": {
                    "offer_id": new_offer["offer_id"],
                    "offer_revision": offer_revision,
                },
                "evidence_event_id": event_id,
            }

        if action == "reject" and active_offer:
            self._set_offer_status(connection, session["id"], active_offer, "rejected")
            state["active_offer"] = None
        other = self._other_participant(connection, session["id"], npc["id"])
        context.next_participant_id = other["id"]
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

    def _ensure_npc_intent(
        self,
        *,
        session_id: str,
        command_scope: str,
        idempotency_key: str,
        request_digest: str,
        pending_payload: dict[str, Any],
    ) -> NpcUtterancePlan:
        """Commit one authoritative NPC intent or resume its stable render job."""

        with self.database.write_transaction() as connection:
            existing = connection.execute(
                "SELECT plan_json, request_digest FROM npc_render_jobs "
                "WHERE command_scope = ? AND idempotency_key = ?",
                (command_scope, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    raise RuntimeError("NPC render job request digest mismatch")
                return utterance_plan_from_payload(_loads(existing["plan_json"]))

            pending = self._idempotency_result(
                connection, command_scope, idempotency_key, request_digest
            )
            if pending is None or pending.payload.get("_internal_result") != "npc_render_pending":
                raise RuntimeError("NPC render command is not pending")
            session = self._session_row(connection, session_id)
            participant_revision = int(pending_payload["participant_revision"])
            if int(session["revision"]) != participant_revision:
                raise RuntimeError("NPC intent revision compare-and-swap failed")
            npc = self._participant_row(connection, str(session["next_participant_id"]))
            if npc["controller"] != "built_in_npc":
                raise RuntimeError("Pending NPC intent has no built-in NPC actor")
            response_participant = self._participant_row(
                connection, str(pending_payload["response_participant_id"])
            )
            scenario = self._scenario_source(connection, session)
            state = _loads(session["state_json"])
            message_row = connection.execute(
                "SELECT content FROM messages WHERE session_id = ? AND participant_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (session_id, response_participant["id"]),
            ).fetchone()
            player_message = str(message_row["content"]) if message_row is not None else ""
            player_action = str(pending_payload.get("player_action", "inform"))
            action, speech_act, terms = self._npc_decision(
                scenario,
                state,
                npc,
                player_message,
                player_action,
                tuple(
                    turn.text
                    for turn in self._dialogue_context(
                        connection,
                        str(session["id"]),
                        str(npc["id"]),
                    )[:-1]
                ),
            )
            intent_revision = participant_revision + 1
            plan = self._build_utterance_plan(
                connection,
                session,
                npc,
                scenario,
                intent_revision=intent_revision,
                action=action,
                speech_act=speech_act,
                terms=terms,
                player_message=player_message,
            )
            context = TransitionContext(
                revision=participant_revision,
                round=int(session["round"]),
                substantive_turn_count=int(session["substantive_turn_count"]),
                status=str(session["status"]),
                next_participant_id=str(session["next_participant_id"]),
            )
            npc_action = self._commit_npc_authoritative_action(
                connection,
                session,
                npc,
                scenario,
                state,
                context,
                plan,
            )
            self._insert_event(
                connection,
                session_id,
                context.revision,
                npc["id"],
                "npc.intent.committed",
                {
                    "render_id": plan.render_id,
                    "action": plan.action,
                    "speech_act": plan.request.speech_act,
                    "requested_term_id": plan.request.requested_term_id,
                    "approved_terms": dict(plan.request.approved_terms),
                },
                {},
            )
            if (
                context.status == "active"
                and state["completed_rounds"] >= scenario["protocol"]["max_rounds"]
            ):
                context.status = "expired"
                context.next_participant_id = None
                self._close_active_offer(connection, session_id, state, "expired")
                self._insert_event(
                    connection,
                    session_id,
                    context.revision,
                    None,
                    "session.expired",
                    {"max_rounds": scenario["protocol"]["max_rounds"]},
                    {},
                )
            self._persist_session(connection, session, state, context, participant_revision)
            connection.execute(
                """
                INSERT INTO npc_render_jobs(
                    session_id, intent_revision, render_id, npc_participant_id,
                    response_participant_id, command_scope, idempotency_key,
                    request_digest, plan_json, prior_actions_json, npc_action_json,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    session_id,
                    intent_revision,
                    plan.render_id,
                    npc["id"],
                    response_participant["id"],
                    command_scope,
                    idempotency_key,
                    request_digest,
                    _json(utterance_plan_payload(plan)),
                    _json(pending_payload.get("prior_actions", [])),
                    _json(npc_action),
                ),
            )
            return plan

    def _claim_npc_render(self, plan: NpcUtterancePlan) -> ServiceResult | None:
        """Claim the only external render attempt for one durable NPC intent."""

        with self.database.write_transaction() as connection:
            job = connection.execute(
                "SELECT command_scope, idempotency_key, request_digest, status "
                "FROM npc_render_jobs WHERE render_id = ?",
                (plan.render_id,),
            ).fetchone()
            if job is None:
                raise RuntimeError("NPC render job was not found")
            if job["status"] == "delivered":
                repeated = self._idempotency_result(
                    connection,
                    str(job["command_scope"]),
                    str(job["idempotency_key"]),
                    str(job["request_digest"]),
                )
                if repeated is None or repeated.payload.get("_internal_result"):
                    raise RuntimeError("Delivered NPC render has no final idempotency result")
                return repeated
            claimed = connection.execute(
                "UPDATE npc_render_jobs SET render_started_at = CURRENT_TIMESTAMP "
                "WHERE render_id = ? AND status = 'pending' AND render_started_at IS NULL",
                (plan.render_id,),
            )
            if claimed.rowcount == 1:
                return None
            return ServiceResult(
                409,
                {
                    "error": "npc_render_pending",
                    "message": "The prior built-in NPC reply is still pending",
                    "revision": plan.intent_revision,
                    "render_id": plan.render_id,
                },
            )

    def _render_npc_plan(self, plan: NpcUtterancePlan) -> NpcDialogueResult:
        """Render outside database transactions and fail closed on injected exceptions."""

        supply_prose = plan.request.render_contract == "supply-dialogue-v1" and plan.action == "propose"
        if plan.action != "inform" and not supply_prose:
            return template_dialogue_result(
                plan.request,
                provider=getattr(self.dialogue_renderer, "provider", None),
                model=getattr(self.dialogue_renderer, "model", None),
            )
        try:
            result = self.dialogue_renderer.render(plan.request)
        except Exception:
            return template_dialogue_result(
                plan.request,
                provider=getattr(self.dialogue_renderer, "provider", None),
                model=getattr(self.dialogue_renderer, "model", None),
                fallback_used=True,
                failure_reason="renderer_failure",
            )
        if not isinstance(result, NpcDialogueResult):
            return template_dialogue_result(plan.request, fallback_used=True, failure_reason="renderer_failure")
        if any(
            secret in value
            for secret in self._known_redaction_secrets
            for value in (result.text, result.provider, result.model, result.failure_reason)
            if isinstance(value, str)
        ):
            return template_dialogue_result(
                plan.request,
                fallback_used=True,
                failure_reason="output_invalid",
            )
        return validated_dialogue_result(plan.request, result)

    def recover_pending_npc_renders(self) -> int:
        """Deliver deterministic fallbacks for durable jobs left pending by a restart."""

        with self.database.read_connection() as connection:
            rows = connection.execute(
                "SELECT scope, idempotency_key, request_digest, response_json "
                "FROM idempotency_results "
                "WHERE json_extract(response_json, '$._internal_result') = "
                "'npc_render_pending' AND scope != 'create_session' "
                "ORDER BY created_at, scope, idempotency_key"
            ).fetchall()
        recovered = 0
        for row in rows:
            pending_payload = _loads(row["response_json"])
            session_id = str(pending_payload["session_id"])
            with self.locks.for_session(session_id):
                plan = self._ensure_npc_intent(
                    session_id=session_id,
                    command_scope=str(row["scope"]),
                    idempotency_key=str(row["idempotency_key"]),
                    request_digest=str(row["request_digest"]),
                    pending_payload=pending_payload,
                )
                fallback = template_dialogue_result(
                    plan.request,
                    provider=getattr(self.dialogue_renderer, "provider", None),
                    model=getattr(self.dialogue_renderer, "model", None),
                    fallback_used=True,
                    failure_reason="restart_recovery",
                )
                self._deliver_npc_render(plan, fallback)
                recovered += 1
        return recovered

    def _safe_renderer_delivery(self, request: NpcDialogueRequest, rendered: NpcDialogueResult) -> NpcDialogueResult:
        rendered = validated_dialogue_result(request, rendered)
        if any(secret and secret in value for secret in self._known_redaction_secrets
               for value in (rendered.text, rendered.provider, rendered.model, rendered.failure_reason, rendered.validation_failure)
               if isinstance(value, str)):
            # Apply the same final boundary to initial output, normal delivery,
            # renderer exceptions, canonical actions, and restart recovery.
            return template_dialogue_result(request, fallback_used=True,
                                            failure_reason="output_invalid", validation_failure="credential")
        return rendered

    def _deliver_npc_render(
        self,
        plan: NpcUtterancePlan,
        rendered: NpcDialogueResult,
    ) -> ServiceResult:
        """CAS-deliver one rendered message for one durable NPC intent."""

        rendered = self._safe_renderer_delivery(plan.request, rendered)
        with self.database.write_transaction() as connection:
            job = connection.execute(
                "SELECT * FROM npc_render_jobs WHERE render_id = ?",
                (plan.render_id,),
            ).fetchone()
            if job is None:
                raise RuntimeError("NPC render job was not found")
            persisted_plan = utterance_plan_from_payload(_loads(job["plan_json"]))
            if _json(utterance_plan_payload(persisted_plan)) != _json(utterance_plan_payload(plan)):
                raise RuntimeError("NPC render plan compare-and-swap failed")
            if job["status"] == "delivered":
                repeated = self._idempotency_result(
                    connection,
                    str(job["command_scope"]),
                    str(job["idempotency_key"]),
                    str(job["request_digest"]),
                )
                if repeated is None or repeated.payload.get("_internal_result"):
                    raise RuntimeError("Delivered NPC render has no final idempotency result")
                return repeated

            session = self._session_row(connection, plan.session_id)
            if int(session["revision"]) != plan.intent_revision:
                raise RuntimeError("NPC render delivery revision compare-and-swap failed")
            npc = self._participant_row(connection, plan.npc_participant_id)
            response_participant = self._participant_row(
                connection, str(job["response_participant_id"])
            )
            self._insert_message(
                connection,
                plan.session_id,
                plan.intent_revision,
                npc,
                rendered.text,
                str(session["language"]),
            )
            renderer_metadata = rendered.public_metadata()
            self._insert_event(
                connection,
                plan.session_id,
                plan.intent_revision,
                npc["id"],
                "npc.utterance.delivered",
                {
                    "render_id": plan.render_id,
                    "speech_act": plan.request.speech_act,
                    "dialogue_renderer": renderer_metadata,
                    "requested_term_id": plan.request.requested_term_id,
                    "disclosed_reason_ids": [
                        reason_id for reason_id, text in plan.request.approved_reasons
                        if text in rendered.text
                    ],
                },
                {},
            )
            updated = connection.execute(
                "UPDATE npc_render_jobs SET status = 'delivered', "
                "renderer_metadata_json = ?, delivered_at = CURRENT_TIMESTAMP "
                "WHERE render_id = ? AND status = 'pending'",
                (_json(renderer_metadata), plan.render_id),
            )
            if updated.rowcount != 1:
                raise RuntimeError("NPC render delivery compare-and-swap failed")

            scenario = self._scenario_source(connection, session)
            state = _loads(session["state_json"])
            if state.get("training") and plan.request.training_context.get("personal_fact") and re.search(
                r"гуффи|goofy", rendered.text, re.I
            ):
                state["training"]["dog_disclosed"] = True
                connection.execute("UPDATE sessions SET state_json = ? WHERE id = ?", (_json(state), plan.session_id))
                session = self._session_row(connection, plan.session_id)
            self._capture_training_checkpoint(connection, session, state)
            context = TransitionContext(
                revision=int(session["revision"]),
                round=int(session["round"]),
                substantive_turn_count=int(session["substantive_turn_count"]),
                status=str(session["status"]),
                next_participant_id=session["next_participant_id"],
            )
            npc_action = _loads(job["npc_action_json"])
            npc_action["message"] = rendered.text
            npc_action["dialogue_renderer"] = renderer_metadata
            prior_actions = _loads(job["prior_actions_json"])
            committed_actions = [*prior_actions, npc_action]
            if job["command_scope"] == "create_session":
                raise RuntimeError("Session creation cannot use an NPC render job")
            result = ServiceResult(
                200,
                self._command_response(
                    connection,
                    plan.session_id,
                    response_participant,
                    scenario,
                    state,
                    context,
                    result=context.status if context.status != "active" else "turn_committed",
                    extra={"committed_actions": committed_actions},
                ),
            )
            if context.status in TERMINAL_STATUSES:
                self._generate_review(connection, session, scenario, state)
            self._replace_idempotency(
                connection,
                str(job["command_scope"]),
                str(job["idempotency_key"]),
                str(job["request_digest"]),
                result,
            )
            return result

    def _binding_violations(self, scenario: dict[str, Any], terms: dict[str, Any]) -> list[str]:
        violations = validate_terms(scenario, terms, complete=True)
        for role in scenario["roles"]:
            violations.extend(constraint_violations(scenario, role, terms))
        return sorted(set(violations))

    @staticmethod
    def _record_protocol_control(state: dict[str, Any]) -> int:
        count = int(state.get("consecutive_protocol_controls", 0)) + 1
        state["consecutive_protocol_controls"] = count
        return count

    @staticmethod
    def _protocol_control_limit(scenario: dict[str, Any]) -> int:
        return int(scenario["protocol"].get("max_consecutive_clarifications", 3))

    def _expire_protocol_controls(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        participant: sqlite3.Row,
        state: dict[str, Any],
        context: TransitionContext,
        reason: str,
        control_count: int,
    ) -> None:
        context.status = "expired"
        context.next_participant_id = None
        state["pending_confirmation"] = None
        state["pending_clarification"] = None
        self._close_active_offer(connection, session["id"], state, "closed_by_termination")
        self._insert_event(
            connection,
            session["id"],
            context.revision,
            participant["id"],
            "session.expired",
            {"reason": reason},
            {"consecutive_protocol_controls": control_count},
        )

    def _failed_transition(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        participant: sqlite3.Row,
        scenario: dict[str, Any],
        state: dict[str, Any],
        context: TransitionContext,
        initial_revision: int,
        message: str,
        code: str,
        description: str,
        status_code: int,
        extra: dict[str, Any] | None = None,
    ) -> ServiceResult:
        context.revision += 1
        self._insert_message(
            connection, session["id"], context.revision, participant, message, session["language"]
        )
        self._insert_event(
            connection,
            session["id"],
            context.revision,
            participant["id"],
            "domain_transition.failed",
            {"error": code},
            {"description": description, **(extra or {})},
        )
        protocol_control_count = self._record_protocol_control(state)
        terminal_reason: str | None = None
        if protocol_control_count >= self._protocol_control_limit(scenario):
            terminal_reason = "protocol_control_limit_reached"
            self._expire_protocol_controls(
                connection,
                session,
                participant,
                state,
                context,
                terminal_reason,
                protocol_control_count,
            )
        self._persist_session(connection, session, state, context, initial_revision)
        payload = {
            "error": code,
            "message": description,
            "revision": context.revision,
            "status": context.status,
            "next_actor": context.next_participant_id,
        }
        current = self._session_row(connection, session["id"])
        if context.status == "expired":
            self._generate_review(connection, current, scenario, state)
            payload["terminal_reason"] = terminal_reason
        payload["observation"] = self._observation(
            connection, current, participant, scenario, state
        )
        return ServiceResult(status_code, payload)

    def _advance_round(
        self,
        state: dict[str, Any],
        participant_id: str,
        context: TransitionContext,
        scenario: dict[str, Any],
        *,
        terminal: bool = False,
    ) -> None:
        actors: list[str] = state.setdefault("round_actor_ids", [])
        if participant_id not in actors:
            actors.append(participant_id)
        if set(actors) == set(state["participant_order"]):
            state["completed_rounds"] = int(state.get("completed_rounds", 0)) + 1
            state["round_actor_ids"] = []
        maximum = int(scenario["protocol"]["max_rounds"])
        context.round = min(maximum, int(state.get("completed_rounds", 0)) + 1)
        if terminal:
            context.round = min(maximum, max(1, context.round))

    # Projections and reviews ------------------------------------------

    @staticmethod
    def _benchmark_release_state(
        sessions: list[sqlite3.Row], run_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        run_id = run_metadata.get("benchmark_run_id")
        expected = run_metadata.get("benchmark_expected_trials")
        matching: list[tuple[sqlite3.Row, dict[str, Any]]] = []
        if run_id:
            for candidate in sessions:
                if candidate["run_mode"] != "benchmark":
                    continue
                candidate_metadata = _loads(candidate["run_metadata_json"])
                if candidate_metadata.get("benchmark_run_id") == run_id:
                    matching.append((candidate, candidate_metadata))
        trial_ids = {
            metadata.get("trial_id")
            for _session, metadata in matching
            if metadata.get("trial_id") is not None
        }
        expected_is_valid = (
            isinstance(expected, int) and not isinstance(expected, bool) and expected > 0
        )
        ready = bool(
            expected_is_valid
            and len(matching) == expected
            and len(trial_ids) == expected
            and all(candidate["status"] in TERMINAL_STATUSES for candidate, _metadata in matching)
            and all(
                metadata.get("benchmark_expected_trials") == expected
                for _candidate, metadata in matching
            )
        )
        return {
            "benchmark_run_id": run_id,
            "expected_trials": expected,
            "session_count": len(matching),
            "completed_count": sum(
                candidate["status"] in TERMINAL_STATUSES for candidate, _metadata in matching
            ),
            "trial_count": len(trial_ids),
            "release_ready": ready,
        }

    def get_review(self, session_id: str, token: str) -> ServiceResult:
        with self.database.read_connection() as connection:
            session, participant = self._authenticated_rows(connection, session_id, token)
            if session["status"] not in TERMINAL_STATUSES:
                return ServiceResult(
                    409,
                    {
                        "error": "review_not_ready",
                        "message": "A review is available only after session termination",
                        "revision": session["revision"],
                    },
                )
            if session["run_mode"] == "benchmark":
                scenario = self._scenario_source(connection, session)
                policy = scenario.get("review", {}).get("reveal_policy", {}).get("benchmark")
                if policy == "after_complete_run_set":
                    run_sessions = connection.execute(
                        "SELECT id, status, run_mode, run_metadata_json FROM sessions"
                    ).fetchall()
                    release = self._benchmark_release_state(
                        list(run_sessions), _loads(session["run_metadata_json"])
                    )
                    if not release["release_ready"]:
                        return ServiceResult(
                            409,
                            {
                                "error": "benchmark_review_sealed",
                                "message": (
                                    "Benchmark review data remains sealed until the complete "
                                    "declared run set is terminal"
                                ),
                                "revision": session["revision"],
                                "benchmark_run": release,
                            },
                        )
            row = connection.execute(
                "SELECT public_json, private_json FROM reviews WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise MissingResourceError("Review was not found")
            public = _loads(row["public_json"])
            private = _loads(row["private_json"])
            own = private["participant_scores"][participant["role"]]
            public["outcome"]["participant_utility"] = own["utility"]
            public["outcome"]["participant_utilities"] = {participant["role"]: own["utility"]}
            public["outcome"]["reservation_comparison"] = own["reservation_comparison"]
            public["skills"] = own["skills"]
            public["scores"] = {
                "outcome_score": own["outcome_score"],
                "skill_score": own["skill_score"],
            }
            public["outcome_score"] = own["outcome_score"]
            public["skill_score"] = own["skill_score"]
            public["recommendations"] = list(own.get("recommendations", []))
            public["assistance_usage"]["hints_used"] = own["hints_used"]
            public.update(self._training_review_projection(connection, session, participant, public))
            return ServiceResult(200, public)

    def aggregate_stats(self) -> dict[str, Any]:
        with self.database.read_connection() as connection:
            sessions = connection.execute(
                "SELECT id, scenario_id, scenario_version, status, language, difficulty, "
                "run_mode, run_metadata_json FROM sessions"
            ).fetchall()
            reviews = {
                row["session_id"]: _loads(row["private_json"])
                for row in connection.execute("SELECT session_id, private_json FROM reviews")
            }
            participants = connection.execute(
                "SELECT session_id, role, provenance_json FROM participants"
            ).fetchall()

        release_by_run: dict[str, dict[str, Any]] = {}
        for session in sessions:
            if session["run_mode"] != "benchmark":
                continue
            metadata = _loads(session["run_metadata_json"])
            run_id = metadata.get("benchmark_run_id")
            if run_id and run_id not in release_by_run:
                release_by_run[run_id] = self._benchmark_release_state(list(sessions), metadata)

        participant_by_session: dict[str, list[sqlite3.Row]] = {}
        for participant in participants:
            participant_by_session.setdefault(participant["session_id"], []).append(participant)

        records: list[dict[str, Any]] = []
        for session in sessions:
            review = reviews.get(session["id"])
            completed = session["status"] in TERMINAL_STATUSES
            agreement = session["status"] == "agreement_reached"
            metadata = _loads(session["run_metadata_json"])
            run_release = release_by_run.get(str(metadata.get("benchmark_run_id")))
            scores_released = session["run_mode"] != "benchmark" or bool(
                run_release and run_release["release_ready"]
            )
            participant_scores = (
                (review or {}).get("participant_scores", {}) if scores_released else {}
            )
            score_rows = list(participant_scores.values())
            aggregate = {
                "completed": completed,
                "agreement": agreement if scores_released else None,
                "outcome": fmean(row["outcome_score"] for row in score_rows)
                if score_rows
                else None,
                "skill": fmean(row["skill_score"] for row in score_rows) if score_rows else None,
                "utility": fmean(row["utility"] for row in score_rows) if score_rows else None,
            }
            records.append(
                {
                    **aggregate,
                    "scenario": f"{session['scenario_id']}@{session['scenario_version']}",
                    "language": session["language"],
                    "difficulty": session["difficulty"],
                    "session_id": session["id"],
                    "run_metadata": metadata,
                    "scores_released": scores_released,
                }
            )

        model_records: list[dict[str, Any]] = []
        by_session = {record["session_id"]: record for record in records}
        for participant in participants:
            base = by_session[participant["session_id"]]
            provenance = _loads(participant["provenance_json"])
            review = reviews.get(participant["session_id"], {})
            role_score = (
                review.get("participant_scores", {}).get(participant["role"])
                if base["scores_released"]
                else None
            )
            model_records.append(
                {
                    "session_id": participant["session_id"],
                    "model": "/".join(
                        value
                        for value in (provenance.get("provider"), provenance.get("model"))
                        if value
                    )
                    or "unspecified",
                    "prompt_version": provenance.get("prompt_version"),
                    "completed": base["completed"],
                    "agreement": base["agreement"],
                    "outcome": role_score.get("outcome_score") if role_score else None,
                    "skill": role_score.get("skill_score") if role_score else None,
                    "utility": role_score.get("utility") if role_score else None,
                }
            )

        summary_groups = self._aggregate_group(records, lambda _record: "all")
        summary = (
            summary_groups[0]
            if summary_groups
            else {
                "key": "all",
                "session_count": 0,
                "completed_count": 0,
                "agreement_rate": None,
                "avg_outcome_score": None,
                "avg_skill_score": None,
            }
        )
        groups = {
            "by_model": self._aggregate_group(model_records, lambda record: record["model"]),
            "by_scenario": self._aggregate_group(records, lambda record: record["scenario"]),
            "by_language": self._aggregate_group(records, lambda record: record["language"]),
            "by_difficulty": self._aggregate_group(records, lambda record: record["difficulty"]),
        }
        labels = {
            "by_model": "model",
            "by_scenario": "scenario",
            "by_language": "language",
            "by_difficulty": "difficulty",
        }
        for group_name, rows in groups.items():
            for row in rows:
                row[labels[group_name]] = row["key"]
        totals = {
            "total_sessions": summary["session_count"],
            "completed_sessions": summary["completed_count"],
            "agreements": sum(
                1 for record in records if record["completed"] and record["agreement"]
            ),
            "agreement_rate": summary["agreement_rate"],
            "avg_outcome_score": summary["avg_outcome_score"],
            "avg_skill_score": summary["avg_skill_score"],
        }
        benchmark_runs: dict[str, dict[str, Any]] = {}
        for record in records:
            metadata = record["run_metadata"]
            run_id = metadata.get("benchmark_run_id")
            if not run_id:
                continue
            entry = benchmark_runs.setdefault(
                run_id,
                {
                    "benchmark_run_id": run_id,
                    "session_count": 0,
                    "completed_count": 0,
                    "trial_ids": [],
                    "seeds": [],
                },
            )
            entry["session_count"] += 1
            entry["completed_count"] += int(record["completed"])
            if metadata.get("trial_id") is not None:
                entry["trial_ids"].append(metadata["trial_id"])
            if metadata.get("seed") is not None:
                entry["seeds"].append(metadata["seed"])
        for entry in benchmark_runs.values():
            entry["trial_ids"] = sorted(set(entry["trial_ids"]))
            entry["seeds"] = sorted(set(entry["seeds"]))
            release = release_by_run.get(entry["benchmark_run_id"])
            if release:
                entry.update(
                    expected_trials=release["expected_trials"],
                    trial_count=release["trial_count"],
                    release_ready=release["release_ready"],
                )
        return {
            "totals": totals,
            **groups,
            "benchmark_runs": list(benchmark_runs.values()),
            "privacy": {
                "minimum_completed_group_size": self.MIN_PUBLIC_STATS_GROUP_SIZE,
                "suppressed_fields": ["utility"],
            },
        }

    def _aggregate_group(
        self, records: list[dict[str, Any]], key_function: Any
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            groups.setdefault(str(key_function(record)), []).append(record)
        output: list[dict[str, Any]] = []
        for key, group in sorted(groups.items()):
            completed = [record for record in group if record["completed"]]
            session_ids = {record["session_id"] for record in group if record.get("session_id")}
            completed_ids = {
                record["session_id"] for record in completed if record.get("session_id")
            }
            rated = [record for record in completed if record.get("agreement") is not None]
            scores_visible = len(completed) >= self.MIN_PUBLIC_STATS_GROUP_SIZE
            output.append(
                {
                    "key": key,
                    "session_count": len(session_ids) if session_ids else len(group),
                    "seat_count": len(group),
                    "completed_count": len(completed_ids) if completed_ids else len(completed),
                    "agreement_rate": round(
                        sum(bool(record["agreement"]) for record in rated) / len(rated), 4
                    )
                    if rated
                    else None,
                    "avg_outcome_score": round(
                        fmean(
                            record["outcome"]
                            for record in completed
                            if record["outcome"] is not None
                        ),
                        4,
                    )
                    if scores_visible and any(record["outcome"] is not None for record in completed)
                    else None,
                    "avg_skill_score": round(
                        fmean(
                            record["skill"] for record in completed if record["skill"] is not None
                        ),
                        4,
                    )
                    if scores_visible and any(record["skill"] is not None for record in completed)
                    else None,
                }
            )
        return output

    def _generate_review(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        scenario: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        if connection.execute(
            "SELECT 1 FROM reviews WHERE session_id = ?", (session["id"],)
        ).fetchone():
            return
        agreement = state.get("agreement_offer")
        terms = agreement["terms"] if agreement else None
        participant_scores: dict[str, dict[str, Any]] = {}
        participant_ids = {
            row["role"]: row["id"]
            for row in connection.execute(
                "SELECT id, role FROM participants WHERE session_id = ?", (session["id"],)
            )
        }
        hint_counts: dict[str, int] = {role: 0 for role in scenario["roles"]}
        for row in connection.execute(
            "SELECT public_payload_json FROM events WHERE session_id = ? AND type = 'hint.delivered'",
            (session["id"],),
        ):
            audience = _loads(row["public_payload_json"]).get("audience_participant_id")
            for role, participant_id in participant_ids.items():
                if participant_id == audience:
                    hint_counts[role] += 1
        message_rows = connection.execute(
            "SELECT session_revision, participant_id, content FROM messages "
            "WHERE session_id = ? ORDER BY id",
            (session["id"],),
        ).fetchall()
        walked_away_by = connection.execute(
            "SELECT participant_id FROM events WHERE session_id = ? "
            "AND type = 'session.walked_away' LIMIT 1",
            (session["id"],),
        ).fetchone()
        walked_away_participant = walked_away_by["participant_id"] if walked_away_by else None
        action_rows = connection.execute(
            "SELECT participant_id, type, private_payload_json FROM events "
            "WHERE session_id = ? ORDER BY id",
            (session["id"],),
        ).fetchall()
        defined_term_count = max(1, len(scenario["terms"]["definitions"]))
        for role in scenario["roles"]:
            model = scenario["utility_model"]["role_models"][role]
            reservation = float(model["reservation_utility"])
            batna_utility = float(scenario["roles"][role]["batna"]["utility"])
            utility = evaluate_utility(scenario, role, terms) if terms else batna_utility
            comparison = "at_or_above" if utility >= reservation else "below"
            participant_id = participant_ids[role]
            role_messages = [
                row["content"] for row in message_rows if row["participant_id"] == participant_id
            ]
            role_actions = [
                row["type"] for row in action_rows if row["participant_id"] == participant_id
            ]
            role_term_deltas = [
                _loads(row["private_payload_json"]).get("term_delta", {})
                for row in action_rows
                if row["participant_id"] == participant_id
                and row["type"] in {"offer.created", "offer.countered", "proposal.revised"}
            ]
            question_count = sum(action == "participant.question" for action in role_actions)
            clarification_count = sum(action == "clarification.required" for action in role_actions)
            conditional_count = sum(
                any(
                    marker in message.casefold()
                    for marker in (
                        "если",
                        "при условии",
                        "в обмен",
                        " if ",
                        "provided that",
                        "in exchange",
                    )
                )
                for message in role_messages
            )
            maximum_breadth = max(
                (
                    len(term_delta)
                    for term_delta in role_term_deltas
                    if isinstance(term_delta, dict)
                ),
                default=0,
            )
            skills = {
                "probing": min(100.0, 35.0 * question_count),
                "package_design": round(100.0 * maximum_breadth / defined_term_count, 4),
                "clarity": max(0.0, 100.0 - 25.0 * clarification_count),
                "conditional_trading": min(100.0, 50.0 * conditional_count),
            }
            raw_skill = fmean(skills.values())
            skill_score = max(0.0, round(raw_skill - 5.0 * hint_counts[role], 4))
            participant_scores[role] = {
                "utility": utility,
                "reservation_utility": reservation,
                "reservation_comparison": comparison,
                "outcome_score": utility,
                "skill_score": skill_score,
                "skills": skills,
                "hints_used": hint_counts[role],
                "recommendations": _review_recommendations(
                    str(session["language"]),
                    status=str(session["status"]),
                    skills=skills,
                    agreement=bool(agreement),
                    utility=utility,
                    reservation=reservation,
                    walked_away_self=walked_away_participant == participant_id,
                ),
            }
            if is_supply_scenario(scenario):
                # Progressive package construction is intentional, not a failure to make all terms at once.
                participant_scores[role]["recommendations"] = [
                    item for item in participant_scores[role]["recommendations"] if item["skill"] != "package_design"
                ]
                for item in participant_scores[role]["recommendations"]:
                    if item["skill"] == "clarity":
                        item["text"] = ("Уточняйте, к какой партии относится оплата и какой результат диагностики определяет доплату."
                                        if session["language"] == "ru" else
                                        "Specify which lot each payment covers and which diagnostic outcome determines the extra charge.")
        event_rows = connection.execute(
            "SELECT event_id, type, participant_id, session_revision, public_payload_json "
            "FROM events WHERE session_id = ? "
            "AND type IN ('proposal.created', 'proposal.revised', 'offer.created', 'offer.countered', 'agreement.reached', "
            "'session.walked_away', 'session.expired') ORDER BY id",
            (session["id"],),
        ).fetchall()
        role_by_participant = {
            participant_id: role for role, participant_id in participant_ids.items()
        }
        quotes = {
            (row["participant_id"], int(row["session_revision"])): str(row["content"])
            for row in message_rows
        }
        language = str(session["language"])
        key_moments: list[dict[str, Any]] = []
        for row in event_rows:
            payload = _loads(row["public_payload_json"])
            actor_role = role_by_participant.get(row["participant_id"])
            moment: dict[str, Any] = {
                "event_id": row["event_id"],
                "type": row["type"],
                "title": _KEY_MOMENT_TITLES.get(language, _KEY_MOMENT_TITLES["en"]).get(
                    row["type"], row["type"].replace(".", " ").replace("_", " ").title()
                ),
                "summary": _key_moment_summary(
                    language, row["type"], actor_role, payload, scenario
                ),
            }
            # Revision zero contains an authored opening artifact and a social greeting.
            # The greeting is not evidence that the NPC uttered or changed the opening terms.
            quote = (quotes.get((row["participant_id"], int(row["session_revision"])))
                     if int(row["session_revision"]) > 0 else None)
            if quote:
                excerpt = " ".join(quote.split())
                if len(excerpt) > 160:
                    excerpt = excerpt[:157].rstrip() + "…"
                moment["detail"] = f"«{excerpt}»" if language == "ru" else f"“{excerpt}”"
            key_moments.append(moment)
        public = {
            "session_id": session["id"],
            "revision": session["revision"],
            "outcome": {
                "agreement": session["status"] == "agreement_reached",
                "termination_reason": session["status"],
                "agreement_terms": terms,
            },
            "assistance_usage": {
                "mode": session["difficulty"],
                "hints_enabled": bool(session["hints_enabled"]),
                "hints_used": 0,
            },
            "key_moments": key_moments,
            "scoring_version": "deterministic-rubric-v1",
        }
        if is_supply_scenario(scenario):
            public["negotiation_contract_version"] = "supply-package-v1"
            if terms:
                public["outcome"]["financial_summary"] = supply_financial_summary(scenario, terms)
        private = {"participant_scores": participant_scores}
        connection.execute(
            "INSERT INTO reviews(session_id, terminal_revision, public_json, private_json) "
            "VALUES (?, ?, ?, ?)",
            (session["id"], session["revision"], _json(public), _json(private)),
        )

    def _observation(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        participant: sqlite3.Row,
        scenario: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        messages = [
            {
                "revision": row["session_revision"],
                "participant_id": row["participant_id"],
                "role": row["role"],
                "message": row["content"],
            }
            for row in connection.execute(
                "SELECT session_revision, participant_id, role, content FROM messages "
                "WHERE session_id = ? ORDER BY id",
                (session["id"],),
            )
        ]
        role_by_participant = {
            row["id"]: row["role"]
            for row in connection.execute(
                "SELECT id, role FROM participants WHERE session_id = ?", (session["id"],)
            )
        }
        active_offers = []
        if state.get("active_offer"):
            offer = state["active_offer"]
            active_offers.append(
                {
                    "offer_id": offer["offer_id"],
                    "offer_revision": offer["offer_revision"],
                    "proposer_role": role_by_participant[offer["proposer_participant_id"]],
                    "terms": offer["terms"],
                    "unresolved_required_terms": [
                        term
                        for term in scenario["terms"]["required_term_ids"]
                        if term not in offer["terms"]
                    ],
                }
            )
        assistance = self._assistance(session, participant, scenario, messages)
        hint_rows = connection.execute(
            "SELECT event_id, public_payload_json FROM events "
            "WHERE session_id = ? AND type = 'hint.delivered' "
            "ORDER BY id",
            (session["id"],),
        ).fetchall()
        hints: list[dict[str, Any]] = []
        for row in hint_rows:
            payload = _loads(row["public_payload_json"])
            if payload.get("audience_participant_id") != participant["id"]:
                continue
            hints.append(
                {
                    "event_id": row["event_id"],
                    "id": payload.get("id"),
                    "level": payload.get("level"),
                    "text": payload.get("text"),
                }
            )
        distractor_ids = set(state.get("delivered_distractors", {}).get(participant["id"], []))
        context = [
            {"id": item["id"], "type": item["type"], "content": item["content"]}
            for item in scenario.get("distractors", [])
            if item["id"] in distractor_ids
        ]
        training_view = None
        if state.get("training"):
            training_view = training_observation(state["training"], participant["id"])
            if state["training"].get("owner_id") == participant["id"]:
                training_view["rewind"] = self._training_rewind_status(
                    connection, session, state
                )
        return {
            "participant_id": participant["id"],
            "role": participant["role"],
            "role_brief": self._role_brief(scenario, participant["role"], session["language"]),
            "currency": scenario["currency"],
            "conversation": messages,
            "active_offers": active_offers,
            "assistance": assistance,
            "hints": hints,
            "remaining_hints": max(0, self.MAX_HINTS_PER_PARTICIPANT - len(hints)),
            "hints_available": len(hints) < self.MAX_HINTS_PER_PARTICIPANT,
            "context": context,
            "status": session["status"],
            "revision": session["revision"],
            "round": session["round"],
            "substantive_turn_count": session["substantive_turn_count"],
            "next_actor": session["next_participant_id"],
            "language": session["language"],
            **({"training": training_view} if training_view is not None else {}),
            **self._supply_observation(scenario, state),
        }

    @staticmethod
    def _role_brief(scenario: dict[str, Any], role: str, language: str) -> dict[str, Any]:
        role_data = scenario["roles"][role]
        brief = role_data.get("brief", {})
        brief = brief if isinstance(brief, dict) else {}

        legacy_text = brief.get("text")
        if isinstance(legacy_text, dict):
            legacy_text = legacy_text.get(language)
        if isinstance(legacy_text, str):
            summary = legacy_text
        elif language == "en":
            summary = f"You represent {role_data['company']}."
        else:
            summary = f"Вы представляете компанию {role_data['company']}."

        objective = brief.get("objective")
        if isinstance(objective, str):
            objectives = [objective]
        elif isinstance(objective, list):
            objectives = [item for item in objective if isinstance(item, str)]
        else:
            objectives = []

        context = brief.get("context")
        if not isinstance(context, str):
            context = ""

        batna = role_data.get("batna", {})
        batna_description = batna.get("description") if isinstance(batna, dict) else None
        if not isinstance(batna_description, str):
            batna_description = ""

        constraints = {
            key: value
            for key, value in role_data.get("constraints", {}).items()
            if key != "reservation_utility"
        }
        interests = role_data.get("interests", {})
        interest_order = sorted(
            interests,
            key=lambda key: (
                interests[key].get("weight", 0) if isinstance(interests[key], dict) else 0
            ),
            reverse=True,
        )
        return {
            "summary": summary,
            "objectives": objectives,
            "context": context,
            "batna": batna_description,
            "constraints": constraints,
            "priorities": interest_order,
        }

    @staticmethod
    def _assistance(
        session: sqlite3.Row,
        participant: sqlite3.Row,
        scenario: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        difficulty = session["difficulty"]
        if difficulty not in {"guided", "easy"}:
            return None
        own_priorities = list(scenario["roles"][participant["role"]]["interests"])
        public_text = " ".join(
            item["message"].casefold()
            for item in messages
            if item["participant_id"] != participant["id"] and int(item["revision"]) > 0
        )
        signals: list[str] = []
        if any(token in public_text for token in ("предоплат", "аванс", "prepay", "payment")):
            signals.append("payment_terms_repeated")
        if any(token in public_text for token in ("достав", "постав", "delivery")):
            signals.append("delivery_terms_repeated")
        if any(token in public_text for token in ("цена", "стоим", "price")):
            signals.append("price_terms_repeated")
        result: dict[str, Any] = {
            "mode": difficulty,
            "own_priorities": own_priorities,
            "detected_signals": signals,
        }
        if difficulty == "guided":
            result["coaching"] = (
                "Проверьте интерес вопросом и обменивайте уступку только на встречное условие."
                if session["language"] == "ru"
                else "Test the interest with a question and trade each concession for a return condition."
            )
        else:
            result["probable_interests"] = [signal.removesuffix("_repeated") for signal in signals]
        return result

    # Storage helpers ---------------------------------------------------

    def _command_response(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        participant: sqlite3.Row,
        scenario: dict[str, Any],
        state: dict[str, Any],
        context: TransitionContext,
        *,
        result: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self._session_row(connection, session_id)
        return {
            "result": result,
            "session_id": session_id,
            "round": context.round,
            "substantive_turn_count": context.substantive_turn_count,
            "revision": context.revision,
            "status": context.status,
            "next_actor": context.next_participant_id,
            **(extra or {}),
            **supply_envelope(scenario, state, participant["id"]),
            "observation": self._observation(connection, session, participant, scenario, state),
        }

    def _persist_session(
        self,
        connection: sqlite3.Connection,
        session: sqlite3.Row,
        state: dict[str, Any],
        context: TransitionContext,
        initial_revision: int,
    ) -> None:
        if context.status in TERMINAL_STATUSES and "pending_offer_publication" in state:
            state["pending_offer_publication"] = None
            if state.get("preliminary_proposal"):
                state["preliminary_proposal"]["status"] = "closed"
        cursor = connection.execute(
            """
            UPDATE sessions
            SET status = ?, revision = ?, round = ?, substantive_turn_count = ?,
                next_participant_id = ?, state_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND revision = ?
            """,
            (
                context.status,
                context.revision,
                context.round,
                context.substantive_turn_count,
                context.next_participant_id,
                _json(state),
                session["id"],
                initial_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Optimistic session revision update failed")

    @staticmethod
    def _grounded_opening_request(
        scenario: dict[str, Any],
        npc_role: str,
        opening_terms: dict[str, Any],
        language: str,
        training_setup: Any,
    ) -> GroundedOpeningRequest | None:
        strategy = scenario["roles"][npc_role].get("dialogue_strategy")
        if not strategy:
            return None
        setup = training_setup.model_dump(mode="json") if training_setup is not None else {}
        relationship = str(setup.get("relationship", "first_meeting"))
        player_name = redact_untrusted_credentials(str(setup.get("player_name", ""))).strip()
        player_background = redact_untrusted_credentials(
            str(setup.get("shared_background", ""))
        ).strip()
        shared_parts = [str(strategy["shared_context"]).strip()]
        if relationship == "successful_history" and strategy.get("successful_history_context"):
            shared_parts.append(str(strategy["successful_history_context"]).strip())
        shared_context = " ".join(shared_parts)
        selected_terms = {
            term_id: opening_terms[term_id]
            for term_id in strategy["opening_term_ids"]
        }
        formatted_terms = format_terms(selected_terms, scenario=scenario, language=language)
        if language == "ru":
            public_position = formatted_terms
            if relationship == "successful_history":
                introduction = "Рад снова с вами работать."
            else:
                introduction = "Рад познакомиться и обсудить условия."
            name_prefix = f"{OPENING_NAME_TOKEN}, добрый день." if player_name else "Добрый день."
            fallback_template = (
                f"{name_prefix} {introduction} Как вы видели в нашем предложении по теме "
                f"«{OPENING_TITLE_TOKEN}», {OPENING_POSITION_TOKEN}. "
                f"{strategy['shared_context']} Подходит ли вам предложенная основа, "
                "и какое условие вы хотите обсудить первым?"
            )
        else:
            public_position = formatted_terms
            if relationship == "successful_history":
                introduction = "I am glad to work with you again."
            else:
                introduction = "I am glad to meet you and discuss the terms."
            name_prefix = f"Good afternoon, {OPENING_NAME_TOKEN}." if player_name else "Good afternoon."
            fallback_template = (
                f"{name_prefix} {introduction} As shown in our proposal for "
                f"{OPENING_TITLE_TOKEN}, {OPENING_POSITION_TOKEN}. "
                f"{strategy['shared_context']} Is this a workable basis, and which term "
                "would you like to discuss first?"
            )
        return GroundedOpeningRequest(
            language=language,
            scenario_title=str(scenario["title"]),
            npc_role=npc_role,
            player_name=player_name,
            relationship=relationship,
            shared_scenario_context=shared_context,
            untrusted_player_background=player_background,
            opening_goal=str(strategy["opening_goal"]),
            public_position=public_position,
            conversation_style=str(
                scenario["roles"][npc_role].get("conversation_style", "pragmatic")
            ),
            fallback_template=fallback_template,
            methodology_version=METHODOLOGY_VERSION,
        )

    @staticmethod
    def _initial_npc_greeting(
        title: str,
        language: str,
        *,
        session_id: str = "",
        relationship: str = "first_meeting",
    ) -> str:
        if relationship == "successful_history":
            greeting_language = language if language in SUCCESSFUL_HISTORY_GREETINGS else "en"
            templates = SUCCESSFUL_HISTORY_GREETINGS[greeting_language]
            selection_key = "\x1f".join(
                (
                    RELATIONSHIP_GREETING_VERSION,
                    session_id,
                    greeting_language,
                    title,
                    relationship,
                )
            )
            selection_digest = hashlib.sha256(selection_key.encode("utf-8")).digest()
            index = int.from_bytes(selection_digest[:8], "big") % len(templates)
            return templates[index].format(title=title)
        if language == "ru":
            return f"Здравствуйте. Давайте обсудим «{title}». Слушаю вас."
        return f'Hello. I am ready to discuss "{title}". Please go ahead.'

    @staticmethod
    def _insert_message(
        connection: sqlite3.Connection,
        session_id: str,
        revision: int,
        participant: sqlite3.Row,
        content: str,
        language: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO messages(
                session_id, session_revision, participant_id, role, content, language
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, revision, participant["id"], participant["role"], content, language),
        )

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        session_id: str,
        revision: int,
        participant_id: str | None,
        event_type: str,
        public_payload: dict[str, Any],
        private_payload: dict[str, Any],
    ) -> str:
        event_id = _event_id()
        connection.execute(
            """
            INSERT INTO events(
                event_id, session_id, session_revision, participant_id, type,
                public_payload_json, private_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                session_id,
                revision,
                participant_id,
                event_type,
                _json(public_payload),
                _json(private_payload),
            ),
        )
        return event_id

    @staticmethod
    def _set_offer_status(
        connection: sqlite3.Connection,
        session_id: str,
        offer: dict[str, Any],
        status: str,
    ) -> None:
        connection.execute(
            "UPDATE offers SET status = ? WHERE session_id = ? AND offer_id = ? "
            "AND offer_revision = ?",
            (status, session_id, offer["offer_id"], offer["offer_revision"]),
        )
        offer["status"] = status

    def _close_active_offer(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        state: dict[str, Any],
        status: str,
    ) -> None:
        active = state.get("active_offer")
        if active:
            self._set_offer_status(connection, session_id, active, status)
            state["active_offer"] = None

    @staticmethod
    def _session_row(connection: sqlite3.Connection, session_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise MissingResourceError("Session was not found")
        return row

    @staticmethod
    def _participant_row(connection: sqlite3.Connection, participant_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM participants WHERE id = ?", (participant_id,)
        ).fetchone()
        if row is None:
            raise MissingResourceError("Participant was not found")
        return row

    @staticmethod
    def _other_participant(
        connection: sqlite3.Connection, session_id: str, participant_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM participants WHERE session_id = ? AND id != ?",
            (session_id, participant_id),
        ).fetchone()
        if row is None:
            raise MissingResourceError("Counterparty was not found")
        return row

    def _authenticated_rows(
        self, connection: sqlite3.Connection, session_id: str, token: str
    ) -> tuple[sqlite3.Row, sqlite3.Row]:
        session = self._session_row(connection, session_id)
        participant = connection.execute(
            "SELECT * FROM participants WHERE session_id = ? AND token_hash = ?",
            (session_id, _token_hash(token)),
        ).fetchone()
        if participant is None:
            raise AuthenticationError("The participant credential is invalid for this session")
        return session, participant

    @staticmethod
    def _scenario_source(connection: sqlite3.Connection, session: sqlite3.Row) -> dict[str, Any]:
        row = connection.execute(
            "SELECT source_json FROM scenario_versions WHERE scenario_id = ? AND version = ?",
            (session["scenario_id"], session["scenario_version"]),
        ).fetchone()
        if row is None:
            raise MissingResourceError("Pinned scenario version was not found")
        return _loads(row["source_json"])

    def _idempotency_result(
        self,
        connection: sqlite3.Connection,
        scope: str,
        key: str,
        request_digest: str,
    ) -> ServiceResult | None:
        row = connection.execute(
            "SELECT request_digest, status_code, response_json FROM idempotency_results "
            "WHERE scope = ? AND idempotency_key = ?",
            (scope, key),
        ).fetchone()
        if row is None:
            return None
        if row["request_digest"] != request_digest:
            return ServiceResult(
                409,
                {
                    "error": "idempotency_key_reused",
                    "message": "The idempotency key was already used with a different request",
                },
            )
        return ServiceResult(int(row["status_code"]), _loads(row["response_json"]))

    @staticmethod
    def _pending_render_result(
        connection: sqlite3.Connection,
        session_id: str,
        revision: int,
    ) -> ServiceResult | None:
        row = connection.execute(
            "SELECT render_id FROM npc_render_jobs "
            "WHERE session_id = ? AND status = 'pending' LIMIT 1",
            (session_id,),
        ).fetchone()
        pending_handoff = connection.execute(
            "SELECT 1 FROM idempotency_results "
            "WHERE json_extract(response_json, '$._internal_result') = "
            "'npc_render_pending' "
            "AND json_extract(response_json, '$.session_id') = ? LIMIT 1",
            (session_id,),
        ).fetchone()
        if row is None and pending_handoff is None:
            return None
        payload: dict[str, Any] = {
            "error": "npc_render_pending",
            "message": "The prior built-in NPC reply is still pending",
            "revision": revision,
        }
        if row is not None:
            payload["render_id"] = row["render_id"]
        return ServiceResult(
            409,
            payload,
        )

    def _save_idempotency(
        self,
        connection: sqlite3.Connection,
        scope: str,
        key: str,
        request_digest: str,
        result: ServiceResult,
        *,
        contains_credentials: bool = False,
    ) -> None:
        persisted_payload = result.payload
        if contains_credentials:
            persisted_payload = {
                name: value
                for name, value in result.payload.items()
                if name not in {"participant_credentials", "participant_token"}
            }
            persisted_payload["credential_delivery"] = "initial_response_only"
        connection.execute(
            """
            INSERT INTO idempotency_results(
                scope, idempotency_key, request_digest, status_code, response_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (scope, key, request_digest, result.status_code, _json(persisted_payload)),
        )

    @staticmethod
    def _replace_idempotency(
        connection: sqlite3.Connection,
        scope: str,
        key: str,
        request_digest: str,
        result: ServiceResult,
        *,
        contains_credentials: bool = False,
    ) -> None:
        persisted_payload = result.payload
        if contains_credentials:
            persisted_payload = {
                name: value
                for name, value in result.payload.items()
                if name not in {"participant_credentials", "participant_token"}
            }
            persisted_payload["credential_delivery"] = "initial_response_only"
        updated = connection.execute(
            "UPDATE idempotency_results SET status_code = ?, response_json = ? "
            "WHERE scope = ? AND idempotency_key = ? AND request_digest = ?",
            (result.status_code, _json(persisted_payload), scope, key, request_digest),
        )
        if updated.rowcount != 1:
            raise RuntimeError("Idempotency result compare-and-swap failed")
