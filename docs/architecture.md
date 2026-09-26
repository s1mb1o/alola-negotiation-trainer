# Architecture

## Required OpenAPI documentation (DR-37)

The service MUST generate an OpenAPI 3.1 document from route declarations and typed API contracts.
The service MUST publish the document at `/openapi.json` and interactive Swagger UI at `/docs`.
The document MUST cover every implemented canonical REST operation under `/api/v1`.
The contracts MUST describe requests, successful responses, errors, authentication, and actor access restrictions.
API changes MUST update the schema and relevant examples in the same change.
Automated checks MUST validate the document, operation coverage, and unique operation IDs.
Contract tests MUST check representative successful and error responses against the documented schemas.
Swagger UI MUST use the same access controls and validation as other clients.
Examples MUST NOT expose real credentials or hidden session state.
The full contract is defined in [DR-37](decisions/2026-09-24_openapi-documentation.md) and the [API specification](api.md).
The implementation uses typed HTTP projections in `backend/app/api_contracts.py` and route metadata in `backend/app/main.py`.
The shared backend test client validates actual response bodies, including direct `JSONResponse` results.
See the [OpenAPI guide](openapi-guide.md).

## Human training loop (DR-36)

The opt-in human training flow MUST support private preparation, pinned shared background, bounded social state, actor-safe LLM review, checkpoint retry, and observed outcome comparison.
Private preparation MUST NOT enter NPC context or public administrative projections.
The engine MUST retain authority over economic results and social transitions.
Model failure MUST preserve the deterministic report and committed state.
The exact contracts and release rules are defined in [DR-36](decisions/2026-09-24_training-loop.md).

The training configuration MUST be restricted to one human and one built-in NPC in training mode.
The configuration MUST pin profile, relationship, shared background, private preparation, and rule versions.
The engine MUST validate finite numeric targets against the scenario's scalar term grammar.
Only an agreed complete deal MAY satisfy a deal-term target.
Free-text goals MUST NOT receive invented completion percentages.

Social state MUST use bounded rapport, credibility, tension, and patience values.
The classifier MAY propose at most two allowlisted events with exact message excerpts.
The engine MUST apply validated changes once per committed revision.
Positive relationship events MUST have cumulative caps.
Classification failure MUST leave social state unchanged.
Social values MUST NOT override economic acceptability or binding-confirmation rules.

The active player observation MUST expose the current four-axis social projection only to the training owner under [DR-45](decisions/2026-09-26_live-social-indicators.md).
The projection MUST include the latest aggregate engine-applied delta and its source revision.
It MUST NOT expose classifier evidence or another participant's private state.
The Web UI MUST render the projection as accessible live indicators in the supporting column.

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
The [delivery plan](plans/05_reference-supply-and-generalization.md) records stages and readiness gates.

## Grounded negotiation dialogue (DR-28)

[DR-28](decisions/2026-09-06_grounded-negotiation-dialogue.md) governs contextual input, validated exchanges, public quote slots, authored styles, difficulty profiles, and dialogue evaluation.
The parser MUST distinguish questions, quotations, proposals, relative changes, and short answers before committing terms.
Numeric questions and quotations MUST NOT create offers.
A mixed message MAY commit an explicitly scoped proposal clause while leaving a separate question non-binding.
The service MUST derive parse context after participant authentication, revision checks, and turn checks.
A relative change MUST use one active public offer revision and the scenario currency.
A short numeric answer MAY use one unambiguous public topic or an engine-authored requested term.
An ambiguous reference, missing baseline, or unsupported calculation MUST request clarification without changing offer terms.
Generated NPC prose MUST NOT establish the requested term, an agreement, or ground truth.
Human and external-agent acceptance MUST retain the separate complete-offer confirmation step.

The compiler MUST bound an authored exchange grid and validate its numeric candidates against required term schemas.
The engine MUST select a complete package that passes every role's hard constraints and the NPC reservation utility.
It MUST use only NPC utility, public proposals, and authored rules for exchange selection.
It MUST NOT optimize against counterpart private utility or expose private limits.
The policy SHOULD prefer a monetary concession in return for an authored nonmonetary benefit to the NPC.
It MUST NOT reverse a previous public monetary concession.
Missing terms MUST remain `UNSPECIFIED` during discussion.
The policy MUST NOT complete an omitted opening term implicitly.
An unsupported exchange MUST use a validated fallback or rejection without invented terms.
An exchange explanation MUST describe only the selected public package.

Numeric references MUST use exact attributed engine quote slots tied to an active public offer revision.
Each slot MUST identify its offer, revision, proposer role, term, value, currency, and exact display text.
The provider MUST emit a slot token instead of writing a number.
Unknown, altered, repeated, inactive, or unbound slots MUST be rejected.
The service MUST substitute exact engine text and validate the resolved reply.
A quote MUST NOT authorize a new promise, waiver, calculation, or agreement.
Novel prose MUST still pass the separate grounding check.
Canonical financial actions MUST remain deterministic.
The durable render plan MUST preserve the slots and their revision binding.
Historical plans without slots MUST remain readable.

