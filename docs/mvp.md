# MVP Plan

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
The [delivery plan](plans/05_reference-supply-and-generalization.md) records stages and readiness gates.

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
- `max_rounds` produces deterministic expiry;
- parser and NLG retry exhaustion uses the specified deterministic fallback;
- a recoverable failure resumes from the last committed revision without a duplicate action.

---

## Phase 3 — Evaluation

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
- an Easy training session with a built-in NPC opening role starts with one replayable canonical opening message;
- the Easy message contains exactly the authored public opening terms;
- the Easy message does not describe a partial `opening_position` as a complete package;
- the Easy opening message does not change the session revision, round, turn count, offer, or `next_actor`;
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
