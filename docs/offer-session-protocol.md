# Offer and Session Protocol

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

## Grounded dialogue extension (DR-28)

[DR-28](decisions/2026-09-06_grounded-negotiation-dialogue.md) applies before offer transitions and NPC delivery.
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
Admin diagnostics MUST use public transcript, public renderer events, and bounded telemetry only.
They MUST distinguish exact repetition, question repetition, latency, fallback rate, and categorized validation failures.
Missing telemetry MUST remain unavailable rather than zero.
Heuristics MUST NOT be presented as proof of relevance or factual correctness.
Offline human scorecards MUST retain versioned source references and rating coverage.
Unrated dimensions MUST remain unrated.
The regression corpus MUST cover connected Russian and English dialogue, numeric questions, relative changes, short replies, corrections, repetitions, and false claims.
Existing privacy, confirmation, immutable-version, and durable-render boundaries remain required.

## Status

This document is normative.

Alexander Shmelev accepted this protocol on 2026-08-27.

Alexander Shmelev accepted the partial-opening update in DR-18 on 2026-08-28.

The protocol applies to human participants and external-agent participants.

## Core invariants

- Structured state is the source of truth.
- The public Player API accepts natural-language participant messages.
- A human and an external agent use the same Player API behavior.
- A parsed message proposes an internal action.
- The engine validates every internal action.
- Only an engine-validated transition can change the deal state.
- Only an engine-confirmed acceptance transition can create a binding agreement.
- The engine checks every hard constraint before binding an agreement.
- A built-in policy MUST NOT accept below `reservation_utility`.
- A human or external agent MAY accept below its own `reservation_utility`.
- The review MUST identify such an outcome as a negotiation failure.
- A runtime composite can use authored primitives, capabilities, and evaluation rules.
- A proposal outside the compiled scenario grammar has no utility value.
- Such a proposal cannot become part of a binding agreement.
- Every mutation of an existing session uses an idempotency key and an expected session revision.
- Session creation uses an idempotency key and has no expected session revision.
- The event log stores every authoritative transition.

The knowledge and runtime-term boundary is defined in `docs/knowledge-and-emergent-state.md`.

## Session initialization

Exactly one scenario role MUST define exactly one authored opening artifact.

The artifact is either `opening_offer` or `opening_position`.

Public scenario metadata MAY use `opening_offer_role` as a compatibility field for the role that owns either artifact.

An `opening_offer` MUST contain every required term.

An `opening_position` MAY omit required terms.

An `opening_position` MUST contain at least one authored term.

The service commits the authored opening artifact as the initial active offer revision at `session_revision = 0`.

The initial active revision MUST contain exactly the terms in the authored artifact.

An omitted required term is `UNSPECIFIED`.

The service MUST list each omitted required term in `unresolved_required_terms`.

The compiler and service MUST NOT infer, copy, default, or substitute a value for an omitted term.

An explicit zero is a real term value. It is not `UNSPECIFIED`.

In a human-versus-built-in-NPC training session, the human is `next_actor`.

The authored opening artifact remains structured session state.

The built-in NPC sends one opening message at `session_revision = 0` before the human's first message.

The greeting MUST refer to the public scenario title and MUST use the session language.

For a scenario version without `dialogue_strategy`, `first_meeting` MUST use the neutral greeting.

For a scenario version without `dialogue_strategy`, `successful_history` MUST use one of the bounded authored relationship-aware greetings.

The service MUST select that greeting with a stable session-scoped digest.

The greeting MAY signal prior familiarity or collaboration.

It MUST NOT invent a historical term, concession, promise, event, or current agreement.

For a scenario version with `dialogue_strategy`, the opening MAY state only engine-formatted terms selected from the authored opening artifact.

The grounded opening MUST use exact engine-owned placeholders before the engine inserts the title, optional player name, and public terms.

The grounded opening MUST NOT create or change a term, concession, commitment, agreement, or lifecycle action.

The greeting MUST NOT commit an action or change the session revision, round, substantive-turn count, active offer, or `next_actor`.

The event log records one `npc.greeting.delivered` event.

A create-session idempotency replay MUST NOT duplicate the opening message or event.

For other session types, the other participant remains `next_actor`.

