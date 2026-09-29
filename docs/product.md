# Product Model

## Public product page and private trainer (DR-53)

The deployed product MUST provide a public Russian page at `/ru/` and a public English page at `/en/`.
Each page MUST explain the implemented trainer, scenario coverage, deterministic validation, evidence-linked review, and shared Player API.
Each page MUST contain indexable HTML and complete search metadata.
The pages MUST NOT claim validated learning outcomes.

The trainer MUST remain behind deployment admission control under `/app/*`.
The canonical trainer routes are `/app/training`, `/app/progress`, and `/app/inspector`.
Trainer and API responses MUST remain non-indexable.
The full delivery and metadata rules are defined in [DR-53](decisions/2026-09-29_public-marketing-private-trainer.md).

## Required OpenAPI documentation (DR-37)

The product MUST provide a machine-readable OpenAPI 3.1 document at `/openapi.json` and interactive Swagger UI at `/docs`.
The documentation MUST cover every implemented canonical REST operation under `/api/v1`.
The documentation MUST describe requests, successful responses, errors, authentication, and actor access restrictions.
API changes MUST update the schema and relevant examples in the same change.
The release MUST pass the schema and contract checks defined in [DR-37](decisions/2026-09-24_openapi-documentation.md).
Documentation availability alone MUST NOT count as contract completeness.
The [API specification](api.md) defines the detailed documentation requirements.
The implemented documentation covers all 25 canonical operations. See the [OpenAPI guide](openapi-guide.md).

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

The active training workspace MUST show the four current social axes under [DR-45](decisions/2026-09-26_live-social-indicators.md).
Each indicator MUST show a current number that matches its marker position.
Each indicator MUST show the signed engine-applied change with a separate delta label.
The interface MUST identify the values as simulation parameters.

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

## Product thesis

A negotiation trainer should not be only a role-playing chatbot.

A strong trainer needs an explicit model of:

- what each side wants;
- what each side knows;
- what each side incorrectly believes;
- what has been revealed;
- what deal terms are currently proposed;
- how good the deal is for each side;
- which negotiation skills were used;
- whether value was created or merely claimed.

The LLM provides realistic conversation. The negotiation engine provides consistency.

The engine selects and validates each NPC action.

A future fuzzy LLM policy may rank legal actions. It cannot authorize an action, override a constraint, or assign utility to a proposal outside the compiled scenario grammar.

Human participants and external-agent participants use the same natural-language Player API.

The parser proposes an internal action. The engine validates and commits it.

---

## MVP interfaces and language

The Web UI is the hackathon demonstration interface.

The CLI is a required interface for operation, testing, and agent runs.

The MVP conversation language is Russian.

All application-owned LLM instructions and task templates MUST be written in English.
All application-owned LLM instructions and task templates MUST use STE-style English.
Use short, active sentences with one instruction or idea per sentence.
Use consistent terms and explicit references.
Preserve exact identifiers, schema keys, source quotes, protocol phrases, and requirement keywords.
See [DR-43](decisions/2026-09-24_ste-system-prompts.md).
The MVP player-facing dialogue, hints, and final review MUST be in Russian.
Russian messages, quotes, authored text, and examples MAY remain in their original language as clearly separated task data.
See [DR-34](decisions/2026-09-23_prompt-language.md) for the runtime prompt audit and external-agent version change.

Structured state, utility models, and events must not depend on Russian text labels.

Each scenario and session must identify its language. The contracts must allow additional languages later.

This language extension can support a future proposal for ВАВТ.

STT and TTS are desirable extensions after the text workflow is stable.

Speech recognition produces text before parsing. Speech synthesis consumes an actor-safe public message after generation.

Audio is not the source of truth. The canonical history contains text and structured events.

---

## Player start state

The player receives a role brief, not a complete mathematical utility function.

The scenario or authorized training setup MUST allow explicit player background known to the NPC.
The session MUST pin the validated background and its visibility at creation.
The NPC MUST receive only background explicitly marked as known to it.
Background MUST NOT create a current-session agreement or override economic constraints.
Prior successful deals can support familiarity and authored initial trust.
The review MUST distinguish initial relationship advantages from behavior demonstrated during this session.
See [DR-35](decisions/2026-09-23_player-background.md) and the implemented scope in [DR-36](decisions/2026-09-24_training-loop.md).

