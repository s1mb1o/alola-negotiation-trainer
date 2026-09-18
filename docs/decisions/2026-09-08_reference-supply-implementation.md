# DR-30. Reference supply implementation

Date: 2026-09-08.
Status: accepted for implementation after the user's `yes` to authored synthetic economics and reserve rules.
Sequence: [DR-29](2026-09-08_reference-before-generalization.md).

## Authority and scope

Implement Stage A from [the delivery plan](../plans/05_reference-supply-and-generalization.md).
The [resolved implementation contract](../reference-supply-contract.md) supplies the exact wire model and synthetic economics.
It resolves the open inputs in [the reference specification](../reference-supply-spec.md).
It takes precedence over that draft's proposed names and unresolved alternatives.
It does not authorize paid model calls or an external AI reviewer.

## Normative implementation rules

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

## Decisions

Use a supply-specific typed package in Stage A.
Use exact integer minor units and basis points.
Use conservative reserve liability and margin valuation without guessed defect probabilities.
Treat the latest delivery-window endpoint as the buyer's guaranteed delivery date.
At the diagnostic deadline, an inconclusive claim receives a free replacement under the synthetic policy.
The supplier retains the original when the replacement is free.
The buyer receives the original back when a verified buyer-side cause makes the reserve payable.
No device can incur both a used-unit and unused-unit charge.

No production scenario version is edited in place.
No live naturalness or model ranking is claimed from offline fixtures.