In an Easy training session with an external-agent next actor, a built-in NPC opening role MUST present the authored public opening terms in the transcript.

The presentation uses a deterministic canonical template.

Its speech act matches the authored artifact: `opening_offer` or `opening_position`.

The presentation MUST contain exactly the authored public terms.

The presentation MUST NOT imply that an `opening_position` is a complete package.

The presentation MUST NOT add an active term that is absent from the authored opening artifact.

The presentation has `session_revision = 0` and is not a substantive action.

It MUST NOT change the offer, session revision, round, substantive-turn count, or `next_actor`.

It MUST NOT create negotiation evidence, a belief update, or a detected-interest signal.

It MUST NOT call an external dialogue provider.

The event log records one `npc.opening_utterance.delivered` event.

The event identifies whether the authored artifact is `opening_offer` or `opening_position`.

A create-session idempotency replay MUST NOT duplicate the message or event.

The service MUST NOT synthesize an opening message for a human or external-agent opening role.

## Public message model

For a non-binding NPC speech act, the service MAY retrieve prepared reply examples from a versioned local library.
Retrieval MUST occur after the engine selects the action and permitted disclosures.
The service MUST filter examples by scenario, role, language, speech act, and required approval.
Retrieved text MUST remain a wording example and MUST NOT change the action, terms, or disclosure policy.
The durable render plan MUST retain the exact selected examples and library version.
Canonical binding speech acts MUST NOT use retrieved wording.

Human participants and external-agent participants submit natural-language messages.

The public Player API MUST NOT provide a typed action endpoint to an external agent.

The Web UI MAY provide controls for common responses.

Such a control MUST submit a canonical natural-language message through the same Player API flow.

The CLI and benchmark runner use the same flow.

STT produces canonical text before this flow begins.

## Internal action model

The parser maps a participant message to one proposed internal action.

The internal action union includes:

- `inform`;
- `question`;
- `offer`;
- `counter_offer`;
- `offer_set`;
- `acceptance_intent`;
- `confirm_acceptance`;
- `reject`;
- `withdraw`;
- `walk_away`;
- `pass`;
- `clarification_response`.

The parser output is untrusted.

The parser MUST NOT commit an action.

The engine validates the action against the session state, authored terms, turn policy, and participant permissions.

Built-in controllers and replay controllers MAY use a typed internal controller interface.

That interface is not part of the public Player API.

## Offer model

Every formal offer revision contains:

- `offer_id`;
- `offer_revision`;
- `proposer_participant_id`;
- `base_offer_id`, when applicable;
- `base_offer_revision`, when applicable;
- `offer_set_id`, when applicable;
- a materialized term package;
- unresolved required terms;
- creation session revision.

An offer revision is immutable.

Offer lifecycle status is separate from immutable offer content.

`OfferLifecycleState` maps each offer revision to its current status.

The pair of `offer_id` and `offer_revision` identifies the revision.

A new independent offer starts at revision `1`.

An ordinary counteroffer references the active revision and increments `offer_revision`.

The participant may express only changed terms.

The engine carries unchanged terms from the referenced revision into the new materialized package.

The participant may remove an authored optional term with an explicit natural-language instruction.

The parser maps this instruction to an internal `unset` operation.

The engine MUST reject an attempt to unset a required term.

An offer can remain incomplete during negotiation.

Every required term MUST be resolved before binding acceptance.

An active revision created from `opening_position` cannot bind while `unresolved_required_terms` is not empty.

The service MUST NOT create a pending acceptance confirmation for an incomplete revision.

## Offer status and lifetime

`OfferLifecycleState` uses these statuses:

- `active`;
- `superseded`;
- `withdrawn`;
- `rejected`;
- `accepted`;
- `expired`.
- `closed_by_termination`.

An ordinary counteroffer supersedes its referenced active revision.

A superseded revision cannot become active again.

A participant cannot accept a superseded revision.

An active offer remains active until one of these events occurs:

- the proposer withdraws it;
- a counteroffer supersedes it;
- the recipient rejects it;
- the recipient accepts it;
- the session terminates.

The proposer MAY withdraw an active offer before acceptance.

The proposer MUST NOT withdraw an accepted offer.

