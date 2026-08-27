# Offer and Session Protocol

## Status

This document is normative.

Alexander Shmelev accepted this protocol on 2026-08-27.

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

## Public message model

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
- a complete materialized term package;
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

A valid `pass` consumes a turn.

The scenario policy must explicitly permit `pass`.

A built-in NPC MAY ask a question, request clarification, hold its position, reject an offer, or walk away without a counteroffer.

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

This rule includes stored domain-error results.

A mismatched expected revision returns HTTP `409` with code `revision_conflict`.

The response includes the current session revision.

No parser, policy, validator, or NLG retry can append the same authoritative action twice.

## NLG failure handling

The system retries a failed NLG operation at most two times after the first failure.

The system then uses an actor-safe deterministic template.

An NLG failure does not roll back an already committed authoritative action.

The worker resumes from the last committed session revision.

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

The MVP uses scenario `max_rounds` for expiry.

The MVP does not require a wall-clock deadline.

When `max_rounds` is reached without another terminal transition, the session enters `expired`.

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

A fork identifies an exact source session revision.

The fork API uses `source_revision`.

The child state includes all effects committed through that revision.

The child state includes the offer statuses at that revision.

The child preserves inherited offer IDs and offer revisions.

The child state includes the observations, hints, distractors, and messages already delivered to each participant through that revision.

The child state includes `next_actor`, pending clarification, and pending acceptance confirmation.

The child inherits the parent scenario version and run configuration by default.

An authorized orchestrator MAY override model or policy configuration for a training comparison.

The child session records every override.

The child starts with `session_revision` equal to `source_revision`.

The first child-local event uses `source_revision + 1`.

Lineage history identifies the source session for every inherited event.

A fork is not eligible as an independent benchmark trial.

## Principle-only scope

`agreed_in_principle` is a non-binding conversation state.

It cannot satisfy a required binding term.

A scenario can define a bindable term with `scope_depth: principle_only`.

Such a term must have a concrete authored value schema and validation rule.

It can bind a commercial principle without adding detailed legal drafting.