New scenario versions MAY add grounded reasons, exchange candidates, and an allowlisted stable conversation style.
Existing versions MUST remain unchanged.
The service MUST select a bounded public dialogue profile from the session difficulty.
Guided and Easy profiles SHOULD clarify one term at a time and take conversational initiative.
Normal and Expert profiles SHOULD ask for grounds and reciprocal changes without abusive behavior.
Difficulty and style MUST NOT change hidden truth, utility, hard constraints, or reservation thresholds.
Benchmark sessions MUST use Normal difficulty and disabled assistance.

Dialogue quality MUST remain separate from utility and agreement rate.
Admin Session Inspector diagnostics MUST use public transcript, public renderer events, and bounded telemetry only.
The separate privileged LLM trace window follows DR-40 below.
They MUST distinguish exact repetition, question repetition, latency, fallback rate, and categorized validation failures.
Missing telemetry MUST remain unavailable rather than zero.
Heuristics MUST NOT be presented as proof of relevance or factual correctness.
Offline human scorecards MUST retain versioned source references and rating coverage.
Unrated dimensions MUST remain unrated.
The regression corpus MUST cover connected Russian and English dialogue, numeric questions, relative changes, short replies, corrections, repetitions, and false claims.
Existing privacy, confirmation, immutable-version, and durable-render boundaries remain required.

## Conversation continuity increment (DR-27)

The service MUST derive a bounded versioned public conversation memory from durable messages and public events in the same session.
Memory MUST preserve source references and distinguish attributed player statements, proposed terms, responded questions, and binding agreements.
Each remembered offer MUST retain its lifecycle status and the source public event reference.
Public lifecycle events MUST control historical offer status. An inactive offer MUST NOT be presented as active.
Chronological response MUST NOT prove that a question was answered.
Memory MUST survive restart through deterministic reconstruction. An LLM summary MUST NOT become truth.
The service MUST redact credentials before memory construction and truncation. Hidden state and private event payloads MUST remain excluded.
Explicit term focus MUST override generic discussion cues. A valid partial offer MAY receive `acknowledge_partial_offer` without requiring the full package immediately.
The engine MAY select `focused_discussion`. Missing terms MUST remain `UNSPECIFIED`.
Each role MAY author up to six `dialogue_reasons` with `id`, `term_id`, `text`, `source_ref`, and `disclose_when: on_topic_question`.
The source MUST be the same role's `brief.objective` or `brief.context`. Only up to two selected texts and IDs MAY reach the renderer on a matching question.
The renderer MAY also receive previously delivered public reason history with source `npc.utterance.delivered` event references.
Source text and unselected private reasons MUST remain excluded. Reasons MUST NOT change economic rules.
Only delivered disclosures MAY enter public disclosure history.
The renderer MUST include every text from `approved_reasons` verbatim in the reply.
It MUST reject generated text that omits or paraphrases a selected reason instead of including the exact text.
After a reason is delivered, the engine MUST NOT select it again for `approved_reasons`.
The renderer MAY use that reason from `disclosed_reasons` without verbatim repetition.
Only an exact selected reason text in the actually delivered message qualifies for `disclosed_reason_ids` in the public `npc.utterance.delivered` event.
A pending render, failed render, or paraphrase alone MUST NOT prove disclosure.
Canonical financial messages and all DR-26 validation and durable-render boundaries remain unchanged.
Historical scenarios and render plans without these fields MUST remain valid.
See [DR-27](decisions/2026-09-06_conversation-continuity.md).

## High-level architecture

The product is a headless service with API clients.

```text
                    ┌────────────── Web UI
                    ├────────────── Mobile app
                    ├────────────── CLI
                    ├────────────── External LLM agent
                    ├────────────── Scripted bot
                    └────────────── Benchmark runner
                                   │
                                   ▼
                         Negotiation Service API
                                   │
                         ┌─────────┴─────────┐
                         ▼                   ▼
                   Session Manager     Scenario Service
                         │                   │
                         │             Scenario Compiler
                         │                   │
                         ▼
                  Negotiation Engine
                  ├─ Reality State
                  ├─ Deal State
                  ├─ Belief State
                  ├─ Evidence Validator
                  ├─ Term DSL Validator
                  ├─ Utility
                  ├─ Constraints
                  ├─ Scope
                  └─ Assistance Policy
                         │
                         ▼
                     NPC Policy
                         │
                         ▼
                 Approved speech act
                         │
                         ▼
               Optional dialogue renderer
                 ├─ Provider output
                 └─ Deterministic fallback
                         │
                         ▼
                Transcript + Event Store
                         │
                         ▼
                Evaluator / Analytics
```

The Web UI and CLI are required MVP clients.

The Web UI is the hackathon demonstration client.

The CLI supports operation, tests, scripted agents, and benchmark runs.

STT and TTS are optional boundary adapters. STT converts speech to canonical text before parsing. TTS converts an actor-safe public message to audio after generation.

The canonical transcript remains text. The canonical history remains the structured event log.

The MVP conversation language is Russian. Scenario, session, prompt, and rendering contracts carry language metadata so that later versions can add languages without changing domain identifiers.