An attempt to accept an inactive revision returns HTTP `409` with code `offer_not_active`.

The server records the participant message and failed acceptance result before it returns this conflict.

The failed acceptance does not consume a negotiation round.

The response identifies the post-recording session revision and the current active offer, when one exists.

## MESO offer sets

Several offers can remain active only as alternatives in one explicit MESO offer set.

Every alternative has its own `offer_id` and `offer_revision`.

Every alternative shares one `offer_set_id`.

All alternatives in one set have the same proposer and recipient.

Acceptance of one alternative accepts that alternative and expires every sibling alternative.

A counteroffer to a MESO alternative supersedes the complete referenced offer set.

The counterparty MUST create a new explicit offer set to keep several new alternatives active.

The proposer MAY withdraw one alternative while the other alternatives remain active in the explicit set.

The recipient MAY reject one alternative while the other alternatives remain active in the explicit set.

## Context-aware interpretation

The parser evaluates a message against:

- the complete current message;
- the preceding public dialogue;
- the active offer or offer set;
- the pending clarification, when one exists;
- the pending acceptance confirmation, when one exists.

The parser MUST distinguish these meanings:

- acknowledgement of information;
- agreement with one condition;
- `agreed_in_principle`;
- intent to accept a complete offer;
- ambiguous agreement.

The word `согласен` alone does not create a binding agreement.

The parser MUST consider the surrounding context before it classifies `согласен` or an equivalent phrase.

If the context does not identify one meaning with sufficient confidence, the engine requests clarification.

`agreed_in_principle` is non-binding.

Partial acceptance is not binding.

A proposed modification creates a counteroffer.

A natural acceptance phrase that names the offer, the terms, or the package is an acceptance intent. Examples: `принимаю ваше предложение целиком`, `согласны на ваше встречное предложение`, `we accept your offer`.

A negated acceptance phrase is not an acceptance intent.

An acceptance phrase that also states a new term value is a counteroffer with that value. This rule also applies while an acceptance confirmation is pending.

A positive, unquoted assertion that restates every term of the counterpart's complete active revision is an acceptance intent.
A question or reported quotation MUST NOT become an acceptance intent through numeric matching.
The engine does not create a duplicate offer revision for a valid acceptance intent.

A bare agreement word such as `согласен`, `договорились`, or `ok`, with or without punctuation, requires clarification.

The parser reads number words and thousand or million abbreviations, for example `сто десять тысяч`, `110 тыс.`, `1,2 млн`, `thirty percent`, `six weeks`.

The server MUST build `ParseContext` only after participant authentication, expected-revision validation, and turn validation.
The snapshot contains `active_offer_id`, `active_offer_revision`, `active_offer_terms`, `active_offer_currency`, `focused_term_id`, `expected_term_id`, and `ambiguous_offer_reference`.
It MUST contain at most 12 finite numeric public terms.
The active baseline MUST match one active public offer revision from lifecycle state.
The parser MUST NOT select a superseded offer or a historical transcript quotation as its baseline.

The parser MAY resolve one `на` or `by` delta against that baseline.
A monetary delta MAY be an absolute amount or a percentage of the baseline.
A prepayment delta MUST identify percentage points.
Week and quantity values MUST remain integral.
The parser MUST request clarification for ambiguous units, several referents, missing baselines, unsupported calculations, and unsupported date expressions.
It MUST NOT treat a relative amount as an absolute offer price.
It MUST exclude questions and quotations before term extraction.
It MUST exclude a complaint about a term before term extraction unless the same clause contains explicit proposal intent.
This rule applies to every supported term, including price, payment, quantity, and delivery duration.
The parser MUST evaluate contrast clauses such as `но`, `зато`, `однако`, and `however` independently.
An explicit proposal clause in a mixed message MAY still create a counteroffer.

An unlabelled short numeric answer MUST identify one unambiguous public focus or requested term.
Conflicting focus and requested-term context MUST request clarification.
`expected_term_id` MUST come from the latest relevant delivered NPC event's engine-authored `requested_term_id`.
A pending intent or generated question alone MUST NOT establish this field.
The public Player API MUST NOT let a client supply this context directly.

## Clarification flow

Semantic ambiguity does not change the deal or offer state.

The server persists the original message and an ambiguity event.

