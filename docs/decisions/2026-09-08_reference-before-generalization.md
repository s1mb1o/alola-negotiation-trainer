# DR-29. Reference scenario before generalization

Date: 2026-09-08.
Status: accepted sequencing decision through the user's request `2, затем 3`.

## Context

The user supplied a preferred supply-negotiation dialogue.
It develops from price and prepayment to separate delivery lots and a conditional reserve.
The current supplier scenario excludes those composite structures.
The user selected a complete reference scenario before a general deal language.

## Options considered

1. Improve wording within existing scalar terms. This does not support the full reference.
2. Implement and validate one bounded reference scenario. Then generalize its validated components.
3. Implement a general deal language before validating the reference interaction.

Option 2 followed by option 3 is selected.

## Accepted delivery order

The next increment MUST implement and validate one bounded supply-negotiation scenario before generalizing its deal model.
The reference increment MUST retain structured-state authority, actor-safe projections, exact confirmation, immutable scenario versions, and replay without LLM calls.
Generalization MUST preserve the reference scenario's validated behavior and support a second domain through authored configuration.
Implementation MUST NOT begin until the reference specification, economic assumptions, and unresolved contract rules are approved.
This sequencing decision does not authorize paid model calls or external AI review.

## Specification status

The [reference specification](../reference-supply-spec.md) is a draft for approval.
Its proposed fields, economics, and protocol extensions are not yet accepted runtime rules.
This decision does not supersede DR-28's financial rendering or offer-transition requirements.
Approval of changes to those requirements must update the affected core specifications in the same change.

The [reference supply specification](../reference-supply-spec.md) defines the two stages and their gates.
Neither stage is implemented by this documentation change.

## Consequences

Keep FastAPI, React, SQLite, the modular monolith, and the Player API.
Do not build arbitrary schema generation or an executable language for LLM-produced code.
Use a supply-specific package first.
Extract reusable primitives only after the package works through conversation, confirmation, review, and replay.
Keep the reference dialogue as behavioral evidence, not a script of mandatory discounts or replies.