All application-owned LLM instructions and task templates MUST be written in English.
All application-owned LLM instructions and task templates MUST use STE-style English.
Use short, active sentences with one instruction or idea per sentence.
Use consistent terms and explicit references.
Preserve exact identifiers, schema keys, source quotes, protocol phrases, and requirement keywords.
See [DR-43](decisions/2026-09-24_ste-system-prompts.md) for the migration and prompt versions.
This convention does not claim formally checked ASD-STE100 compliance.
The MVP player-facing dialogue, hints, and final review MUST be in Russian.
Russian messages, quotes, authored text, and examples MAY remain in their original language as clearly separated task data.
The rule applies to every application-owned model task and retry path.
See [DR-34](decisions/2026-09-23_prompt-language.md) for the runtime prompt audit and external-agent version change.

### Initial player background (DR-35)

Status: accepted requirement. Bounded implementation delivered under [DR-36](decisions/2026-09-24_training-loop.md).

The scenario or authorized training setup MUST allow explicit player background known to the NPC.
The session MUST pin the validated background and its visibility at creation.
The NPC MUST receive only background explicitly marked as known to it.
Background MUST NOT create a current-session agreement or override economic constraints.

The service validates setup against scenario capabilities and records the initial context with source identifiers.
The permitted NPC projection remains distinct from the player's private brief.
Authored rules MAY initialize social state. The LLM MUST NOT invent initial social values.
Historical relationship facts MUST remain distinct from current-session offers and confirmations.
Replay and benchmark configuration MUST retain the pinned background and initialization rules.
The [human training guide](human-training-guide.md) defines the implemented schema, persistence, and renderer projection.
See [DR-35](decisions/2026-09-23_player-background.md).

---

## Modular monolith for MVP

Do not begin with microservices.

Suggested module layout:

```text
negotiation-service/
├── api/
├── sessions/
├── scenarios/
├── engine/
├── agents/
├── llm/
├── evaluator/
├── storage/
└── analytics/
```

Later, heavy components can be extracted if necessary.

---

## Core processing pipeline

Exactly one scenario role defines exactly one authored opening artifact.

The artifact is either a complete `opening_offer` or an `opening_position` that can omit required terms.

An `opening_position` contains at least one authored term.

Session creation commits the authored opening artifact as the initial active offer revision at revision 0.

The compiler and service preserve only the authored terms.

An omitted `opening_position` term remains `UNSPECIFIED` and appears in `unresolved_required_terms`.

The compiler and service do not synthesize a value for an omitted term.

An explicit zero remains a real value.

For human-versus-built-in-NPC training, the NPC delivers one case-specific opening message at revision 0.

The human remains `next_actor` and makes the first live negotiation move.

An older scenario version without `dialogue_strategy` uses one bounded relationship-aware template.

The template can signal familiarity or collaboration.

It does not invent prior terms, concessions, promises, or current agreements.

An opening role can define an actor-safe `dialogue_strategy` in a new immutable scenario version.

The strategy contains shared scenario context, optional successful-history context, an opening goal, a conversation goal, and identifiers for authored opening terms.

The opening renderer receives no role brief, BATNA, utility value, hard constraint, or private economic fact.

When the dialogue route uses a Character model, the service uses the control route for this structured opening task.

Later in-character dialogue continues to use the Character route.

The engine formats the selected public opening terms.

The model MUST use an exact placeholder for these terms.

The engine replaces this placeholder after validation.

The opening can state the exact public position and authored operational context.

The opening asks one question that advances the authored opening goal.

Provider execution occurs before the session write transaction.

Provider or validation failure uses a deterministic grounded fallback.

The opening message remains non-substantive.

It does not change the active offer, session revision, round, turn count, or `next_actor`.

An idempotent create retry returns the stored message without another provider call.

Active dialogue rewind creates a new child session from an immutable checkpoint after an NPC message.

The source session remains unchanged.

A durable root-lineage counter permits three rewinds and stays outside checkpoint snapshots.

Player-side reply assistance receives only the authenticated actor-safe projection and private learner preparation.

It returns text without changing state.

The Web UI submits that text through the normal message operation.

For Easy training with an external-agent next actor, a built-in NPC opening role delivers one canonical opening message at revision 0.

The speech act is `opening_offer` for a complete opening offer and `opening_position` for a partial opening position.

This presentation uses exactly the public terms in the authored opening artifact.

The presentation does not describe an `opening_position` as a complete package.

The active revision contains no hidden term that is absent from the presentation.

It does not call an external provider.

It does not change the offer, revision, round, substantive-turn count, or `next_actor`.

It does not create evidence, a belief update, or a detected-interest signal.

The opening event records `opening_kind` and the matching `speech_act`.

This behavior is session-difficulty policy.

It is not a `scenario.assistance.easy` setting.

```text
User speech, when present
  ↓
Optional STT
  ↓
Participant text
  ↓
Authenticate participant and validate command, expected revision, and turn ownership
  ↓
Build bounded actor-safe parse context from the checked session
  ↓
Extract proposed internal action, evidence, and typed term structures
  ↓
Validate against compiled knowledge definitions and term grammar
  ↓
Meaning ambiguous? ── yes ──→ Persist message and ambiguity
  │                              ↓
  │                         Return clarification_required
  no
  ↓
Apply deterministic evidence and belief updates
  ↓
Evaluate constraints and utility
  ↓
Atomically commit the authoritative action event and session revision
  ↓
Session active and next_actor uses built_in_npc? ── no ──→ Return turn result
  │
  yes
  ↓
Generate legal NPC action candidates
  ↓
Optional future fuzzy ranking of legal candidates
  ↓
Engine selection and validation
  ↓
Atomically commit the NPC intent event and session revision
  ↓
Persist a stable render identity for the approved intent
  ↓
End the SQLite write transaction
  ↓
Atomically claim the pending render job
  ↓
Build an allowlisted `NpcDialogueRequest`
  ↓
Generate contextual non-binding wording with the configured provider, or use the deterministic template
  ↓
Run deterministic output checks and a separate grounding check for novel prose
  ↓
Provider unavailable or output invalid? ── yes ──→ Use the precomputed deterministic template
  ↓
CAS-deliver one public message for the render identity
  ↓
Optional TTS
```