The response sets `result` to `clarification_required`.

The response includes an actor-safe clarification question.

The response MAY include actor-safe candidate interpretations.

The response keeps `next_actor` assigned to the same participant.

A clarification request does not consume a negotiation round.

A clarification response does not consume a round until it resolves to a substantive action.

The resolved substantive action consumes a turn.

The Web UI and CLI MUST show that clarification is required.

An external agent receives the same explicit result and clarification question.

A parser schema or transport failure permits one retry.

A semantic ambiguity does not use this retry.

The system requests clarification immediately for semantic ambiguity.

If the parser retry fails, the server persists a `parser_failure` event and preserves deal state.

It returns `clarification_required` with reason `parser_unavailable` and an actor-safe deterministic request to restate the message.

The same participant remains `next_actor`.

This fallback does not increment `substantive_turn_count` or consume a round.

New training sessions pin `training-clarification-v1`.

A parser clarification in such a session MUST NOT terminate the session.

After three consecutive clarifications, the response MUST include `clarification.recovery`.

The object contains `version`, `example`, and `end_session_message`.

The example is actor-safe and uses supported proposal wording.

When available, the example identifies unresolved required terms.

The end message is `Прекращаю переговоры.` for Russian or `I walk away.` for English.

The participant remains `next_actor` until a substantive action or explicit exit occurs.

The authenticated session projection MUST retain the same recovery object while the clarification is pending.

A reload or service restart MUST NOT remove this recovery object.

Training-mode HTTP 4xx transition failures, acceptance-confirmation openings, and confirmation cancellations MUST NOT consume the protocol-control termination allowance.

Benchmark mode retains the configured bounded protocol-control termination rule.

## Binding acceptance flow

Binding acceptance uses two steps.

This two-step flow applies to natural-language human and external-agent controllers.

### Step 1: acceptance intent

The participant sends a natural-language message.

The parser can classify the message as `acceptance_intent` only when the context refers to one complete active offer revision.

The engine verifies that all required terms are resolved.

The engine verifies every hard constraint.

The engine then creates a pending acceptance confirmation.

The pending confirmation identifies the exact `offer_id`, `offer_revision`, participant, and session revision.

The response sets `result` to `confirmation_required`.

The response shows the complete materialized offer.

The response keeps `next_actor` assigned to the same participant.

This step does not create an agreement.

This step does not consume a negotiation round.

This step does not increment `substantive_turn_count`.

### Step 2: confirmation

The participant confirms or cancels in natural language.

The Web UI MAY render confirm and cancel controls.

The controls submit canonical natural-language messages.

An external agent receives the same pending confirmation and responds in natural language.

The parser maps an unambiguous positive response to `confirm_acceptance`.

The engine verifies the pending confirmation and exact offer revision again.

The engine then commits the agreement atomically.

The confirmation does not increment `substantive_turn_count`.

The accepted deal becomes immutable.

The session enters `agreement_reached`.

A negative response cancels the pending confirmation.

A negative response does not increment `substantive_turn_count`.

The same participant remains `next_actor` after cancellation.

An ambiguous response returns `clarification_required`.

An ambiguous response does not increment `substantive_turn_count`.

The pending acceptance remains active while the participant clarifies the confirmation response.

The same participant remains `next_actor`.

A response that adds or changes a term cancels the pending confirmation and creates a counteroffer.

The committed counteroffer increments `substantive_turn_count` and consumes the participant's substantive turn.

The first acceptance-intent message cannot bypass the confirmation step.

A built-in NPC uses the typed internal controller interface.

It can accept in one engine transition after deterministic validation.

## Turn ownership

The engine computes `next_actor` from the deterministic session state machine.

The MVP does not use free-form concurrent writes.

Each session has one serialized writer.

The default two-party turn cycle gives each participant one substantive action.

`substantive_turn_count` is the authoritative counter for committed substantive participant actions.

A round begins when control first passes to the configured round opener.

A round completes after both participants commit at least one substantive action and control would return to the round opener.

An authored consecutive action remains inside the current round until both participants have acted.

A clarification message and an acceptance-confirmation message are protocol-control messages.

Protocol-control messages do not consume a negotiation round.

