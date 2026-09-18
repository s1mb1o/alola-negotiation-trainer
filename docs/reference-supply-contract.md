# Resolved reference supply contract

Date: 2026-09-08.
Status: implementation-ready under [DR-30](decisions/2026-09-08_reference-supply-implementation.md).
All economic values are authored synthetic training inputs.
They are not claims about real companies, logistics prices, or warranty law.

## Scenario and calendar

Publish `supplier_integration_ru` and `supplier_integration_en`, version 1.
Set `negotiation_contract: supply-package-v1`.
Keep old scenarios unchanged.
The authored negotiation date is 2026-10-01.
The named destination is `vector_site`; it is an authored fictional customer site.
The only delivery basis is `DDP` to that destination as a bounded simulation condition.
The order contains 100 identical main devices and at most three additional reserves.
One or two main lots are supported.
Dates are ISO calendar dates. A window retains both endpoints.
The earliest first lot is 2026-11-05 and contains at most ten main devices before 2026-11-10.
The earliest full main order is 2026-11-10.
The latest supported date is 2026-11-26.
“Early November” is an authored public vocabulary rule for 2026-11-05 through 2026-11-07.
User-visible briefs state the scenario year and interpretation rule.
The opening preliminary proposal contains EUR 120,000 and one lot of 100 devices due 2026-11-26.
It omits payment, delivery basis, and reserve terms.

## Materialized terms

```json
{
  "base_price": {"currency": "EUR", "minor_units": 10950000},
  "delivery_lots": [
    {"lot_id": "early", "quantity": 10, "window_start": "2026-11-05", "window_end": "2026-11-07"},
    {"lot_id": "remaining", "quantity": 90, "window_start": "2026-11-20", "window_end": "2026-11-20"}
  ],
  "payment_schedule": [
    {"lot_id": "early", "advance_bps": 10000, "balance_days": 0},
    {"lot_id": "remaining", "advance_bps": 5000, "balance_days": 0}
  ],
  "delivery_basis": {"basis": "DDP", "destination_id": "vector_site"},
  "reserve_policy": {
    "mode": "contingent",
    "quantity": 3,
    "delivery_lot_id": "remaining",
    "use_cutoff": "2026-12-01",
    "unused_payable_on": "2026-12-02",
    "unit_price_rule": "base_unit_ceil",
    "diagnosis_policy_id": "hardware-replacement-v1"
  }
}
```

This is an illustrative complete package, not a required negotiation result.
`reserve_policy: {"mode":"none"}` explicitly declines reserve.
Missing fields remain unresolved. They never imply zero or no reserve.
Nested payment entries may omit `advance_bps` or `balance_days` during preliminary discussion.
The permitted balance days are 0 and 30 after the associated lot's delivery.
An authored NPC action may propose a missing balance rule explicitly. It cannot insert it silently.
The lot IDs are session-scoped semantic identifiers allocated by the engine.
The initial lot ID is `main`; a split uses `early` and `remaining`.
An ambiguous change or condition must not partially mutate the package.

Base price is 10,000,000 through 12,500,000 minor units.
Use nonnegative exact integer money and fractions from 0 through 10,000 basis points.
Allocate each lot's base price by quantity with floor rounding; assign the final residual to the last canonical lot.
Round each advance to the nearest minor unit with half-up rounding.
The balance is its allocated lot price minus its advance.
Reserve unit price is `ceil(base_price.minor_units / 100)`.
The sum of lot prices and the sum of advance plus balance must equal the exact base price.

## Reserve outcomes

The reserve arrives with its referenced main lot, outside the 100 main devices.
Claims must be reported by the end of 2026-12-01 in the authored simulation timezone.
The authored simulation timezone is `Europe/Moscow`.
An unused unit is payable on 2026-12-02.
A timely used unit is excluded from the unused-unit bill.
Diagnostic deadline is ten calendar days after the supplier receives the original device.
These are authored outcome rules, not a live warranty workflow.

| Verified outcome | Extra reserve charge | Original device | Replacement |
| --- | --- | --- | --- |
| Hardware defect or supplier repair | Zero | Supplier retains it | Buyer retains it |
| Buyer software/configuration/infrastructure cause, no hardware fault | Unit price | Returned to buyer | Buyer purchases it |
| Inconclusive before deadline | No charge due yet | Supplier holds it | Buyer holds it provisionally |
| Inconclusive at deadline | Zero | Supplier retains it | Buyer retains it |
| Unused at cutoff | Unit price | Not applicable | Buyer purchases it |

Confirmed hardware fault takes precedence when both hardware and buyer-side factors are verified.
A party's claim does not verify any outcome.
A late claim does not reverse an unused-unit purchase in this bounded scenario.
For a timely claim, diagnosis and its deadline rule determine settlement even after the cutoff.
Settlement can record `diagnosed_on` to prove that a verdict occurred before the deadline.
Without that timestamp, settlement uses the observation date.
A later verdict cannot reopen a deadline-based free replacement.
Every unit has exactly one settlement outcome and at most one extra charge.

## Synthetic economics

The evaluator version is `supply-economics-v1`.
Configuration stores all coefficients, bounds, dates, and outcome rules in the scenario.
Money below is in EUR; implementation uses exact minor units for liabilities.