An LLM failure must not roll back an already committed participant action or create a duplicate turn. The processing worker must resume from the stable render identity and the last committed session revision.

An external provider call MUST occur outside a SQLite write transaction.

The claim MUST use an atomic compare-and-swap update.

Concurrent service instances MUST NOT make more than one claimed render attempt for one render identity.
That attempt MAY contain a generation call and a separate grounding-check call.

---

## Action and language-model boundary

### Parser / Extractor

Input:

- participant message;
- actor-safe visible context;
- pending actor-safe protocol context.

Output:

- proposed internal action;
- proposed claims and evidence;
- proposed typed runtime term structures;
- ambiguities;
- source spans;
- possible negotiation-skill signals.

The parser output is untrusted.

The engine validates proposed evidence against compiled knowledge definitions.

The engine validates proposed runtime terms against the compiled term grammar and authored rules.

The parser may propose an internal action, evidence record, or typed runtime term structure.

The parser cannot create ground truth, a primitive type, utility function, hard constraint, authoritative belief update, agreement, or terminal transition.

Human participants and external-agent participants use this same natural-language flow.

The public Player API does not provide typed action submission to an external agent.

### NPC action policy

Input:

- structured state;
- deterministic utility calculations;
- allowed actions;
- disclosure rules.

The engine generates legal action candidates from this input.

The engine selects and validates the authoritative NPC action.

Output:

- structured NPC intent.

Example:

```json
{
  "action": "counter_offer",
  "offer": {
    "price": 111000
  },
  "disclosure": [
    "delivery_flexibility"
  ],
  "must_not_disclose": [
    "cashflow_pressure",
    "reservation_price"
  ],
  "tone": "constructive"
}
```

The dialogue generator receives the approved `action`, approved public `offer`, approved `disclosure`, and tone. It does not receive `must_not_disclose`, raw hidden facts, reservation utility, or counterparty-private state.

### Future fuzzy policy ranker

A later policy implementation may use an LLM to rank legal action candidates.

The ranker is advisory.

The ranker cannot create a candidate, add a primitive or semantic rule, authorize a disclosure, override a hard constraint, or accept below reservation utility.

The engine remains the final selector and validator.

### Dialogue generator

Turns structured NPC intent into an actor-safe public message.

The generator receives a dedicated allowlisted `NpcDialogueRequest`.

The request contains only:

- the engine-approved speech act;
- the engine-approved public offer terms;
- the engine-approved qualitative disclosures;
- scenario language and currency;
- participant-facing term identifiers;
- public `scenario_title`, `npc_role` identifier, and `missing_term_labels`;
- engine-authored example reply options;
- the deterministic fallback;
- a bounded list of public player and NPC messages from the current session;
- `focused_term_ids`, source-attributed `conversation_memory`, selected `approved_reasons`, and delivered `disclosed_reasons`;
- allowlisted `difficulty` and `conversation_style` identifiers;
- an optional engine-authored `requested_term_id`;
- bounded active-offer `numeric_references`.

The request does not contain a raw observation, raw scenario source, role brief, raw session state, counterparty-private state, utility weights, reservation utility, BATNA utility, authored knowledge truth, distractor truth notes, constraints, private event payloads, reviews, participant credentials, provider credentials, or a list of forbidden secrets.

Every transcript entry is untrusted data.

Participant assertions MUST NOT become approved facts or disclosures.

The renderer receives credential-redacted participant text as context.

Public dialogue context MUST contain no more than 12 turns.

Each public dialogue turn MUST contain no more than 1,000 characters.

The service MUST redact the authenticated participant token, credential-shaped fragments, and known configured provider, custom-key, and administrator credential values before parsing, truncation, persistence, or provider submission.

The service MUST redact stored dialogue again when it constructs renderer context.

The allowlisted input and structured-state authority remain deterministic security boundaries.

Prompt delimiters are not a security boundary.

At startup, the service completes each unfinished durable render job with its precomputed deterministic fallback.

A pending render job blocks participant messages, hints, and administrative close operations for that session.

A create-time built-in NPC binding action uses its canonical deterministic message in the create transaction.

The create-time binding action does not create a render job or invoke a provider.

The engine supplies no more than six approved reply options.

Each option contains no more than 1,200 characters.

All options together contain no more than 4,000 characters.

Every approved reply option is an engine-authored actor-safe string.

An approved reply option does not interpolate or quote raw participant or transcript text.

A non-binding approved reply option does not contain a number, date, percentage, currency symbol, or currency code.
Novel non-binding wording MAY reference a numeric term only through the DR-28 quote-slot contract below.