In training sessions that pin `training-clarification-v1`, these messages do not consume a termination allowance.

In benchmark sessions, the configured protocol-control limit remains authoritative.

A valid `pass` consumes a turn.

The scenario policy must explicitly permit `pass`.

A built-in NPC MAY ask a question, request clarification, hold its position, reject an offer, or walk away without a counteroffer.

A built-in NPC MUST NOT evaluate an incomplete active revision as a complete package.

It preserves the incomplete revision and MAY request the missing required terms by name.

While an incomplete revision is active, a built-in NPC still answers a greeting, a priority question, or a general question before it repeats the request for the missing terms.

An explicit request to discuss one authored term MUST take precedence over a generic discussion cue.

An incomplete valid price proposal MUST NOT force an immediate complete-package request when a focused non-binding response is available.

The engine MAY select `focused_discussion` or `acknowledge_partial_offer` before rendering.

An explicit topic switch MUST replace the previous focus.

A postponed topic MUST remain unresolved and MAY resume after a later explicit request.

All omitted required terms MUST remain `UNSPECIFIED`.

Binding acceptance MUST still require a complete validated package.

A built-in NPC MUST NOT bind a package that violates a hard constraint of any role, even when the package satisfies its own reservation utility.

A built-in NPC counteroffer MUST NOT reverse its previous public monetary concession.
The NPC anchors a later monetary counter on its own previous counter, not on the opening terms.
Other terms MAY change only as part of a validated package.

An authored `exchange_policy.candidate_values` grid MUST contain between two and 12 required terms.
It MUST include `price` or `annual_rent`.
Each term MUST have between one and 16 distinct finite numeric values that pass its schema.
The compiler MUST limit the complete candidate product to 512 packages.
The policy MUST evaluate a complete candidate before selecting it.
The candidate MUST satisfy every role's hard constraints and the NPC reservation utility.
The policy MUST NOT optimize counterpart private utility.
It SHOULD prefer a monetary concession with a nonmonetary change that improves NPC utility.
The selected public terms are the only basis for the exchange explanation.
An incomplete offer MUST NOT trigger implicit completion by the exchange policy.
Without a supported exchange, the NPC MUST use a validated fallback or rejection.

When one participant uses the built-in NPC as the counterparty, the service automatically runs the built-in NPC after a valid substantive participant action.

The request can return the committed participant result and the generated NPC response.

The service commits the participant action and NPC action as separate atomic transitions.

In an external-agent-versus-external-agent session, one request commits at most one participant action.

The response always identifies `next_actor` or a terminal status.

The engine evaluates `max_rounds` only after a complete round and after it resolves any pending clarification or acceptance confirmation.

## Concurrency and idempotency

A new session starts at `session_revision = 0` after the initial state is committed.

Every request that mutates an existing session includes `idempotency_key` and `expected_revision`.

Session creation includes `idempotency_key` only.

A repeated idempotency key returns the stored result of the first request that used that key.

The create-session response delivers participant credentials only once.
The stored create-session result excludes credentials.
A repeated create-session request returns the same session with `credential_delivery: initial_response_only`.

This rule includes stored domain-error results.

A mismatched expected revision returns HTTP `409` with code `revision_conflict`.

The response includes the current session revision.

No parser, policy, validator, or NLG retry can append the same authoritative action twice.

## Conversation memory and authored reasons

These rules implement [DR-27](decisions/2026-09-06_conversation-continuity.md).

The service MUST derive conversation memory deterministically from durable public messages and public events in the current session.
Memory MUST contain a version and source message or event references.
The service MUST rebuild memory after restart without process-local state.
It MUST NOT use an LLM summary as authoritative memory.
The renderer projection MUST remain bounded and validated.
The service MUST redact credentials before memory construction and truncation.
Memory MUST NOT contain role briefs, private event payloads, hidden knowledge, utility values, or another session's data.

Memory MAY retain explicit and postponed topics, attributed participant statements, question-response references, public offer revisions, and a binding agreement.
An event-derived offer or agreement MUST remain distinct from a participant claim.
Each remembered offer MUST retain its lifecycle status and the public event reference that establishes that status.
Public lifecycle events MUST control historical offer status.
The renderer MUST NOT present an inactive historical offer as active.
A question followed by a reply MAY be marked `responded`.
Chronology alone MUST NOT mark the question `answered`.
Topic extraction MUST use participant text and engine-authored metadata.
It MUST NOT parse generated NPC prose into negotiation state.
A reply, claim, question, or postponed topic MUST NOT become an agreement or ground truth.

