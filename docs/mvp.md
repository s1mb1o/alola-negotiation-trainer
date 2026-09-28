# MVP Plan

## OpenAPI release gate (DR-37)

The MVP MUST publish an OpenAPI 3.1 document at `/openapi.json` and interactive Swagger UI at `/docs`.
The document MUST cover every implemented canonical REST operation under `/api/v1`.
The document MUST describe requests, successful responses, errors, authentication, and actor access restrictions.
API changes MUST update the schema and relevant examples in the same change.
Release checks MUST validate OpenAPI conformance, operation coverage, and unique operation IDs.
Contract tests MUST verify representative successful and error responses against the documented schemas.
Examples MUST use synthetic data without real credentials or hidden session state.
Swagger UI MUST use the same access controls and validation as other clients.
The detailed requirements are defined in [DR-37](decisions/2026-09-24_openapi-documentation.md) and the [API specification](api.md).
The implementation covers all 25 canonical operations with typed responses and contract checks.
See the [OpenAPI guide](openapi-guide.md) for verification commands and extension-point boundaries.
Registered documentation routes do not satisfy this gate alone.

## Human training loop (DR-36)

The opt-in human training flow MUST support private preparation, pinned shared background, bounded social state, actor-safe LLM review, checkpoint retry, and observed outcome comparison.
Private preparation MUST NOT enter NPC context or public administrative projections.
The engine MUST retain authority over economic results and social transitions.
Model failure MUST preserve the deterministic report and committed state.
The exact contracts and release rules are defined in [DR-36](decisions/2026-09-24_training-loop.md).

The training configuration MUST be restricted to one human and one built-in NPC in training mode.
The configuration MUST pin profile, relationship, optional player name, shared background, private preparation, and rule versions.
The engine MUST validate finite numeric targets against the scenario's scalar term grammar.
Only an agreed complete deal MAY satisfy a deal-term target.
Free-text goals MUST NOT receive invented completion percentages.

Social state MUST use bounded rapport, credibility, tension, and patience values.
The classifier MAY propose at most two allowlisted events with exact message excerpts.
The engine MUST apply validated changes once per committed revision.
Positive relationship events MUST have cumulative caps.
Classification failure MUST leave social state unchanged.
Social values MUST NOT override economic acceptability or binding-confirmation rules.

The Web UI MUST show the current four-axis social projection to the training owner under [DR-45](decisions/2026-09-26_live-social-indicators.md).
The indicators MUST use a 0–100 meter and a matching current number.
They MUST show the signed latest-message delta separately.
The Player API MUST omit this projection for other participants.

Coaching MUST require an explicit authenticated request after session termination.
The reviewer MUST receive only the owner's permitted evidence, preparation, and economic baseline.
Generation and grounding MUST run outside write transactions.
The service MUST cache the validated result or an unavailable status.
Active and sealed benchmark sessions MUST NOT initiate coaching.
Model failure MUST preserve the deterministic report.
Exact cited excerpts MUST be attached by the service.

Retry MUST require a completed human training session and an existing immutable checkpoint.
The child MUST restore the selected state and history boundary with fresh participant credentials.
It MUST NOT inherit later history, parent credentials, render jobs, or idempotency results.
The comparison MUST use the same role and identify observed results as informed practice.
It MUST NOT claim causal skill improvement.
Legacy sessions without checkpoints and benchmark sessions MUST NOT use this training fork.

The API schemas, formulas, limits, and verification boundary are documented in the [human training guide](human-training-guide.md).

## Reference supply contract (DR-30)

[DR-30](decisions/2026-09-08_reference-supply-implementation.md) and the [resolved contract](reference-supply-contract.md) define the opt-in implementation.