For a non-binding speech act, an external provider MAY generate new wording.
The service MAY retrieve up to four prepared, case-specific reply examples before generation.
The examples MUST match the engine-selected speech act and permitted disclosures.
They MUST remain wording context and MUST NOT become a source of truth or policy authority.
The durable render plan MUST store the selected examples and library version.
Under [DR-38](decisions/2026-09-24_context-gated-reply-rag.md), an entry MAY require up to two current approved reasons.
Each selected reply MUST contain each required reason text verbatim.
An entry MAY require exact `personal_fact` or `relationship` values from the NPC-safe `training_context`.
Player text and shared background MUST NOT satisfy these gates.
Bounded local matching MAY use up to four additional patterns and sentence fragments.
Selection MUST take one reply per matching entry before additional variants and MUST deduplicate reply text.
The four-example limit and existing output checks remain mandatory.
Old plans MUST retain their stored examples when the corpus changes.

`approved_reply_options` provide examples and fallback candidates.

Under [DR-49](decisions/2026-09-26_public-position-restatement.md), a direct request for the NPC deal terms MUST return the latest public position authored by that NPC.
The engine SHOULD resolve a supported short follow-up from bounded recent dialogue.
It MUST use an active NPC offer, the latest NPC counteroffer, or the authored NPC opening position in that order.
It MUST keep a request for one authored term on the existing term-question and public-quote route.
The response MUST use the deterministic `public_position_restatement` speech act with exact engine-approved terms.
The response MUST NOT create, reactivate, revise, accept, or reject an offer.
The response MUST NOT disclose private constraints, utility, reservation utility, BATNA, or private role facts.

Under [DR-39](decisions/2026-09-24_polite-topic-return.md), a recognized unrelated question without an approved personal fact MUST receive a polite acknowledgment and return to negotiation.
The deterministic fallback MUST support this behavior without a model call and MUST be stored in the durable render plan.
The engine MUST provide several fallback variants. It MUST prefer an unused variant in the recent NPC history, then the least recently used variant.
The reply SHOULD restate the previous negotiation question or resume the current public topic.
It MUST NOT invent or deny unknown personal facts, repeat historical prices, or imply agreement.
Binding actions and mixed messages with negotiation content MUST retain their existing action handling.
Existing output validators and disclosure gates remain mandatory.

They do not restrict the vocabulary of generated replies.

The provider returns one strict JSON object with only `speech_act` and `reply`.

The deterministic validator MUST check speech-act equality, output size, requested language, structure, credentials, numeric terms, and prohibited commitments.

The validator rejects invalid JSON, unexpected fields, empty output, unsafe structure, multiple speakers, markup, tool output, URLs, and output that exceeds a bound.

Novel prose MUST pass a separate LLM grounding check before delivery.

An exact engine-authored reply option MAY bypass the grounding check.

The check receives only the same actor-safe input and candidate reply.

The check MUST reject unsupported facts, unauthorized disclosures, commitments, and contradictions of the approved intent.

The check MAY approve or reject presentation only.

The check MUST NOT change the action, utility, truth, or session state.

The semantic check is probabilistic, not a formal guarantee.

Deterministic checks cannot prove arbitrary natural-language meaning.

The service MUST NOT parse generated NPC prose back into negotiation state.

Binding `opening_offer`, `opening_position`, `offer_acceptance`, `offer_rejection`, and `complete_counteroffer` messages bypass the provider.

A revision-zero grounded opening can use a provider for wording under DR-50.

The engine inserts its exact public-position values after validation.

Each binding speech act uses the canonical deterministic template and canonical engine-approved terms.

The service uses the precomputed actor-safe deterministic template when the provider is not configured, fails, times out, returns invalid output, or violates the output contract.

The fallback uses the same approved speech act and public terms.

Dialogue rendering failure does not change the selected action, offer state, session revision, status, or turn ownership.

Rule:

> Policy decides WHAT. The renderer can select only an engine-approved way to say it.

The current rendering decisions are DR-26, DR-27, DR-28, and DR-50.

### Grounded request and persistence fields

`ParseContext` contains `active_offer_id`, `active_offer_revision`, `active_offer_terms`, `active_offer_currency`, `focused_term_id`, `expected_term_id`, and `ambiguous_offer_reference`.
The snapshot MUST contain at most 12 finite numeric public terms.
The service MUST use the active revision confirmed by public lifecycle events.
It MUST NOT obtain a baseline from an old transcript quotation.
`expected_term_id` MUST come from the latest relevant delivered public `requested_term_id`.
The provider does not select this field.

`NpcDialogueRequest.difficulty` is `guided`, `easy`, `normal`, or `expert`.
`conversation_style` is `pragmatic`, `analytical`, or `relationship_focused`.
The provider input maps these identifiers to fixed `dialogue_profile` and `conversation_style` instructions.
`requested_term_id` is an authored participant-facing term or `null`.
When it is present, the renderer MUST ask for that numeric term rather than another term.
The public `npc.intent.committed` and `npc.utterance.delivered` payloads record this identifier.
Only the delivered event can supply the next parser's requested-term context.