Under [DR-49](decisions/2026-09-26_public-position-restatement.md), a direct request for the NPC terms MUST use the latest public position authored by that NPC.
A supported short follow-up MAY resolve against bounded recent dialogue about deal terms.
A request that names one authored term MUST retain the existing term-question and public-quote behavior.
The restatement MUST preserve the exact public term values.
It MUST NOT change offer lifecycle state.
An inactive position MUST remain historical and non-binding.
The restatement MUST NOT expose private constraints, utility, reservation utility, BATNA, or private role facts.

A role MAY define `dialogue_reasons` in a new immutable scenario version.
Each reason MUST contain `id`, `term_id`, `text`, `source_ref`, and `disclose_when`.
`source_ref` MUST reference that role's `brief.objective` or `brief.context`.
`disclose_when` MUST be `on_topic_question` in this increment.
The compiler MUST validate identifiers, uniqueness, topic references, source references, limits, and plain nonnumeric text.
Each role MAY define at most six reasons.
Each reason text MUST contain at most 300 characters.
The author remains responsible for semantic grounding in the referenced authored source.

The engine MAY disclose at most two reasons per reply when the participant asks about the matching term or asks a contextual follow-up about the current topic.
The renderer MUST receive only selected reason identifiers and texts, plus previously delivered public reason history.
It MUST NOT receive the private source text or unselected private reasons.
Only delivered disclosures MAY enter persistent disclosed-reason history.
A pending or failed render MUST NOT prove disclosure.
The renderer MUST include every text from `approved_reasons` verbatim in the reply.
It MUST reject generated text that omits or paraphrases a selected reason instead of including the exact text.
After a reason is delivered, the engine MUST NOT select it again for `approved_reasons`.
The renderer MAY use that reason from `disclosed_reasons` without verbatim repetition.
Only an exact reason text in the delivered message qualifies for the public `disclosed_reason_ids` metadata.
A paraphrase alone MUST NOT prove disclosure.
Reasons MUST NOT change utility, acceptance thresholds, hard constraints, or capabilities.
Old scenario versions MUST remain unchanged and valid without reasons.
Historical render plans without conversation memory or authored reasons MUST remain readable.

## Grounded rendering fields

The durable `NpcDialogueRequest` includes `difficulty`, `conversation_style`, `requested_term_id`, and `numeric_references`.
`difficulty` MUST be `guided`, `easy`, `normal`, or `expert`.
`conversation_style` MUST be `pragmatic`, `analytical`, or `relationship_focused`.
The provider receives fixed instructions as `dialogue_profile` and `conversation_style`.
These profiles MUST NOT alter economic truth or disclosure permissions.
The Easy canonical opening rule applies when the next actor is an external agent.

`requested_term_id` MUST be an authored participant-facing identifier or `null`.
The engine MUST select it before rendering.
When it is present, a generated numeric-answer question MUST concern that term only.
Both `npc.intent.committed` and `npc.utterance.delivered` record the field.
Only actual delivery can supply the next parser's requested-term context.

The numeric reference list MUST contain at most 12 unique slots named `quote_a` through `quote_l`.
Each slot contains `slot_id`, `offer_id`, `offer_revision`, `proposer_role`, `term_id`, `value`, `currency`, `display_text`, and `format_version`.
`format_version` MUST be `1` in this increment.
`display_text` MUST contain at most 400 characters and MUST preserve exact value and attribution.
The request MUST validate each slot against one active public offer and the request currency.
Inactive or omitted terms MUST NOT receive a slot.
The provider MUST emit the exact supplied token, such as `[[quote_a]]`, instead of writing a number.
The service MUST substitute the engine-authored display text.
It MUST reject unknown, altered, repeated, or unbound tokens.
The reply MUST satisfy the 1,200-character limit before and after substitution.
The resolved reply MUST pass all applicable deterministic and grounding checks.
Quoted terms remain proposals, not new commitments or agreements.