Scenarios with `negotiation_contract: supply-package-v1` MUST initialize an exact authored preliminary proposal instead of an accept-enabled formal opening offer.
Preliminary proposals MUST remain non-binding even when complete.
The service MUST distinguish preliminary revision, final-offer publication, acceptance intent, and exact-revision confirmation.
A participant's final offer MUST require confirmation of its exact materialized snapshot before publication.
NPC promotion of its own preliminary package MUST present a formal offer without also treating the presentation request as acceptance.
The service MUST permit at most one actor-bound pending finalization operation per session.
An explicit amendment based on a formal offer MUST supersede that offer and invalidate its pending confirmation atomically.
Questions and uncommitted hypotheticals MUST NOT supersede an offer.
Every material amendment MUST use a source revision and preserve dependent conditions atomically.
Composite quantities, monetary allocation, reserve references, and all outcome obligations MUST be validated deterministically.
Incomplete packages MUST NOT receive authoritative complete-package utility.
The NPC MUST select actions using authored rules, NPC utility, and actor-safe public context.
It MUST NOT rank actions using counterpart private utility or expose hidden limits.
New supply rendering MAY use bounded paragraphs around an immutable engine-authored package block.
The LLM MUST NOT alter the block, invent amounts, or establish agreement through prose.
Legacy scalar scenarios, financial confirmation text, and stored renderer versions MUST retain their existing behavior.
Humans and external agents MUST use the same authenticated natural-language Player API.
Public history MUST retain source-linked preliminary revisions and formal offers without exposing private economics.
Replay and restart MUST use persisted validated transitions and stored wording without new LLM calls.
The implementation MUST pass offline reference trajectories and safety regressions before any generalization.
Optional semantic normalization MUST run outside SQLite write transactions.
The service MUST recheck actor authority, session revision, turn, and idempotency before committing its result.
The normalizer MUST preserve numeric tokens and MUST pass its result through deterministic parsing and validation.
Explicit negation, past proposals, and protocol controls MUST NOT become amendments through normalization.
Unsupported conditional clauses and uncertain equivalence MUST produce no package mutation.
Normalization failure MUST produce an observable clarification without exposing raw provider errors.

## Delivery order (DR-29)

[DR-29](decisions/2026-09-08_reference-before-generalization.md) defines the accepted sequence.

The next increment MUST implement and validate one bounded supply-negotiation scenario before generalizing its deal model.
The reference increment MUST retain structured-state authority, actor-safe projections, exact confirmation, immutable scenario versions, and replay without LLM calls.
Generalization MUST preserve the reference scenario's validated behavior and support a second domain through authored configuration.
Implementation MUST NOT begin until the reference specification, economic assumptions, and unresolved contract rules are approved.
This sequencing decision does not authorize paid model calls or external AI review.

The [reference specification](reference-supply-spec.md) records the design. DR-30 and the resolved contract replace its open alternatives.
The [reference specification](reference-supply-spec.md) records stages and readiness gates.

## Prompt language and initial player background

All application-owned LLM instructions and task templates MUST be written in English.
All application-owned LLM instructions and task templates MUST use STE-style English.
Use short, active sentences with one instruction or idea per sentence.
Use consistent terms and explicit references.
Preserve exact identifiers, schema keys, source quotes, protocol phrases, and requirement keywords.
The MVP player-facing dialogue, hints, and final review MUST be in Russian.
Russian messages, quotes, authored text, and examples MAY remain in their original language as clearly separated task data.
See [DR-34](decisions/2026-09-23_prompt-language.md) for the language rule.
See [DR-43](decisions/2026-09-24_ste-system-prompts.md) for the runtime prompt migration.

The scenario or authorized training setup MUST allow explicit player background known to the NPC.
The session MUST pin the validated background and its visibility at creation.
The NPC MUST receive only background explicitly marked as known to it.
Background MUST NOT create a current-session agreement or override economic constraints.
See [DR-35](decisions/2026-09-23_player-background.md) and the implemented scope in [DR-36](decisions/2026-09-24_training-loop.md).

