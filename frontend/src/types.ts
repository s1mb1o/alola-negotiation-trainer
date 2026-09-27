export type UiLanguage = 'ru' | 'en'
export type SessionLanguage = 'ru' | 'en'
export type Difficulty = 'guided' | 'easy' | 'normal' | 'expert'

export type SessionStatus =
  | 'active'
  | 'agreement_reached'
  | 'walked_away'
  | 'expired'
  | 'aborted'
  | 'technical_failure'

export type JsonRecord = Record<string, unknown>

export interface ScenarioSummary {
  training_terms?: Array<{ term_id: string; label: string }>
  scenario_id: string
  version: number
  title: string
  opening_kind?: 'opening_offer' | 'opening_position'
  currency?: string
  description?: string
  languages?: SessionLanguage[]
  duration_minutes?: number
  role_label?: string
  counterpart_label?: string
  roles?: ScenarioRole[]
}

export interface ScenarioRole {
  role_id: string
  title: string
  description?: string
}

export interface OfferView {
  offer_id: string
  offer_revision: number
  offer_set_id?: string
  proposer_role?: string
  proposer_participant_id?: string
  status?: string
  terms: JsonRecord
  unresolved_required_terms?: string[]
}

export interface UnresolvedTermDetail {
  path: string
  label: string
}

export interface PreliminaryProposal {
  proposal_id: string
  proposal_revision: number
  proposer_participant_id: string
  proposer_role: string
  terms: JsonRecord
  status: string
  source_event_ids: string[]
  unresolved_required_terms: string[]
  unresolved_term_details?: UnresolvedTermDetail[]
}

export interface FinancialSummaryView {
  currency?: string
  base_price_minor?: number
  reserve_unit_price_minor?: number
  reserve_quantity?: number
  maximum_reserve_liability_minor?: number
  maximum_liability_minor?: number
  advance_minor?: number
  balance_minor?: number
  weighted_advance_fraction?: number
  delayed_balance_fraction?: number
  lots?: Array<{ lot_id: string; quantity: number; price_minor: number; advance_minor: number; balance_minor: number; balance_days: number }>
}

export interface HintView {
  id?: string
  title?: string
  text?: string
  message?: string
  level?: string | number
  used?: boolean
}

export interface AssistanceView {
  hints?: HintView[]
  signals?: Array<string | { label?: string; text?: string; confidence?: string | number }>
  detected_signals?: Array<string | { label?: string; text?: string; confidence?: string | number }>
  own_priorities?: string[]
  probable_interests?: string[]
  coaching?: string
  remaining_hints?: number
  available?: boolean
  [key: string]: unknown
}

export interface ContextItem {
  id?: string
  type?: string
  content: string
}

export interface RoleBriefView {
  title?: string
  summary?: string
  content?: string
  objectives?: string[]
  context?: string | string[]
  batna?: string
  constraints?: JsonRecord
  priorities?: string[]
}

export interface ConversationEntry {
  id?: string
  event_id?: string
  revision?: number
  participant_id?: string
  role?: string
  actor?: string
  action?: string
  message?: string
  text?: string
  occurred_at?: string
  created_at?: string
}

export interface Observation {
  training?: TrainingObservation
  negotiation_contract_version?: string
  role_brief?: string | RoleBriefView
  conversation?: Array<ConversationEntry | string>
  active_offers?: OfferView[]
  preliminary_proposals?: PreliminaryProposal[]
  unresolved_required_terms?: string[]
  unresolved_term_details?: UnresolvedTermDetail[]
  financial_summary?: FinancialSummaryView | null
  current_public_terms?: JsonRecord
  assistance?: AssistanceView | null
  hints?: HintView[]
  context?: ContextItem[]
  currency?: string
  remaining_hints?: number
  hints_available?: boolean
  participant_id?: string
  role?: string
  [key: string]: unknown
}

export interface CommittedAction {
  participant_id?: string
  role?: string
  action?: string
  message?: string
  offer?: Partial<OfferView>
  offer_lifecycle?: Partial<OfferView>
}

export interface Clarification {
  reason_code?: string
  question: string
  candidate_interpretations?: string[]
}

export interface PendingConfirmation {
  offer_id: string
  offer_revision: number
  terms: JsonRecord
  unresolved_required_terms?: string[]
}

export interface PendingOfferPublication {
  proposal_id: string
  proposal_revision: number
  terms: JsonRecord
  snapshot_digest: string
  unresolved_required_terms: string[]
}

export interface ParticipantCredential {
  participant_id?: string
  role?: string
  token?: string
  access_token?: string
}