The enclosing durable plan retains `render_id`, `session_id`, `intent_revision`, `npc_participant_id`, `action`, and `request`.
It MUST preserve the approved references before provider I/O.
Recovery MUST revalidate the request and retain its original revision binding.
Old requests default to Normal difficulty, pragmatic style, no requested term, and an empty reference list.
The existing atomic render claim, compare-and-swap delivery, and same-session pending-render lock remain required.

## Built-in NPC dialogue failure handling

Opening presentation, binding acceptance, rejection, complete counteroffer, and public-position restatement messages use canonical deterministic templates.

These canonical messages do not call a dialogue provider.

A non-binding speech act MAY use contextual LLM wording under [DR-26](decisions/2026-09-05_contextual-npc-dialogue.md).
The engine MUST select the action and permitted disclosures before generation.
Novel prose MUST pass deterministic output checks and a separate LLM grounding check.
The grounding check MAY reject presentation only.
It MUST NOT change the action, utility, truth, or session state.
The service MUST NOT parse generated NPC prose back into negotiation state.
The semantic check is probabilistic, not a formal guarantee.
One claimed render attempt MAY contain a generation call and a grounding-check call.
Both calls MUST occur outside SQLite write transactions.

An eligible non-binding NPC utterance uses at most one claimed render attempt.

A provider failure, timeout, empty response, invalid response, or contract violation uses the precomputed actor-safe deterministic template.

A dialogue-rendering failure does not roll back an already committed authoritative action.

The worker resumes the durable render job from its stable intent revision.

The worker does not duplicate the NPC action or public message.

The renderer MAY record safe `validation_failure`, `latency_ms`, and `attempted_generation` metadata.
Validation categories are `format`, `speech_act`, `numeric_reference`, `unauthorized_claim`, `repetition`, `grounding`, `language`, and `credential`.
An unavailable category or duration MUST remain `null`.
The legacy `failure_reason` categories remain unchanged.
No raw rejected output, prompt, credential, or provider error may enter public telemetry.

## Separate dialogue evaluation

The Admin session detail MAY expose `dialogue_quality` with version `1`.
It MUST derive only from the selected session's public messages and public renderer events.
It MUST distinguish technical diagnostics from economic outcome and human judgment.
Repetition flags MUST cite source messages and MUST remain bounded to 100 displayed flags.
The counts MAY include further repeats beyond the displayed flags.
Canonical replies without generation MUST NOT enter latency or fallback-rate denominators.
Missing latency and fallback observations MUST remain unavailable.
The API human dimensions remain unrated in this increment.
An offline scorecard MAY rate relevance, continuity, attribution, and absence of unsupported claims from 0 to 4.
It MUST retain rubric version, source references, reviewer identity, and coverage.
The analyzer MUST reject changed sources, invalid ratings, and unknown source references.
Unrated dimensions MUST remain `null`.
Dialogue diagnostics MUST NOT reveal hidden state or release sealed benchmark reviews.
See the [dialogue evaluation rubric](dialogue-evaluation-rubric.md).

## Terminal states

`clarification_required` and `confirmation_required` are response results.

They are not terminal session states.

The session remains `active` while the corresponding pending state exists.

The terminal session states are:

- `agreement_reached`;
- `walked_away`;
- `expired`;
- `aborted`;
- `technical_failure`.

`walked_away` is a unilateral participant action.

An ambiguous statement about ending negotiations requires clarification.

A negated ending statement such as `мы не уйдём из переговоров` or `we will not walk away` is not a walk-away. The parser ignores the ending cue and reads the rest of the message.

The MVP uses scenario `max_rounds` for expiry.

The MVP does not require a wall-clock deadline.

When `max_rounds` is reached without another terminal transition, the session enters `expired`.

The engine evaluates `max_rounds` immediately after the substantive action that completes the last round, for every controller type. A built-in NPC receives no action after the last round is complete.

An unambiguous `walk_away` terminates the session without a separate confirmation.

Every remaining active offer changes to `closed_by_termination` when the session ends for a reason other than agreement or expiry.

Every remaining active offer changes to `expired` when the session expires.

`POST /sessions/{id}/close` is a privileged administrative operation.