Acceptance checks must include a returning counterpart, a first-time counterpart, private player information, and background text that attempts to change instructions.
The final review must distinguish initial relationship conditions from behavior in the current session.

## Phase 1 — Domain skeleton

Implement:

- versioned external scenario schema in `schemas/scenario-v1.schema.json`;
- deterministic scenario compiler;
- scenario validator and linter;
- ScenarioVersion;
- RoleBrief;
- Session;
- Participant;
- ParticipantCredential;
- Observation;
- NegotiationState;
- DealState;
- BeliefState;
- KnowledgeItem;
- Evidence;
- Claim;
- NegotiationEvent;
- Offer;
- OfferSet;
- RuntimeTerm;
- Constraint;
- UtilityModel;
- AssistancePolicy.

Acceptance:

- scenario can be loaded;
- scenario conforms to the external schema;
- exactly one scenario role defines exactly one of `opening_offer` and `opening_position`;
- `opening_offer` contains every required term;
- an omitted `opening_position` term remains unresolved and receives no generated placeholder value;
- an explicit zero remains a real term value;
- linter reports ZOPA status and accepts an intentional no-ZOPA scenario when it matches the declared training intent;
- session can be started;
- Russian is stored as the scenario and session language;
- participant-scoped public observation can be generated without raw hidden state;
- events are persisted;
- state and delivered observations can be reconstructed without invoking an LLM;
- high-level scenario entities compile into atomic knowledge-item definitions;
- a validated split-delivery structure can be created from authored primitives and rules;
- an ungrounded hypothesis cannot change reality, constraints, or utility.

---

## Phase 2 — Two-party session with a built-in NPC

Implement:

- message endpoint;
- parser/extractor;
- simple deterministic state transition;
- immutable materialized offer revisions;
- counteroffer, withdrawal, rejection, MESO, contextual acceptance, and terminal transitions;
- engine-owned NPC action selection and validation;
- response generation;
- actor-safe NLG input;
- claim ledger for canonical terms and briefed facts;
- transcript;
- CLI client;
- minimal Web UI.

The session uses participant roles. Human and built-in NPC controllers are not fixed domain seat types.

Implement the normative state machine in `docs/offer-session-protocol.md`.

Implement the normative state model in `docs/knowledge-and-emergent-state.md`.

Acceptance:

- one complete Russian supplier scenario works end-to-end through the CLI and Web UI;
- a proposal outside the compiled scenario grammar cannot affect utility or deal validity;
- a supported runtime composite can affect utility through authored rules;
- the dialogue generator receives no raw hidden state;
- a parser ambiguity returns `clarification_required` and cannot silently change deal state;
- the phrase `согласен` cannot bind a complete deal without context and confirmation;
- a superseded offer cannot be accepted;
- an active offer can be withdrawn only before acceptance;
- a stale acceptance returns `409 offer_not_active` with the post-recording revision;
- a built-in NPC runs automatically when it is `next_actor`;
- a human-versus-built-in-NPC training session starts with one stored NPC greeting and the human as `next_actor`;
- `max_rounds` produces deterministic expiry;
- parser and NLG retry exhaustion uses the specified deterministic fallback;
- a recoverable failure resumes from the last committed revision without a duplicate action.

---

## Phase 3 — Evaluation

### Goal-based final review (DR-33)

Status: accepted requirement. Bounded implementation delivered under [DR-36](decisions/2026-09-24_training-loop.md).

The terminal training review MUST include LLM analysis of progress toward the participant's recorded goals and actionable recommendations.
The engine MUST supply the authoritative outcome, constraints, utility, and any numeric goal-progress measures.
Each evaluative claim and recommendation MUST reference supporting session evidence or an authored goal or rule.
The review MUST distinguish observed results from hypotheses about alternative actions.
The review MUST enforce actor-specific disclosure permissions and the benchmark run-set release gate.
An unavailable or invalid LLM analysis MUST leave the deterministic outcome report available and identify the missing analysis.

