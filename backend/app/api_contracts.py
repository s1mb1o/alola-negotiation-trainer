"""HTTP projections only. These contracts do not expose domain or storage state."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from .models import Controller, Difficulty, RunMode
from .training import Preparation, Target

Count = Annotated[int, Field(ge=0)]
Version = Annotated[int, Field(ge=1)]
Language = Literal["ru", "en"]
SessionStatus = Literal[
    "active", "agreement_reached", "walked_away", "expired", "aborted", "technical_failure"
]
PublicTerms = Annotated[
    dict[str, JsonValue],
    Field(
        description="Public term values keyed by authored term ID. The pinned scenario grammar "
        "validates scalar and composite values. Omitted terms remain UNSPECIFIED."
    ),
]
PublicPayload = Annotated[
    dict[str, JsonValue],
    Field(
        description="Versioned, actor-safe event payload selected by event type. "
        "Internal event payloads are never included."
    ),
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(Contract):
    status: Literal["ok"]
    database: Literal["sqlite"]
    journal_mode: str
    scenario_count: Count


class LlmTraceSummary(Contract):
    trace_id: str
    session_id: str
    task: Literal[
        "npc_dialogue",
        "npc_opening",
        "npc_grounding",
        "social",
        "coaching",
        "player_assist",
        "supply_extraction",
    ]
    provider: str
    model: str
    started_at: str
    status: Literal["running", "completed", "error"]
    duration_ms: float | None
    error_type: str | None
    http_status: int | None
    retry_count: Count
    usage: dict[str, int | float]
    request_truncated: bool
    response_truncated: bool


class LlmTraceMessage(Contract):
    model_config = ConfigDict(extra="allow")
    role: str
    content: str


class LlmTraceParameters(Contract):
    max_output_tokens: int
    temperature: float | None
    enable_thinking: bool | None
    timeout_seconds: float
    max_attempts: int
    seed: int | None
    retry_backoff_seconds: float


class LlmTraceRequest(Contract):
    attempt: int = Field(ge=1)
    method: Literal["POST"]
    url: str
    headers: dict[str, str]
    body: dict[str, JsonValue]
    timeout_seconds: float


class LlmTraceDetail(LlmTraceSummary):
    instructions: str
    messages: list[LlmTraceMessage]
    response: str | None
    parameters: LlmTraceParameters
    requests: list[LlmTraceRequest]


class LlmTraceListResponse(Contract):
    enabled: bool
    capacity: Count
    capacity_bytes: Count
    items: list[LlmTraceSummary]


class ScenarioRole(Contract):
    role: str
    company: str


class TrainingTerm(Contract):
    term_id: str
    label: str


class ScenarioResponse(Contract):
    id: str
    version: Version
    title: str
    language: Language
    currency: str
    max_rounds: Version
    roles: list[ScenarioRole]
    opening_offer_role: str
    opening_kind: Literal["opening_offer", "opening_position"]
    negotiable_terms: list[str]
    scenario_content_digest: str
    scenario_compiler_version: str
    compiled_scenario_digest: str
    training_terms: list[TrainingTerm]
    negotiation_contract_version: str | None = None


class ScenarioListResponse(Contract):
    items: list[ScenarioResponse]
    count: Count


class Participant(Contract):
    participant_id: str
    role: str
    controller: Controller


class ParticipantCredential(Contract):
    participant_id: str
    role: str
    token: str = Field(description="Session-scoped credential. Delivered once. Store privately.")


class RoleBrief(Contract):
    summary: str
    objectives: list[str]
    context: str
    batna: str
    constraints: dict[str, JsonValue] = Field(
        description="The authenticated role's authored constraints."
    )
    priorities: list[str]


class ConversationTurn(Contract):
    revision: Count
    participant_id: str | None
    role: str
    message: str


class PublicOffer(Contract):
    offer_id: str
    offer_revision: Version
    proposer_role: str
    terms: PublicTerms
    unresolved_required_terms: list[str]


class PreliminaryProposal(Contract):
    proposal_id: str
    proposal_revision: Version
    proposer_participant_id: str
    proposer_role: str
    terms: PublicTerms
    status: str
    source_event_ids: list[str]
    unresolved_required_terms: list[str]


class Assistance(Contract):
    mode: Literal["guided", "easy"]
    own_priorities: list[str]
    detected_signals: list[str]
    coaching: str | None = None
    probable_interests: list[str] | None = None


class Hint(Contract):
    event_id: str
    id: str
    level: Annotated[int, Field(ge=1, le=3)]
    text: str


class ContextItem(Contract):
    id: str
    type: str
    content: str


class SocialAxes(Contract):
    rapport: Annotated[int, Field(ge=0, le=100)]
    credibility: Annotated[int, Field(ge=0, le=100)]
    tension: Annotated[int, Field(ge=0, le=100)]
    patience: Annotated[int, Field(ge=0, le=100)]


class SocialAxisDelta(Contract):
    rapport: Annotated[int, Field(ge=-100, le=100)]
    credibility: Annotated[int, Field(ge=-100, le=100)]
    tension: Annotated[int, Field(ge=-100, le=100)]
    patience: Annotated[int, Field(ge=-100, le=100)]


class TrainingSocialState(Contract):
    values: SocialAxes
    delta: SocialAxisDelta
    source_revision: Count


class TrainingRewindStatus(Contract):
    limit: Count
    used: Count
    remaining: Count
    available: bool
    eligible_source_revisions: list[Count]


class TrainingContext(Contract):
    version: str
    profile: Literal["concise_skeptical", "sociable"]
    relationship: Literal["first_meeting", "successful_history"]
    player_name: str
    shared_background: str
    personal_detail: bool
    preparation: Preparation | None = Field(default=None, description="Present only for the owner.")
    social_state: TrainingSocialState | None = Field(
        default=None,
        description="Current simulation axes and the latest committed message delta. Present only for the owner.",
    )
    rewind: TrainingRewindStatus | None = Field(
        default=None,
        description="Root-lineage rewind budget and NPC-message checkpoints. Present only for the owner.",
    )


class FinancialLot(Contract):
    lot_id: str
    quantity: int
    price_minor: int
    advance_minor: int
    balance_minor: int
    balance_days: int


class FinancialSummary(Contract):
    currency: str
    base_price_minor: int
    reserve_quantity: int
    reserve_unit_price_minor: int
    maximum_reserve_liability_minor: int
    maximum_liability_minor: int
    advance_minor: int
    balance_minor: int
    weighted_advance_fraction: float
    delayed_balance_fraction: float
    lots: list[FinancialLot]


class Observation(Contract):
    participant_id: str
    role: str
    role_brief: RoleBrief
    currency: str
    conversation: list[ConversationTurn]
    active_offers: list[PublicOffer]
    assistance: Assistance | None
    hints: list[Hint]
    remaining_hints: Count
    hints_available: bool
    context: list[ContextItem]
    status: SessionStatus
    revision: Count
    round: Count
    substantive_turn_count: Count
    next_actor: str | None
    language: Language
    training: TrainingContext | None = None
    negotiation_contract_version: str | None = None
    preliminary_proposals: list[PreliminaryProposal] | None = None
    current_public_terms: PublicTerms | None = None
    unresolved_required_terms: list[str] | None = None
    financial_summary: FinancialSummary | None = None


class PendingConfirmation(Contract):
    offer_id: str
    offer_revision: Version
    terms: PublicTerms
    unresolved_required_terms: list[str] | None = None


class PendingPublication(Contract):
    proposal_id: str
    proposal_revision: Version
    terms: PublicTerms
    snapshot_digest: str
    unresolved_required_terms: list[str]


class ProtocolEnvelope(Contract):
    negotiation_contract_version: str | None = None
    confirmation_kind: Literal["publish_offer", "accept_offer"] | None = None
    pending_offer_publication: PendingPublication | None = None
    pending_confirmation: PendingConfirmation | None = None


class SessionPosition(ProtocolEnvelope):
    session_id: str
    revision: Count
    status: SessionStatus
    round: Count
    next_actor: str | None
    observation: Observation


class OfferReference(Contract):
    offer_id: str
    offer_revision: Version


class RendererMetadata(Contract):
    mode: Literal["template", "llm"]
    provider: str | None
    model: str | None
    fallback_used: bool
    failure_reason: str | None
    validation_failure: str | None
    latency_ms: float | None
    attempted_generation: bool


class CommittedAction(Contract):
    participant_id: str
    action: str
    message: str
    evidence_event_id: str
    offer: OfferReference | None = None
    speech_act: str | None = None
    dialogue_renderer: RendererMetadata | None = None


class RunMetadata(Contract):
    benchmark_run_id: str | None = None
    trial_id: str | None = None
    benchmark_expected_trials: Version | None = None
    seed: int | None = None


class CreateSessionResponse(SessionPosition):
    scenario_version: Version
    scenario_content_digest: str
    scenario_compiler_version: str
    compiled_scenario_digest: str
    substantive_turn_count: Count
    language: Language
    participants: list[Participant]
    participant_credentials: list[ParticipantCredential] | None = None
    participant_token: str | None = None
    credential_delivery: Literal["initial_response_only"] | None = Field(
        default=None, description="Replay marker. Credentials are omitted on an idempotent replay."
    )
    run_metadata: RunMetadata
    committed_actions: list[CommittedAction]


class Clarification(Contract):
    reason_code: str
    question: str
    # Parser-specific public details. They never contain internal parser state.
    expected_currency: str | None = None
    unresolved_required_terms: list[str] | None = None
    candidate_terms: PublicTerms | None = None
    candidate_term_delta: PublicTerms | None = None
    source_offer_id: str | None = None
    source_offer_revision: int | None = None
    confirmation_kind: str | None = None
    evidence_event_id: str | None = None
    baseline_offer_id: str | None = None
    baseline_offer_revision: int | None = None
    provided_currencies: list[str] | None = None


class SessionResponse(SessionPosition):
    scenario_id: str
    scenario_version: Version
    substantive_turn_count: Count
    language: Language
    difficulty: Difficulty
    run_mode: RunMode
    hints_enabled: bool
    pending_confirmation: PendingConfirmation | None
    clarification: Clarification | None


class MessageResponse(SessionPosition):
    result: str = Field(
        description="Committed transition or protocol result, such as "
        "turn_committed, clarification_required, or confirmation_required."
    )
    substantive_turn_count: Count
    committed_actions: list[CommittedAction] | None = None
    clarification: Clarification | None = None
    terminal_reason: str | None = None


class MessageRecord(Contract):
    session_revision: Count
    participant_id: str | None
    role: str
    content: str
    language: Language
    created_at: str


class EventRecord(Contract):
    event_id: str
    session_revision: Count
    participant_id: str | None
    type: str
    payload: PublicPayload
    created_at: str


class MessagesResponse(Contract):
    session_id: str
    revision: Count
    messages: list[MessageRecord]


class EventsResponse(Contract):
    session_id: str
    revision: Count
    events: list[EventRecord]


class HistoryResponse(MessagesResponse):
    events: list[EventRecord]


class HintResponse(Contract):
    session_id: str
    revision: Count
    hint: Hint
    observation: Observation


class Checkpoint(Contract):
    source_revision: Count


class CheckpointsResponse(Contract):
    session_id: str
    checkpoints: list[Checkpoint]


class ForkResponse(SessionPosition):
    scenario_id: str
    scenario_version: Version
    language: Language
    parent_session_id: str
    source_revision: Count
    difficulty: Difficulty
    hints_enabled: bool
    substantive_turn_count: Count
    participant_credentials: list[ParticipantCredential] | None = None
    participant_token: str | None = None
    credential_delivery: Literal["initial_response_only"] | None = None


class AssistedReplyResponse(Contract):
    session_id: str
    revision: Count
    message: str
    prompt_version: str
    provider: str | None
    model: str | None


class CloseResponse(Contract):
    session_id: str
    revision: Count
    status: Literal["aborted"]
    next_actor: None
    terminal_reason: str


class Outcome(Contract):
    agreement: bool
    termination_reason: SessionStatus
    agreement_terms: PublicTerms | None
    financial_summary: FinancialSummary | None = None


class ParticipantOutcome(Outcome):
    participant_utility: float
    reservation_comparison: str
    participant_utilities: dict[str, float] | None = None


class KeyMoment(Contract):
    event_id: str
    type: str
    title: str
    summary: str
    detail: str | None = None


class AssistanceUsage(Contract):
    mode: Difficulty
    hints_enabled: bool
    hints_used: Count


class PublicReview(Contract):
    session_id: str
    revision: Count
    outcome: Outcome
    assistance_usage: AssistanceUsage
    key_moments: list[KeyMoment]
    scoring_version: str
    negotiation_contract_version: str | None = None


class Recommendation(Contract):
    skill: str
    text: str


class Scores(Contract):
    outcome_score: float
    skill_score: float


class Skills(Contract):
    probing: float
    package_design: float
    clarity: float
    conditional_trading: float


class Evidence(Contract):
    ref: str
    source_revision: Count
    role: str
    is_player: bool
    text: str
    excerpt_truncated: bool | None = None


class CoachingCard(Contract):
    dimension: Literal["economics", "process", "communication"] | None = None
    assessment: Literal["observed", "insufficient_evidence"] | None = None
    evidence_refs: list[str] = Field(min_length=1, max_length=3)
    observation: str = Field(min_length=1, max_length=900)
    recommendation: str = Field(min_length=1, max_length=900)
    alternative_phrase: str = Field(min_length=1, max_length=900)
    next_practice: str = Field(min_length=1, max_length=900)
    evidence: list[Evidence]
    alternative_is_hypothesis: Literal[True]


class CoachingMetadata(Contract):
    prompt_version: str | None = None
    source_revision: Count | None = None
    provider: str | None = None
    model: str | None = None
    evidence_truncated: bool | None = None


class CompleteCoaching(CoachingMetadata):
    status: Literal["complete"]
    summary: str = Field(min_length=1, max_length=900)
    goal_assessment: str = Field(min_length=1, max_length=900)
    cards: list[CoachingCard] = Field(min_length=1, max_length=3)


class UnavailableCoaching(CoachingMetadata):
    status: Literal["unavailable"]
    reason: str


class PendingCoaching(Contract):
    status: Literal["pending"]


class NotRequestedCoaching(Contract):
    status: Literal["not_requested"]


CoachingResponse = CompleteCoaching | UnavailableCoaching


class SocialState(Contract):
    rapport: Annotated[int, Field(ge=0, le=100)]
    credibility: Annotated[int, Field(ge=0, le=100)]
    tension: Annotated[int, Field(ge=0, le=100)]
    patience: Annotated[int, Field(ge=0, le=100)]


class SocialChange(Contract):
    kind: str
    quote: str
    delta: dict[str, int]
    rule_version: str


class SocialEvent(Contract):
    source_revision: Count
    changes: list[SocialChange]


class GoalComparison(Target):
    actual: float | None
    gap: float | None
    status: Literal["unknown", "met", "not_met"]
    unit: str | None
    evidence_ref: Literal["outcome"]


class InitialContext(Contract):
    profile: str
    relationship: str
    player_name: str
    shared_background: str


class EconomicBaseline(Contract):
    batna_utility: float
    reservation_utility: float


class MethodologyEconomics(Contract):
    outcome: Literal["agreement", "no_agreement"]
    surplus_over_batna: float | None = Field(
        description="Agreement utility minus the learner's BATNA utility. Null without agreement."
    )
    margin_over_reservation: float | None = Field(
        description="Agreement utility minus the learner's reservation utility. Null without agreement."
    )
    meets_reservation: bool | None = Field(
        description="Whether agreement utility reaches the learner's reservation utility. Null without agreement."
    )


class MethodologyReview(Contract):
    version: Literal["harvard-batna-voss-v1"]
    economics: MethodologyEconomics
    zopa: Literal["not_inferred"]


class OfferHistoryItem(Contract):
    source_revision: Count
    event_id: str
    type: str
    terms: PublicTerms


class TrainingReview(Contract):
    version: str
    preparation: Preparation
    role_brief: RoleBrief
    economic_baseline: EconomicBaseline
    methodology: MethodologyReview
    initial_context: InitialContext
    goal_comparison: list[GoalComparison]
    initial_social: SocialState
    final_social: SocialState
    social_rule_version: str
    social_events: list[SocialEvent]
    evidence: list[Evidence]
    offer_history: list[OfferHistoryItem]
    checkpoints: list[Checkpoint]
    parent_session_id: str | None
    source_revision: Count | None
    informed_practice: bool
    skill_scores_validated: Literal[False]
    coaching: CoachingResponse | PendingCoaching | NotRequestedCoaching


class ReviewResponse(PublicReview):
    outcome: ParticipantOutcome
    skills: Skills
    scores: Scores
    outcome_score: float
    skill_score: float
    recommendations: list[Recommendation]
    training: TrainingReview | None = None


class ComparisonResponse(Contract):
    parent_session_id: str
    session_id: str
    source_revision: Count
    informed_practice: Literal[True]
    same_scenario_version: bool
    same_initial_conditions_at_checkpoint: Literal[True]
    role: str
    before: ParticipantOutcome
    after: ParticipantOutcome
    utility_delta: float
    causal_improvement_claim: Literal[False]


class BenchmarkRelease(Contract):
    benchmark_run_id: str | None
    expected_trials: int | None
    session_count: Count
    completed_count: Count
    trial_count: Count
    release_ready: bool


class AdminParticipant(Participant):
    provider: str | None
    model: str | None
    prompt_version: str | None


class AdminSessionSummary(Contract):
    session_id: str
    scenario_id: str
    scenario_version: Version
    scenario_title: str
    currency: str
    status: SessionStatus
    revision: Count
    round: Count
    substantive_turn_count: Count
    next_actor: str | None
    difficulty: Difficulty
    language: Language
    run_mode: RunMode
    hints_enabled: bool
    run_metadata: RunMetadata
    created_at: str
    updated_at: str
    message_count: Count
    event_count: Count
    offer_revision_count: Count
    participants: list[AdminParticipant]
    review_state: Literal["available", "not_ready", "sealed", "missing"]


class AdminSessionsResponse(Contract):
    items: list[AdminSessionSummary]
    total: Count
    limit: Annotated[int, Field(ge=1, le=200)]
    offset: Count


class StoredPublicOffer(Contract):
    offer_id: str
    offer_revision: Version
    proposer_participant_id: str
    terms: PublicTerms
    status: str
    created_session_revision: Count


class LatencySummary(Contract):
    samples: Count
    average: float | None
    p95: float | None


class RepeatFlag(Contract):
    kind: Literal["exact_repeat", "question_repeat"]
    source_message_id: str
    repeats_source_message_id: str


class Repetition(Contract):
    exact_repeat_count: Count
    question_repeat_count: Count
    flags: list[RepeatFlag]
    flags_truncated: bool


class Rendering(Contract):
    delivered_turns: Count
    telemetry_turns: Count
    generation_attempts: Count
    fallback_observations: Count
    fallback_count: Count | None
    fallback_rate: float | None
    failure_counts: dict[str, Count]
    validation_failures: dict[str, Count]
    latency_ms: LatencySummary


class HumanReview(Contract):
    rubric_version: str
    status: Literal["unrated"]
    dimensions: dict[str, None]
    coverage: dict[str, Count]


class DialogueQuality(Contract):
    version: Literal[1]
    heuristic_only: Literal[True]
    turns: dict[str, Count]
    repetition: Repetition
    rendering: Rendering
    human_review: HumanReview


class AdminSessionResponse(AdminSessionSummary):
    messages: list[MessageRecord]
    events: list[EventRecord]
    offers: list[StoredPublicOffer]
    review: PublicReview | None
    benchmark_run: BenchmarkRelease | None
    dialogue_quality: DialogueQuality


class StatsTotals(Contract):
    total_sessions: Count
    completed_sessions: Count
    agreements: Count
    agreement_rate: float | None
    avg_outcome_score: float | None
    avg_skill_score: float | None


class StatsGroup(Contract):
    key: str
    session_count: Count
    seat_count: Count
    completed_count: Count
    agreement_rate: float | None
    avg_outcome_score: float | None
    avg_skill_score: float | None


class ModelStats(StatsGroup):
    model: str


class ScenarioStats(StatsGroup):
    scenario: str


class LanguageStats(StatsGroup):
    language: str


class DifficultyStats(StatsGroup):
    difficulty: str


class BenchmarkStats(Contract):
    benchmark_run_id: str
    session_count: Count
    completed_count: Count
    trial_ids: list[str]
    seeds: list[int]
    expected_trials: int | None = None
    trial_count: Count | None = None
    release_ready: bool | None = None


class StatsPrivacy(Contract):
    minimum_completed_group_size: Version
    suppressed_fields: list[str]


class StatsResponse(Contract):
    totals: StatsTotals
    by_model: list[ModelStats]
    by_scenario: list[ScenarioStats]
    by_language: list[LanguageStats]
    by_difficulty: list[DifficultyStats]
    benchmark_runs: list[BenchmarkStats]
    privacy: StatsPrivacy


class ApiError(Contract):
    error: str = Field(description="Machine-readable service error code.")
    message: str | None = Field(
        default=None, description="Some protocol conflicts omit this field."
    )
    revision: Count | None = None
    status: SessionStatus | None = None
    next_actor: str | None = None
    terminal_reason: str | None = None
    observation: Observation | None = None
    render_id: str | None = None
    benchmark_run: BenchmarkRelease | None = None
    scenario_language: Language | None = None
    expected_roles: list[str] | None = None


class ValidationIssue(Contract):
    type: str
    loc: list[str | int]
    msg: str
    input: JsonValue = None
    ctx: dict[str, JsonValue] | None = None
    url: str | None = None


class ValidationErrorResponse(Contract):
    detail: list[ValidationIssue]