`numeric_references` contains at most 12 `PublicNumericReference` objects.
Each object contains `slot_id`, `offer_id`, `offer_revision`, `proposer_role`, `term_id`, `value`, `currency`, `display_text`, and `format_version`.
The slot identifier is `quote_a` through `quote_l`.
The provider uses the exact token `[[quote_a]]`, or the corresponding token for another supplied slot.
`format_version` is `1`.
The display text MUST contain at most 400 characters.
The versioned formatter MUST preserve the exact numeric value and proposer attribution.
The request MUST validate each slot against one active memory offer with the same ID, revision, role, term, and value.
The slot currency MUST match the request currency.
The service MUST NOT generate slots for accepted, superseded, rejected, withdrawn, expired, or closed offers.
The provider input includes each slot's exact `token` and `text`.
The 1,200-character reply limit applies before and after substitution.

The durable `NpcUtterancePlan.request` MUST store these request fields before provider I/O.
The enclosing plan retains `render_id`, `session_id`, `intent_revision`, `npc_participant_id`, and `action`.
Recovery MUST revalidate the stored request and use its precomputed fallback.
Historical fields default to `difficulty: normal`, `conversation_style: pragmatic`, `requested_term_id: null`, and an empty `numeric_references` list.

### Bounded exchange candidates

`scenario.exchange_policy.candidate_values` MAY define between two and 12 required terms.
It MUST include `price` or `annual_rent`.
Each term MUST have between one and 16 distinct finite numeric candidate values.
The complete candidate product MUST contain at most 512 packages.
The compiler MUST reject optional terms, unknown terms, booleans, duplicate values, and values outside the authored schema.
The engine MUST evaluate all required economic and hard-constraint conditions before selecting a candidate.
Existing scenarios without an exchange grid retain a validated fallback policy.

---

## Session state

A session may contain:

```json
{
  "id": "sess_abc123",
  "session_revision": 15,
  "parent_session_id": null,
  "source_revision": null,
  "scenario_id": "supplier_001",
  "scenario_version": 3,
  "compiled_scenario_digest": "sha256:...",
  "scenario_compiler_version": "scenario-compiler-v2",
  "language": "ru",
  "round": 8,
  "substantive_turn_count": 15,
  "round_opener": "buyer",
  "status": "active",
  "next_actor": "buyer",
  "reveal_policy": "active_player",
  "active_offers": [],
  "active_offer_sets": [],
  "pending_clarification": null,
  "pending_acceptance_confirmation": null,
  "candidate_deal": {
    "runtime_terms": []
  },
  "reality_state": {},
  "revealed_by_participant": {
    "buyer": {},
    "seller": {}
  },
  "belief_state_by_participant": {
    "buyer": {},
    "seller": {}
  },
  "rapport": 0.74,
  "agreement_status": {}
}
```

---

## History

Store both:

### Raw transcript

Human-readable conversation.

### Structured event log

Example:

```text
ROUND 5

PARTICIPANT_ACTION:
  conditional_offer

STATE_EFFECT:
  evidence_validated:
    interest.buyer.delivery.importance
  belief_updated:
    observer=seller confidence=0.10->0.52
  true_disclosure_checked:
    result=matching_permitted_disclosure
  runtime_term_validated:
    type=delivery_schedule
  offer_lifecycle:
    revision_2=active->superseded
    revision_3=null->active

UTILITY:
  buyer  76 -> 84
  seller 74 -> 79
```

This enables replay, analytics, and branching.

Also store the exact observation, assistance, hint, distractor, and public message delivered to each participant.

Each delivery record identifies the participant, language, reveal policy, and source event.

State reconstruction never invokes an LLM.

The event log stores validated evidence, belief updates, runtime term trees, and utility results.

Replay reapplies these validated transitions.

---

## Event sourcing

Recommended from the beginning.

Example:

```text
Event 1: SELLER_OFFER
Event 2: BUYER_PROBE
Event 3: SELLER_CONCESSION
Event 4: BUYER_PROBE
Event 5: SELLER_REVEAL
Event 6: BUYER_CONDITIONAL_OFFER
```

Current state can be reconstructed from events or accelerated with snapshots.

---

## Branching

Store:

```text
parent_session_id
source_revision
```

`source_revision` identifies state after the exact committed parent revision.

The child inherits offer status, `next_actor`, pending clarification, pending acceptance confirmation, delivered information, and run configuration at that revision.

The child preserves inherited offer IDs and revisions.

The child starts at `session_revision = source_revision`.

Its first child-local event uses `source_revision + 1`.

An authorized training orchestrator may override model or policy configuration in the child.

The child records each override.

This enables:

- retry from a weak move;
- compare two strategies;
- decision tree visualization;
- educational replay.

---

## Scope handling

A scenario defines which topics are negotiable and at what depth.

Example:

```yaml
scope:
  price:
    depth: full
  payment:
    depth: full
  delivery:
    depth: full
  warranty:
    depth: medium
  rma:
    depth: principle_only
  governing_law:
    depth: excluded
```

If the user dives into out-of-scope legal drafting, the NPC should acknowledge and move back to agreed commercial principles.

An authored latent term may become available when its authored activation condition occurs.

A participant may create a concrete composite term at runtime.

The composite must use compiled term primitives and authored capabilities, constraints, composition rules, and evaluation rules.

Examples include a split-delivery schedule and a contingent reserve policy.