See [DR-33](decisions/2026-09-23_goal-based-llm-review.md).

### Evaluation scope

Implement:

- skill event detection;
- utility metrics;
- agreement result;
- walk-away result;
- BATNA comparison;
- reservation-utility comparison;
- simple Pareto efficiency approximation;
- outcome score;
- skill score;
- assistance usage;
- evidence event IDs for each feedback claim;
- neutral bluff and exposed-contradiction reporting;
- post-session review with a configured hidden-state reveal policy.

Acceptance:

- outcome score is not reduced by assistance;
- skill score records assistance usage;
- cross-mode skill-score validity is not claimed before calibration;
- an intentional no-ZOPA scenario can score a rational walk-away as successful;
- active-session endpoints never expose raw hidden state.

---

## Phase 4 — Assistance modes

Implement:

- Guided;
- Easy;
- Normal;
- Expert;
- progressive hint API;
- authored Expert-mode distractors;
- actor-safe distractor projection;
- event records for every delivered hint, assistance item, and distractor.

Acceptance:

- benchmark sessions cannot request hints;
- a human-versus-built-in-NPC training session starts with one replayable NPC opening message;
- a scenario version without `dialogue_strategy` uses the bounded relationship-aware greeting;
- a scenario version with `dialogue_strategy` can state only engine-formatted terms selected from the authored opening artifact;
- the grounded opening uses actor-safe shared context and asks one question that advances `opening_goal`;
- `successful_history` can add only the authored successful-history context;
- the model cannot invent previous terms, current terms, concessions, commitments, or agreements;
- the opening message does not change the session revision, round, turn count, offer, or `next_actor`;
- later NPC wording answers the player first and then uses `conversation_goal` as direction only;
- an active training session can branch from an eligible earlier NPC-message checkpoint;
- one root lineage permits three rewinds and cannot restore the spent count from a checkpoint;
- player-side reply assistance uses only actor-safe context and does not change state directly;
- assisted text passes through the normal parser and engine as a player message;
- an Easy training session with an external-agent next actor retains the canonical presentation of authored public opening terms;
- an LLM may paraphrase visible distractor text but cannot invent facts;
- the exact rendered assistance content can be replayed.

---

## Phase 5 — External agents and benchmark runner

Implement generic Player API:

- get observation;
- submit text message;
- participant authentication;
- role-neutral turn result;
- benchmark runner through the CLI;
- prompt-injection tests.

Human and external-agent participants use the same natural-language Player API.

A public typed external-agent action endpoint is outside the product contract.

Acceptance:

- an external LLM can play the same scenario as a human;
- an external LLM uses the same clarification and acceptance-confirmation flow as a human;
- two external agents can occupy both roles;
- each independent benchmark trial uses a fresh session;
- each tested agent plays both roles;
- trials repeat with one fixed run configuration;
- hints and training assistance are disabled;
- results are reported by role and in aggregate.

---

## Phase 6 — Replay and branching

Implement:

- parent_session_id;
- source_revision;
- replay from exact session revision;
- compare branch metrics.

Forked sessions support training and strategy comparison. They are not independent benchmark trials.

Acceptance:

- a branch reconstructs the same state, offer status, pending protocol state, and delivered information at its source revision;
- a branch inherits the pinned run configuration and records every authorized override;
- a branch does not change its parent session;
- official benchmark reports reject forked trials.

---

## Non-goals for first MVP

Do not initially build:

- distributed microservices;
- RL training;
- complex probabilistic beliefs;
- perfect Pareto-frontier solver;
- legal contract drafting;
- negotiation with more than two parties;
- voice/video sentiment analysis.
- public typed external-agent commands.

## Desirable extension after the text MVP

Add STT and TTS adapters after the Web UI, CLI, and canonical text workflow are stable.

STT produces canonical text before parsing.

TTS consumes an actor-safe public message after generation.

Audio does not replace the text transcript or structured event log.