It changes a non-terminal session to `aborted` and records an administrative reason.

A participant cannot use this endpoint as a substitute for `walk_away`.

A recoverable processing failure is not terminal.

The worker resumes from the last committed revision after a recoverable failure.

The session enters `technical_failure` only after the retry budget is exhausted or an operator marks the failure as terminal.

The evaluator can generate a review for every terminal state.

## Session transition summary

| Current state | Valid trigger | Result |
| --- | --- | --- |
| `active` | Unambiguous substantive participant action | Commit action and compute `next_actor`. |
| `active` | Ambiguous participant text | Keep deal state, store pending clarification, and return `clarification_required`. |
| `active` with pending clarification | Clarification resolves to a substantive action | Clear pending clarification and commit the resolved action. |
| `active` | Human or external-agent complete-offer acceptance intent | Store pending acceptance and return `confirmation_required`. |
| `active` with pending acceptance | Unambiguous positive confirmation | Freeze the deal and enter `agreement_reached`. |
| `active` with pending acceptance | Negative confirmation | Clear pending acceptance, keep the same `next_actor`, and remain `active`. |
| `active` with pending acceptance | Ambiguous confirmation | Preserve pending acceptance, keep the same `next_actor`, and return `clarification_required`. |
| `active` with pending acceptance | Modified terms | Clear pending acceptance and commit a counteroffer. |
| `active` | Valid built-in NPC acceptance | Freeze the deal and enter `agreement_reached`. |
| `active` | Unambiguous `walk_away` | Enter `walked_away`. |
| `active` | Complete `max_rounds` limit | Enter `expired`. |
| `active` | Authorized administrative close | Enter `aborted`. |
| `active` | Unrecoverable processing failure | Enter `technical_failure`. |

A terminal session rejects every later participant mutation.

## Branching

An active human training session MAY rewind to an eligible earlier NPC message.

The source revision MUST identify a stored built-in-NPC message and an immutable owner-decision checkpoint.

Rewind MUST create a child session with the exact checkpoint state and fresh credentials.

The source session MUST remain immutable.

The root training lineage MUST permit no more than three rewinds.

The rewind usage count MUST remain outside checkpoint snapshots.

An idempotency replay MUST NOT consume another rewind.

After the third rewind, every new rewind in the lineage MUST fail.

Player-side reply assistance MUST use only the authenticated actor-safe projection and the player's private preparation.

Reply assistance MUST NOT modify session state.

The generated text MUST enter the normal message command before it can affect negotiation state.

The parser and engine remain authoritative for the generated player message.

The implemented DR-36 fork MUST require a terminal human-versus-NPC training session.
The source revision MUST identify an existing immutable human-decision checkpoint.
The child MUST receive fresh participant credentials and remapped participant and event references.
The child MUST NOT inherit later history, parent credentials, render jobs, or idempotency records.
Benchmark sessions and legacy sessions without checkpoints MUST NOT use this fork.
The service MUST preserve profile, preparation, shared background, and social state at the checkpoint.
See [DR-36](decisions/2026-09-24_training-loop.md) and the [implementation guide](human-training-guide.md).

A fork identifies an exact source session revision.

The fork API uses `source_revision`.

The child state includes all effects committed through that revision.

The child state includes the offer statuses at that revision.

The child preserves inherited offer IDs and offer revisions.

The child state includes the observations, hints, distractors, and messages already delivered to each participant through that revision.

The child state includes `next_actor`, pending clarification, and pending acceptance confirmation.

The child inherits the parent scenario version and run configuration by default.

The current fork MUST NOT accept model or policy overrides.

The child starts with `session_revision` equal to `source_revision`.

The lineage marker uses `source_revision` and does not consume a negotiation turn.
The first child-local negotiation event uses `source_revision + 1`.

The lineage marker identifies the parent session and the selected history boundary.
Copied structured event references use new child event identifiers.

A fork is not eligible as an independent benchmark trial.

## Principle-only scope

`agreed_in_principle` is a non-binding conversation state.

It cannot satisfy a required binding term.

A scenario can define a bindable term with `scope_depth: principle_only`.

Such a term must have a concrete authored value schema and validation rule.

It can bind a commercial principle without adding detailed legal drafting.