A valid composite is a runtime term instance. It can affect utility without being enumerated as a complete package in the scenario file.

A proposal outside the compiled term grammar is an `unscored_proposal`.

The NPC may clarify, discuss, or decline an `unscored_proposal`.

An `unscored_proposal` cannot affect deal validity or utility. It cannot become part of a binding agreement.

See `docs/knowledge-and-emergent-state.md` for the normative state model.

---

## Agreement completeness

Track required and optional dimensions.

Example:

```text
price            agreed
quantity         agreed
delivery         agreed
payment          agreed
FOC              agreed
RMA principle    agreed_in_principle
```

Completeness should encourage closing but must not force a participant to accept a deal below reservation utility.

The authoritative acceptance threshold is `reservation_utility`.

An acceptable deal must satisfy every hard constraint and `U(deal) >= reservation_utility` for each accepting participant controlled by the built-in policy.

A human or external agent may accept a deal below its own reservation utility when every hard constraint passes.

The post-game review should identify that failure.

A scenario may intentionally have no ZOPA. A rational walk-away is a successful training outcome for such a scenario.

Every formal offer revision is immutable and contains a materialized term package.
The package MAY remain incomplete before binding acceptance.

An ordinary counteroffer supersedes its referenced revision.

Several active alternatives require an explicit MESO offer set.

Binding acceptance by a human or external-agent participant requires a context-aware acceptance intent and a separate confirmation of one complete active offer revision.

A built-in NPC uses one typed engine-confirmed acceptance transition after deterministic validation.

Text such as `согласен` cannot bind an agreement when the context can refer to one condition or an agreement in principle.

The engine returns `clarification_required` for ambiguous meaning.

The terminal states are `agreement_reached`, `walked_away`, `expired`, `aborted`, and `technical_failure`.

See `docs/offer-session-protocol.md` for the normative state machine.

---

## Goal-based final review (DR-33)

Status: accepted requirement. Bounded implementation delivered under [DR-36](decisions/2026-09-24_training-loop.md).

The terminal training review MUST include LLM analysis of progress toward the participant's recorded goals and actionable recommendations.
The engine MUST supply the authoritative outcome, constraints, utility, and any numeric goal-progress measures.
Each evaluative claim and recommendation MUST reference supporting session evidence or an authored goal or rule.
The review MUST distinguish observed results from hypotheses about alternative actions.
The review MUST enforce actor-specific disclosure permissions and the benchmark run-set release gate.
An unavailable or invalid LLM analysis MUST leave the deterministic outcome report available and identify the missing analysis.

The review task is separate from the NPC rendering task.
It MAY use the same provider and model.
The service MUST build the permitted review projection before model submission.
The reviewer MUST NOT modify session state or deterministic scores.
Transcript content MUST remain untrusted data in the review prompt.
The service MUST validate evidence references, numeric claims, and disclosure scope before delivery.
The review call MUST occur outside a database write transaction.
The [human training guide](human-training-guide.md) defines the implemented cache and API extension.