Information should be divided into four categories.

### 1. Known facts

Facts the character must know.

Examples:

- budget;
- internal deadline;
- current supplier offer;
- production capacity;
- an instruction from management;
- known BATNA.

### 2. Private interests

Motivations the character knows.

Example:

> This client is strategically important because the company is entering the banking market.

These can be stated qualitatively.

### 3. Derived information

Facts are provided, but the correct negotiation implication is not.

Example:

> At volumes above 10,000 units, unit cost falls by 14%.

The system should not explicitly say:

> Use volume to trade for price.

### 4. Unknown information

Must be discovered through negotiation.

Examples:

- counterparty BATNA;
- real deadline;
- real budget;
- hidden operational constraint;
- internal approval problem;
- relative importance of price/payment/delivery.

---

## Beliefs are not reality

The player may start with incorrect assumptions.

Example:

> Your manager believes the buyer is extremely price-sensitive.

Reality:

- price importance: medium;
- delivery importance: very high.

This lets the trainer teach hypothesis testing rather than blind trust in the brief.

The scenario defines ground truth or deterministic rules that derive it.

The extractor emits proposed evidence from dialogue.

The extractor does not write belief state.

The belief engine updates participant-scoped confidence from validated evidence.

The UI can derive `UNKNOWN`, `PARTIAL_SIGNAL`, `PROBABLE`, and `CONFIRMED` labels from confidence.

These labels describe one participant's evidence state. They do not replace ground truth.

A participant can form an ungrounded runtime hypothesis.

The hypothesis can guide questions. It cannot change reality, utility, constraints, or deal validity.

## Emergent deal structures

The scenario author defines term primitives, capabilities, constraints, composition rules, and evaluation rules.

The author does not need to enumerate every concrete package.

A participant can create a split-delivery schedule, staged payment, contingent reserve, option, or another supported composite at runtime.

The extractor maps the proposal to a typed structure.

The engine validates and evaluates that structure through the compiled scenario rules.

A proposal outside the compiled grammar can be discussed. It cannot affect utility or become binding.

See `docs/knowledge-and-emergent-state.md` for the normative model.

## Authored opening artifacts

Exactly one scenario role defines exactly one authored opening artifact.

A complete `opening_offer` contains every required term.

An `opening_position` contains at least one authored term.

It contains only the terms that the role states at the start.

An omitted required term is `UNSPECIFIED` and remains unresolved.

The system never inserts a default or placeholder value for an omitted term.

An explicit zero is a real offer value.

A participant cannot bind an opening position until every required term is explicit.

This model lets a scenario preserve a negotiation topic for discovery.

For example, a supplier can state a price without stating a prepayment share or delivery time.

## Agreement interaction

The system interprets agreement in context.

The phrase `согласен` can refer to one condition, an agreement in principle, or the complete offer.

Ambiguous agreement returns `clarification_required`.

Complete acceptance requires a second confirmation that displays the complete materialized offer.

The same flow applies to humans and external agents.

See `docs/offer-session-protocol.md` for the normative protocol.

---

## Difficulty / assistance modes

The same scenario can be reused at multiple difficulty levels.

Every mode uses an actor-safe observation projection.

Guided and Easy assistance may use visible evidence and permitted detected signals. It must not read raw counterparty utility, BATNA, constraints, or hidden facts.

Language is independent of difficulty.

### Guided

Shows:

- player's own priorities clearly;
- detected signals;
- likely interpretations;
- coaching about the type of next move.

Example:

> Signal: the supplier repeatedly returns to payment terms. This parameter may be important to them.

### Easy

Shows:

- one case-specific built-in-NPC greeting at the start of human training sessions;
- clear own priorities;
- confirmed or probable counterparty interests;
- no direct recommended wording.

An older scenario version without `dialogue_strategy` uses the bounded greeting.
It does not state offer terms or give negotiation advice.
It does not consume a turn or change the deal state.
The human makes the first live negotiation move.
For `successful_history`, the greeting uses bounded varied wording that signals prior familiarity.
It does not invent details about previous negotiations.
The Web UI selects `successful_history` by default for a new training setup.
The user can select `first_meeting` before session creation.
Existing sessions retain their pinned relationship and stored greeting.