| Parameter | Value |
| --- | --- |
| Buyer maximum total contractual liability | 115,000 |
| Seller hard minimum base price | 103,000 |
| Seller base production and standard delivery cost | 102,000 |
| Additional cost for two main lots | 300 |
| Seller acceleration cost per main device before 26 November | 10 |
| Seller financing credit at 100% weighted advance | 4,500 |
| Seller conservative reserve cost per reserve device | 200 |
| Buyer comparison value for main order | 120,000 |
| Buyer integration value if at least ten devices arrive by 7 November | 5,000 |
| Buyer value if all main devices arrive by 20 November | 2,500 |
| Buyer financing cost at 100% weighted advance | 2,000 |
| Buyer immediate reserve value per device arriving by 20 November | 350 |
| Utility scaling denominator for both roles | 200 |
| Utility range | 0 through 100 |
| Reservation utility | 40 for each role |
| BATNA utility | Buyer 36; seller 34 |

Use the guaranteed `window_end` for buyer benefits.
Seller acceleration cost applies when a lot's promised window begins before 26 November.
Weighted advance is the sum of allocated advances divided by base price.
For balances at 30 days, subtract seller financing credit of EUR 500 times the unpaid fraction and add buyer financing benefit of EUR 250 times that fraction.

Seller utility is its conservative margin divided by 200, clamped to the utility range.
Margin equals base price minus base cost, split cost, acceleration cost, and reserve cost, plus financing credit, less delayed-balance financing cost.
Do not count uncertain extra reserve revenue toward NPC acceptance.
Buyer utility is comparison value minus maximum liability, plus integration, completion, and reserve benefits, less financing cost, plus delayed-balance benefit; divide by 200 and clamp.
Maximum liability equals base price plus reserve quantity times derived reserve unit price.
This is conservative branch aggregation, not a claimed expected value.
Reserve outcomes can differ per unit. Enumerate or derive the bounded joint maximum without double charging.
No probabilities are assumed.
The evaluator returns no complete-package utility for an incomplete package.
Report utility and liability separately from conversational quality.

NPC candidate prices are authored and bounded.
Initial candidates are EUR 115,000, 113,000, 111,000, 109,500, 108,000, 105,000, and 103,000.
Candidates must satisfy the stated conditions, authored feasibility, all hard constraints, and NPC reservation utility before formal publication.
Incomplete discussion may inspect internal supported completions but cannot publish their unstated terms.
NPC selection must not read counterpart utility or promise automatic discounts per turn.

## Wire and transition contract

Use the existing authenticated `POST /api/v1/sessions/{id}/messages` route.
Request fields remain `message`, `expected_revision`, and `idempotency_key`.
GET session restores the same actor-safe pending state.

Add `negotiation_contract_version: supply-package-v1` to observations and session envelopes.
`preliminary_proposals` contains at most one active proposal with `proposal_id`, `proposal_revision`, `proposer_participant_id`, `proposer_role`, `terms`, `status`, `source_event_ids`, and `unresolved_required_terms`.
Nested unresolved paths remain strings. `unresolved_term_details` adds `{path,label}` entries.
Formal `active_offers` keeps its current shape and contains no preliminary proposal.
`current_public_terms` is the current preliminary package, active formal offer, or final agreement as appropriate.

Publication intent returns `result: confirmation_required`, `confirmation_kind: publish_offer`, and `pending_offer_publication`.
The publication object contains `proposal_id`, `proposal_revision`, `terms`, `snapshot_digest`, and empty `unresolved_required_terms`.
Its internal `participant_id` identifies its owner and is not a cross-actor capability.
Only the owner receives actionable pending publication state.
The canonical owner confirmation is “Подтверждаю окончательное предложение” or “I confirm the final offer”.
Cancellation is “Отменяю подтверждение” or “I cancel confirmation”.
Both are natural-language messages whose meaning requires matching pending state.

Confirmation revalidates the active preliminary ID/revision, digest, completeness, and constraints before formal publication.
NPC acceptance may follow a confirmed participant publication.
NPC final-offer presentation cannot count as the player's acceptance intent.
Player acceptance of a presented NPC formal offer uses existing `pending_confirmation` with `confirmation_kind: accept_offer`, then a separate positive confirmation.
Only one pending finalization operation exists per session.
A relevant change clears it and supersedes any referenced formal offer atomically.
An unchanged question does not reopen or supersede the formal offer.

Use existing `revision_conflict`, `not_your_turn`, `session_terminal`, `offer_not_active`, and `offer_not_bindable` where applicable.
New clarification categories are `ambiguous_composite_scope`, `invalid_composite_terms`, `unresolved_composite_terms`, `unsupported_composite_semantics`, and `extraction_unavailable`.
Stale publication returns `409 proposal_not_active` without publication.
Incomplete publication requests produce clarification without an accept-enabled offer.
Unsupported content cannot receive invented utility or silently commit a supported subset of a conditional clause.

## Persistence and compatibility

Store preliminary revisions in versioned public events and the session state snapshot.
Formal offers use existing offer rows with JSON terms.
No database column replacement or old-row rewrite is required.
Each event retains session ID, source revision, actor, materialized terms, and safe validation category.
Private economics remain internal.
Record exact rendered messages and engine-owned package blocks for replay.
The opt-in contract selects new behavior; missing contract retains the scalar implementation.
The new rendering format must be versioned independently from historical render plans.
Use isolated temporary SQLite databases for tests. Do not migrate or restart a running user service during development.

## Readiness

The user authorized authorship of synthetic economics and reserve rules.
The calendar, liability scope, ownership, deadline, unresolved diagnosis, and exact wire model are resolved above.
Stage A implementation is ready after this contract and DR-30 are synchronized with the affected core specifications.
Stage B remains ordered after reference validation. Live naturalness remains pending separate paid-test approval.
See the [implementation guide](reference-supply-guide.md) for runtime behavior and the optional semantic-normalization flag.