See [DR-33](decisions/2026-09-23_goal-based-llm-review.md) and [the review design](social-state-and-llm-dialogue.md#71-final-goal-based-review-dr-33).

---

## Provider abstraction

The LLM gateway should support multiple providers without leaking provider-specific logic into the domain engine.

The built-in NPC dialogue renderer supports these modes:

- `template`;
- `openai`;
- `qwen`.

`template` is the default mode.

The configured provider generates wording for an engine-approved non-binding speech act.
It does not select an action or authorize a disclosure.

Provider credentials come from the configured process-environment variable.

Standard provider configuration MUST bind the provider to its expected credential variable.

A custom credential variable or base URL requires explicit operator configuration.

The service does not copy a credential into `NpcDialogueRequest`, prompt content, state, persistence, telemetry, or public output.

The service calls an external provider outside SQLite write transactions.

One durable render job has at most one claimed render attempt.
That attempt MAY contain a generation call and a separate grounding-check call.
Both calls MUST occur outside SQLite write transactions.
An invalid or failed check MUST use the precomputed deterministic fallback.
An unvalidated candidate and the check's raw response MUST NOT enter persistence, telemetry, or public output.

The service records only `provider_failure`, `output_invalid`, `renderer_failure`, or `restart_recovery` as a failure reason.

The service bounds and sanitizes provider and model identifiers before persistence or public release.

It does not persist a raw prompt, raw provider response, or raw provider error.

OpenAI rendering defaults to `gpt-5.6-luna`.

Qwen rendering defaults to `qwen3.8-max` and the QwenCloud Token Plan endpoint.

The built-in NPC renderer does not read ambient `QWEN_BASE_URL`.

The service does not send `temperature` when `NEGOTIATION_NPC_TEMPERATURE` is empty.

The service supports independent dialogue, control, and review provider profiles under DR-46.

The dialogue provider writes non-binding NPC prose.

The control provider checks novel prose, classifies social events, and performs optional semantic extraction.

The review provider writes final coaching from the actor-safe evidence package.

An unset control profile reuses the dialogue provider.

An unset review profile reuses the control provider.

The selected live launcher uses `qwen-flash-character`, `DeepSeek-V4-Flash-0731`, and `Qwen3.8-Max` through the QwenCloud Pay-as-you-go endpoint.

The selected launcher disables thinking for bounded control and review JSON tasks.

The Qwen adapter sends `enable_thinking` only when the selected profile defines it.

The benchmark run configuration keeps model, provider, version, temperature, and seed metadata for reproducibility.

The benchmark run configuration also keeps language, scenario digest, prompt versions, policy version, engine version, assistance configuration, and reveal policy.

---

## Hidden-state release

An active participant receives only an actor-safe projection.

The dialogue renderer receives a separate actor-safe projection in `NpcDialogueRequest`.

The service constructs this projection from the approved NPC speech act and public context.

The renderer MUST NOT receive a raw `SessionState`, a full internal event, a role brief, or another participant's observation.

The service MUST project authored role data into a structured `RoleBrief`.
The projection contains `summary`, `objectives`, `context`, `batna`, `constraints`, and `priorities`.
The projection MUST omit `reservation_utility`, BATNA utility, and interest weights.
The projection MUST omit role data for the counterpart.
The UI MAY localize field labels and format values.
The structured values remain the source of truth for display.

A completed training session may receive selected hidden information when the scenario review policy permits it.

The review records each released item and its training purpose.

A benchmark trial keeps hidden information sealed until the complete run set is finished.

Author and administrator access uses a separate privileged projection.

Under [DR-40](decisions/2026-09-24_llm-debug-window.md), the service MUST provide a separate LLM diagnostics page at `/llm-debug`.
Under [DR-41](decisions/2026-09-24_local-llm-debug-access.md), the local page MUST load traces without sign-in.
Both trace endpoints MUST allow a loopback client using a loopback host without a credential.
A supplied `Origin` MUST match the API origin for this exemption. Other requests MUST require the administrator credential.
The exemption MUST NOT apply to other administrator or Player API operations.
The Player API MUST NOT include traces.
Capture MUST require `NEGOTIATION_LLM_TRACE=true`. It MUST NOT require an administrator credential.
The recorder MUST exclude benchmark calls.
The recorder MUST redact known credentials before storage.
It MUST mask credential header values and MUST NOT store raw provider exception messages.
Under [DR-44](decisions/2026-09-25_complete-llm-requests.md), capture each outgoing request at the provider transport boundary.
Show the method, resolved URL, redacted headers, complete JSON body, timeout, and attempt number.
The recorder MUST NOT truncate retained prompts, messages, request bodies, or response text.
The recorder MUST keep at most 200 records and 64 MiB of serialized trace data in process memory.
It MUST evict complete records in start order when either limit is exceeded.
An oversized record is evicted instead of being shortened.
The recorder MUST NOT write trace contents to disk.
Request observation MUST NOT mutate outgoing requests or interrupt negotiation on observer failure.
Use separate observation contexts for concurrent calls.
Application context limits still apply before submission.
Provider-internal instructions and HTTP-library-generated headers are outside this trace.
Trace responses MUST use `Cache-Control: no-store`. Trace operations MUST appear in OpenAPI.
The trace window MUST NOT change engine decisions or session history.
Under [DR-42](decisions/2026-09-24_llm-debug-links.md), `/llm-debug#<trace_id>` MUST address one trace.
Instructions, each input message, and the response MUST have section links under that fragment.
Direct navigation, reload, and browser history MUST restore selection. Polling MUST preserve it.
An unavailable trace MUST show an explicit message. The page MUST NOT substitute another record.
Links MUST contain only an opaque trace ID and an optional section ID. Trace retention and access rules remain unchanged.
The implemented provider wrapper captures calls associated with existing training-session HTTP requests.
It records a running entry before the call and a completed or error entry after it.
Generation and grounding are separate calls. Transport retries remain inside one application call.
Each retry has a complete request snapshot and a section link such as `/llm-debug#<trace_id>/request-0`.
Records disappear on restart. The single-worker local launcher enables capture by default.
See [the usage guide](llm-debug-guide.md) for authentication, bounds, and operational limits.

The Admin Session Inspector uses a read-only administrator projection.

The projection requires the `NEGOTIATION_ADMIN_TOKEN` Bearer credential.

The projection MAY contain session metadata, participant controller metadata, transcript messages, public event payloads, immutable offer revisions, public `dialogue_quality` diagnostics, and an allowed public review.

The projection MUST omit participant credentials, credential hashes, raw `SessionState`, scenario source, private event payloads, and private review data.

An active session has no administrator review projection.

A benchmark review remains sealed until the complete declared run set is terminal.

A terminal training session or a released benchmark session MAY expose only the stored public review through the Inspector.

`dialogue_quality.version` is `1`.
Its `turns`, `repetition`, and `rendering` fields are technical diagnostics.
Its `human_review` fields remain unrated in the API.
The offline evaluator supports human ratings with source references.
Neither path changes utility or benchmark-review release policy.
See the [dialogue evaluation rubric](dialogue-evaluation-rubric.md) for definitions, bounds, coverage, and offline commands.

---

## Benchmark execution

Each independent benchmark trial uses a fresh session.

Each tested agent plays both roles.

The runner repeats trials under one fixed run configuration.

The run configuration pins the scenario version and digest, language, model and provider versions, prompts, policy, generation parameters, and randomness settings.

Benchmark trials disable hints and training assistance.

Forked sessions support training and branch comparison. They are not independent benchmark trials.