A new scenario version can define an actor-safe `dialogue_strategy` for the opening role.
The strategy supplies shared scenario context and separate opening and conversation goals.
The engine inserts exact selected terms from the authored opening artifact.
The wording model connects these facts in natural language.
It asks one question that advances the opening goal.
The model cannot change a value, add a term, make a concession, or commit a lifecycle action.
Provider failure uses a deterministic grounded opening.

Later NPC wording receives the same shared scenario context and the conversation goal.
The NPC answers the player's current message first.
It then advances its negotiation task when the selected engine action permits this step.

During an active training session, the learner can return to an eligible earlier NPC message.
The return restores the exact saved state in a new child session.
One root training lineage allows three returns.
The interface shows the remaining count and disables the action after exhaustion.

The learner can select **Ответь за меня** on the player's turn.
The configured player-side model writes one message from the learner's visible context and private plan.
The normal Player API validates and submits the message.
An Easy session with an external-agent next actor retains the canonical opening presentation.

### Normal

Shows:

- role brief;
- conversation;
- current public terms.

No interpretation.

### Expert

May include:

- ambiguous brief;
- conflicting information;
- irrelevant information;
- weak signals;
- fewer explicit goals.

---

## Hint system

Hints should be progressive.

### Hint 1

Where to look.

### Hint 2

What interest may matter.

### Hint 3

What kind of negotiation move could help.

Avoid immediately providing the exact answer.

Every delivered hint must be recorded as an event.

Benchmark trials disable hints and training assistance.

---

## Training feedback

### Goal-based final review (DR-33)

Status: accepted requirement. Bounded implementation delivered under [DR-36](decisions/2026-09-24_training-loop.md).

The terminal training review MUST include LLM analysis of progress toward the participant's recorded goals and actionable recommendations.
The engine MUST supply the authoritative outcome, constraints, utility, and any numeric goal-progress measures.
Each evaluative claim and recommendation MUST reference supporting session evidence or an authored goal or rule.
The review MUST distinguish observed results from hypotheses about alternative actions.
The review MUST enforce actor-specific disclosure permissions and the benchmark run-set release gate.
An unavailable or invalid LLM analysis MUST leave the deterministic outcome report available and identify the missing analysis.

See [DR-33](decisions/2026-09-23_goal-based-llm-review.md) and [the review design](social-state-and-llm-dialogue.md#71-final-goal-based-review-dr-33).

### Separate assessment dimensions

Separate:

- negotiation outcome;
- negotiation process;
- language quality;
- communication quality.

Possible scoring axes:

- Outcome
- Pareto efficiency
- Information discovery
- Information leakage
- Value creation
- Value claiming
- Conditional trading
- Active listening
- Objective criteria
- Relationship / rapport
- BATNA discipline
- Closing quality

A player may speak excellent language but negotiate badly.

Hints never reduce the economic outcome score.

The skill score records assistance usage and assistance mode.

Do not claim that skill scores are comparable across assistance modes until the scoring model is calibrated and validated.

A rational walk-away is a successful outcome when the scenario intentionally has no ZOPA or when every feasible deal is below the player's reservation utility.

---

## Important rule

Do not punish a player for not knowing hidden information.

You may punish or coach them for failing to investigate relevant signals.

---

## Hidden-state release policy

An active player never receives raw hidden state.

A completed training session may reveal selected hidden facts, utilities, or missed signals when the scenario review policy permits the reveal.

A training review must identify which information was revealed and why.

A benchmark trial does not reveal hidden information when the trial ends.

The benchmark system may release configured review information only after the complete run set is finished.

---

## Benchmark integrity

Each independent trial uses a fresh session.

Each tested agent plays both roles.

The runner repeats trials.

The runner fixes the scenario version, language, policy configuration, model configuration, prompt versions, and randomness configuration for a run set.

Benchmark trials disable hints and training assistance.

Forked sessions are training artifacts. They are not independent benchmark trials.