export interface SessionEnvelope {
  negotiation_contract_version?: string
  session_id: string
  result?: string
  revision: number
  scenario_id?: string
  scenario_version?: number
  scenario_content_digest?: string
  status: SessionStatus
  round?: number
  substantive_turn_count?: number
  next_actor?: string | null
  language?: SessionLanguage
  difficulty?: Difficulty
  run_mode?: string
  /** Returned by `GET /sessions/{id}`; the session-creation choice is the fallback. */
  hints_enabled?: boolean
  observation: Observation
  committed_actions?: CommittedAction[]
  /** `null` when no clarification is pending for the authenticated participant. */
  clarification?: Clarification | null
  /** `null` when no confirmation is pending for the authenticated participant. */
  pending_confirmation?: PendingConfirmation | null
  confirmation_kind?: 'publish_offer' | 'accept_offer' | null
  /** Actionable publication state is returned only to its authenticated owner. */
  pending_offer_publication?: PendingOfferPublication | null
  participant_token?: string
  access_token?: string
  participant_tokens?: Record<string, string>
  participant_credentials?: ParticipantCredential[]
  credential_delivery?: string
  participants?: ParticipantCredential[]
}

export interface CreateSessionRequest {
  training?: TrainingSetup
  idempotency_key: string
  scenario_id: string
  scenario_version: number
  language: SessionLanguage
  participants: Array<{ role: string; controller: 'human' | 'built_in_npc' | 'external_agent' }>
  difficulty: Difficulty
  hints_enabled: boolean
  run_mode: 'training' | 'benchmark'
}

export interface ApiErrorPayload {
  error?: string
  code?: string
  detail?: string
  message?: string
  revision?: number
  current_revision?: number
  observation?: Observation
  [key: string]: unknown
}

export interface OutcomeReview {
  financial_summary?: FinancialSummaryView | null
  agreement?: boolean
  termination_reason?: SessionStatus | string
  participant_utility?: number
  participant_utilities?: Record<string, number>
  pareto_efficiency?: number
  value_created?: number
}

export interface SkillReview {
  [skill: string]: number | undefined
}

export interface KeyMoment {
  event_id?: string
  type?: string
  title?: string
  summary?: string
  message?: string
  impact?: 'positive' | 'negative' | 'neutral' | string
  detail?: string
}

export interface ReviewRecommendation {
  skill: string
  text: string
}

export interface SessionReview {
  training?: TrainingReview
  outcome: OutcomeReview
  skills?: SkillReview
  key_moments?: KeyMoment[]
  recommendations?: ReviewRecommendation[]
  outcome_score?: number
  skill_score?: number
  assistance_usage?: JsonRecord
}

export interface StoredSessionReview {
  session_id: string
  scenario_title: string
  finished_at: string
  review: SessionReview
}

export interface StoredActiveSession {
  session_id: string
  role_id: string
  session_language: SessionLanguage
  scenario: ScenarioSummary
  difficulty: Difficulty
  hints_enabled: boolean
  revision: number
}

export interface AggregateStats {
  sessions: number
  agreements: number
  walkaways: number
  average_outcome: number | null
  average_pareto: number | null
  average_skills: Record<string, number>
  recent: StoredSessionReview[]
}

export interface AggregateStatsResponse {
  totals?: JsonRecord
  by_model?: unknown
  by_scenario?: unknown
  by_language?: unknown
  by_difficulty?: unknown
  [key: string]: unknown
}

export type AdminReviewState = 'not_ready' | 'sealed' | 'available'

export interface AdminParticipant {
  participant_id: string
  role: string
  controller: string
  provider?: string | null
  model?: string | null
  prompt_version?: string | null
}

export interface AdminRunMetadata {
  benchmark_run_id?: string
  trial_id?: string
  benchmark_expected_trials?: number
  seed?: number
}

export interface AdminSessionSummary {
  session_id: string
  scenario_id: string
  scenario_version: number
  scenario_title: string
  currency?: string | null
  status: SessionStatus
  revision: number
  round: number
  substantive_turn_count: number
  next_actor?: string | null
  difficulty: Difficulty
  language: SessionLanguage
  run_mode: 'training' | 'benchmark'
  hints_enabled: boolean
  run_metadata: AdminRunMetadata
  created_at: string
  updated_at: string
  message_count: number
  event_count: number
  offer_revision_count: number
  participants: AdminParticipant[]
  review_state: AdminReviewState
}

export interface AdminSessionMessage {
  session_revision: number
  participant_id: string
  role: string
  content: string
  language: SessionLanguage
  created_at: string
}

export interface AdminSessionEvent {
  event_id: string
  session_revision: number
  participant_id?: string | null
  type: string
  payload: JsonRecord
  created_at: string
}

export interface AdminSessionOffer {
  offer_id: string
  offer_revision: number
  proposer_participant_id: string
  terms: JsonRecord
  status: string
  created_session_revision: number
}

export interface AdminBenchmarkRunState {
  benchmark_run_id?: string | null
  expected_trials?: number | null
  session_count: number
  completed_count: number
  trial_count: number
  release_ready: boolean
}

export interface AdminSessionDetail extends AdminSessionSummary {
  messages: AdminSessionMessage[]
  events: AdminSessionEvent[]
  offers: AdminSessionOffer[]
  review: JsonRecord | null
  benchmark_run: AdminBenchmarkRunState | null
  dialogue_quality?: DialogueQuality | null
}

export interface DialogueQuality {
  version: number
  heuristic_only: boolean
  turns: { total: number; player: number; npc: number }
  repetition: {
    exact_repeat_count: number
    question_repeat_count: number
    flags: Array<{ kind: string; source_message_id: string; repeats_source_message_id: string }>
    flags_truncated: boolean
  }
  rendering: {
    delivered_turns: number
    telemetry_turns: number
    generation_attempts: number
    fallback_observations: number
    fallback_count: number | null
    fallback_rate: number | null
    failure_counts: Record<string, number>
    validation_failures: Record<string, number>
    latency_ms: { samples: number; average: number | null; p95: number | null }
  }
  human_review: {
    rubric_version: string
    status: 'unrated' | 'rated'
    dimensions: Record<'relevance' | 'continuity' | 'attribution' | 'unsupported_claims', number | null>
    coverage: { rated_turns: number; eligible_turns: number }
  }
}

export interface AdminSessionFilters {
  status?: string
  scenario_id?: string
  language?: SessionLanguage | ''
  run_mode?: 'training' | 'benchmark' | ''
  limit?: number
  offset?: number
}

export interface AdminSessionListResponse {
  items: AdminSessionSummary[]
  total: number
  limit: number
  offset: number
}

export interface TimelineMessage {
  id: string
  revision?: number
  participantId?: string
  role: string
  action?: string
  text: string
  timestamp?: string
  pending?: boolean
  failed?: boolean
}

export type ThemePreference = 'system' | 'light' | 'dark'

export interface TrainingSetup {
  profile: 'concise_skeptical' | 'sociable'
  relationship: 'first_meeting' | 'successful_history'
  player_name: string
  shared_background: string
  personal_detail: boolean
  preparation: {
    target: string
    unacceptable_result: string
    available_trades: string
    information_to_discover: string
    targets: Array<{ term_id: string; operator: 'lte' | 'gte' | 'eq'; value: number }>
  }
}

export interface SocialAxes {
  rapport: number
  credibility: number
  tension: number
  patience: number
}

export interface TrainingSocialState {
  values: SocialAxes
  delta: SocialAxes
  source_revision: number
}

export interface TrainingRewindStatus {
  limit: number
  used: number
  remaining: number
  available: boolean
  eligible_source_revisions: number[]
}

export type TrainingObservation = Omit<TrainingSetup, 'preparation'> & {
  version: string
  preparation?: TrainingSetup['preparation']
  social_state?: TrainingSocialState
  rewind?: TrainingRewindStatus
}

export interface AssistedReplyResponse {
  session_id: string
  revision: number
  message: string
  prompt_version: string
  provider?: string | null
  model?: string | null
}

export interface CoachingEvidence {
  excerpt_truncated?: boolean
  ref: string
  source_revision: number
  text: string
  role: string
  is_player: boolean
}

export interface CoachingResult {
  evidence_truncated?: boolean
  status: 'not_requested' | 'pending' | 'complete' | 'unavailable'
  summary?: string
  goal_assessment?: string
  cards?: Array<{
    dimension?: 'economics' | 'process' | 'communication' | null
    assessment?: 'observed' | 'insufficient_evidence' | null
    observation: string; recommendation: string; alternative_phrase: string; next_practice: string
    evidence: CoachingEvidence[]; alternative_is_hypothesis: boolean
  }>
}

export interface TrainingReview {
  methodology?: {
    version: 'harvard-batna-voss-v1'
    economics: {
      outcome: 'agreement' | 'no_agreement'
      surplus_over_batna: number | null
      margin_over_reservation: number | null
      meets_reservation: boolean | null
    }
    zopa: 'not_inferred'
  }
  preparation: TrainingSetup['preparation']
  goal_comparison: Array<{ term_id: string; operator: string; value: number; actual: number | null; gap: number | null; status: string }>
  initial_social: Record<string, number>
  final_social: Record<string, number>
  offer_history: Array<{ source_revision: number; event_id: string; type: string; terms: JsonRecord }>
  evidence: CoachingEvidence[]
  checkpoints: Array<{ source_revision: number }>
  parent_session_id?: string | null
  informed_practice: boolean
  skill_scores_validated: boolean
  coaching: CoachingResult
}

export interface TrainingComparison {
  before: OutcomeReview
  after: OutcomeReview
  utility_delta: number
  source_revision: number
  informed_practice: boolean
  same_scenario_version: boolean
  same_initial_conditions_at_checkpoint: boolean
}
