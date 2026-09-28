# Reference supply negotiation specification

Date: 2026-09-08.
Status: approved design, resolved and implemented in bounded form under DR-30.
Delivery authority: [DR-29](decisions/2026-09-08_reference-before-generalization.md).
Implementation order: Stage A, then Stage B.

The [resolved contract](reference-supply-contract.md) and [DR-30](decisions/2026-09-08_reference-supply-implementation.md) take precedence over the proposed names and alternatives below.
The [implementation guide](reference-supply-guide.md) records executable scope and validation limits.
Existing scalar scenarios retain their contract.

## 1. Product outcome

The user can negotiate price, advance payment, split delivery, and conditional reserve in natural language.
The NPC can propose a useful exchange before the whole package is complete.
The NPC can explain a constraint and ask one relevant clarifying question.
The user can introduce a new supported deal structure during the conversation.
The final confirmation shows one exact complete package.
Review explains the resulting obligations and negotiation outcomes.

The supplied ChatGPT conversation is a behavioral reference.
It is not a mandatory script or an authoritative economic model.
The service MUST NOT guarantee a price of EUR 109,500 or reproduce each intermediate discount.
Rejection and no agreement remain valid outcomes.

## 2. Bounded scope

Proposed new scenario identities are `supplier_integration_ru` and `supplier_integration_en`, version 1.
Both versions use equivalent authored economics and a fixed simulation calendar.
Existing `supplier_001` versions remain unchanged and available for replay.

The reference scenario supports:

- one base order of 100 identical devices;
- one or two base delivery lots;
- a calendar date or a bounded date window for each lot;
- one advance fraction and one balance-payment rule per lot;
- one authored delivery basis and destination;
- no reserve, or up to three additional reserve devices;
- one authored diagnostic policy with finite outcomes;
- conditional reserve charges tied to the final base-order price.

Arbitrary legal clauses, external logistics lookup, warranty execution, and real payments are excluded.
DDP is an authored simulation label with a named destination.
The engine does not infer a legal contract from that label.

## 3. Authored world and open inputs

Author these inputs before publishing the scenario:

| Input | Required meaning |
| --- | --- |
| Calendar | Negotiation reference date, year, delivery windows, reserve cutoff, settlement deadlines |
| Delivery capability | Earliest dates, permitted windows, early-lot capacity, destination, delivery basis |
| Base order | Quantity, currency, uniform-unit-price rule, monetary precision |
| Payment | Advance trigger, permitted fractions, balance due rule |
| Reserve | Quantity limit, delivery association, unit-price rule, diagnostic outcomes, obligations |
| Economics | Financing value, production and delivery costs, split-lot cost, integration value, reserve cost |
| Acceptance | Hard constraints, BATNA, reservation utility, ZOPA intent |
| Narrative | Names, roles, prior relationship, motives, authority, permitted disclosures |

Synthetic values require explicit authorization.
Do not infer actual company costs from the reference dialogue.
Do not tune costs only to force its final price.
The new scenarios may change economic truth; their results are not directly comparable with supplier version 5.

Proposed calendar basis is 1 October 2026.
The reference mentions 5–7 November, 10 November, 20 November, and 1 December.
An omitted year can use the authored calendar only through an explicit scenario interpretation rule.
“Early November” remains ambiguous unless that rule defines its interval or a participant clarifies it.
Do not collapse a date window into an invented exact date.

Proposed opening: EUR 120,000 for 100 base devices and the authored standard delivery window.
The standard window must be calculated from the approved calendar and published in the opening artifact.
Advance payment remains omitted.
An opening MUST NOT invent zero advance, payment after delivery, or an approval authority.

## 4. Preliminary proposals and final offers

The new scenario protocol distinguishes a `PreliminaryProposal` from a formal `Offer`.
The distinction is independent of package completeness.
A complete preliminary proposal MUST NOT become binding or trigger NPC acceptance.
This prevents negotiation from ending before reserve or diagnostic terms are discussed.

For this opt-in protocol, initialization creates preliminary revision 1 at session revision 0 from exactly the authored opening artifact.
It does not create an accept-enabled formal opening offer.
In human-versus-built-in-NPC training, the NPC gives a neutral case-specific greeting instead of presenting the authored opening terms.
When an external agent is `next_actor`, the Easy opening presentation remains canonical and does not call an LLM.
Historical scalar initialization still creates its existing opening offer revision.

A preliminary proposal contains:

- session-scoped stable identity, revision, and proposer;
- source message and event references;
- materialized proposed terms;
- an exact base preliminary or formal revision when terms are carried forward;
- unresolved required paths;
- explicit links between reciprocal conditions;
- lifecycle status and validation results.

The lifecycle is `active`, `superseded`, `withdrawn`, or `promoted`.
Only an exact active source can be amended or promoted.
The first implementation supports one active preliminary package, not simultaneous MESO alternatives.

A negotiation condition differs from a contract contingency.
“This price if we later agree a delivery date” is unresolved negotiation.
“The reserve is paid when diagnosis finds a buyer-side cause” is a defined contingent obligation.
A final package may contain the latter with all outcome rules specified.
It cannot contain the former unresolved.

An explicit request to discuss one term MUST NOT request finalization.
“50% is acceptable” MUST NOT confirm unrelated lots or the full deal.
“Show the final package” requests presentation, not binding consent.

The NPC MAY promote its own complete, legal, economically acceptable preliminary proposal to a formal offer when finalization is explicitly requested.
Promotion presents the formal offer. The same request MUST NOT also count as acceptance intent.
The actor's subsequent acceptance intent returns `result: confirmation_required` and existing `pending_confirmation`.
A further confirmation message can bind that exact active offer revision.

A human or external agent that asks to publish its own final offer first receives an exact publication confirmation.
The UI MUST explain that confirmation authorizes publication and that NPC acceptance can then end the negotiation.
No user-authored complete preliminary package may be auto-accepted before that explicit step.
The proposed additive `pending_offer_publication` state is separate from existing `pending_confirmation` for acceptance of another participant's offer.
Confirming publication validates the exact preliminary source revision and complete snapshot again before creating a formal offer.

This is an opt-in scenario protocol version.
Historical scalar scenarios retain their existing formal-offer flow.

## 5. Supply package contract

Proposed contract identifier: `supply-package-v1`.
Use a supply-specific typed package first, not a generic executable DSL.

| Component | Proposed fields and rules |
| --- | --- |
| `base_price` | Currency and exact minor units for the 100 base devices only |
| `delivery_lots` | One or two stable lot IDs; positive quantity; delivery window |
| `payment_schedule` | One entry per lot ID; advance basis points; balance trigger and due rule |
| `delivery_basis` | Authored basis ID and destination ID |
| `reserve_policy` | Explicit mode `none` or `contingent`; separate reserve quantity, delivery lot reference, and branch obligations |
| `diagnosis_policy_id` | Versioned authored verification and settlement policy for a contingent reserve |

Missing fields remain absent and appear in `unresolved_required_terms` as nested paths.
The engine MUST NOT interpret a missing reserve policy as “no reserve”.
Before finalization, the participants must explicitly select no reserve or resolve a reserve policy.

All base-lot quantities MUST sum to exactly 100 in a complete package.
Reserve devices MUST NOT count toward that sum.
Payment entries MUST reference existing lot IDs exactly once.
Advance plus balance MUST equal the applicable lot price.
An explicit zero advance remains a real value.

A contingent reserve requires `delivery_lot_id` referencing one base lot.
The reserve arrives within that lot's delivery window as additional inventory.
Its delivery deadline must precede its permitted use cutoff.
A reserve with no resolvable delivery reference is incomplete.
Stage A does not support an independent third reserve shipment.

Money uses exact arithmetic and a pinned rounding rule.
The proposed uniform-unit-price rule allocates base price by lot quantity.
Rounding remainders must be assigned deterministically without changing the base total.
Reserve unit prices reference the exact final base-price revision and quantity.
The scenario must define how non-divisible minor-unit prices affect reserve pricing.

Illustrative arithmetic, not an accepted target outcome:

- Base price EUR 109,500 means EUR 1,095 per device under uniform pricing.
- Ten devices paid fully in advance contribute EUR 10,950.
- Ninety devices with 50% advance contribute EUR 49,275.
- Total base-order advance is EUR 60,225, or 55%.
- Three payable reserve devices add EUR 3,285.
- Maximum combined price under that branch is EUR 112,785 before any separately authored charges.

The engine MUST derive these amounts. The LLM MUST NOT supply the calculation result as authority.

## 6. Atomic edits and source binding

The extractor proposes typed operations, not arbitrary JSON Patch or schema extensions.
The bounded operation set covers setting price, replacing the lot schedule, editing one identified lot, assigning one lot's payment, setting reserve terms, and removing an optional supported structure.
The engine allocates stable identifiers and resolves actor-safe references.

Each operation references the exact source proposal or offer revision.
The engine materializes a full new preliminary revision atomically; required paths may remain unresolved.
It MUST NOT apply a generic recursive merge or a shallow replacement that loses unrelated terms.
Replacing a lot schedule must remap payment references explicitly or leave them unresolved after a clear change report.
The same rule applies to the reserve delivery lot reference.
No dangling reference may enter a complete final package.

“100% advance for the first ten, if they arrive early” is one conditional unit.
The engine MUST NOT commit the payment change while dropping its delivery condition.
“The rest” requires one unambiguous remaining lot.
Ambiguous scopes, conflicting values, or multiple candidate packages require clarification without partial term mutation.

A base-price change deterministically recomputes dependent payment and reserve amounts.
A relevant amendment invalidates pending publication or acceptance confirmation.
Repeating the same idempotency key MUST NOT create a second proposal revision or NPC reply.

When an explicit preliminary amendment references an active formal offer, the transition marks that formal revision `superseded` and clears it from the accept-enabled active offer set.
The same atomic event group creates the new preliminary revision and cancels any confirmation based on the old package.
This rule follows the single-active-package negotiation model. It does not let a participant withdraw an unrelated offer by naming an arbitrary ID.
A question, quotation, or uncommitted hypothetical does not supersede a formal offer.
An old formal revision cannot be accepted again after negotiation has been reopened by an explicit amendment.

## 7. Reserve and diagnosis

The requested reference interpretation is pending confirmation:

- confirmed hardware defect or a required supplier repair makes the used replacement free;
- a buyer software, configuration, or infrastructure cause makes the used reserve payable;
- unused reserve devices are purchased after 1 December.

Author mutually exclusive verification outcomes.
Do not let free-text diagnosis create a new predicate or a charge.
Specify precedence when supplier repair and a buyer-side change both occurred.

| Reserve outcome | Proposed charge treatment | Required ownership rule |
| --- | --- | --- |
| Unused at the cutoff | Purchase at the defined unit price | Reserve device becomes buyer-owned after settlement |
| Used; verified hardware failure or supplier repair | No extra replacement charge | Proposal: buyer keeps replacement; supplier retains the original |
| Used; verified buyer-side cause | Purchase at the defined unit price | Proposal: buyer keeps purchased reserve; original returns to buyer |
| Used; inconclusive or late diagnosis | No automatic payable/free classification | Explicit temporary possession, deadline, and final-resolution rule required |

The ownership proposals are not yet approved.
Keeping both an uncharged replacement and a repaired original requires separate economic rules.

Each reserve device MUST have exactly one settlement state.
A used device MUST NOT also incur the unused-device charge at the cutoff.
No reserve device may be charged twice.
The policy must define the claim-use cutoff, charge due date, diagnostic deadline, and inconclusive-case resolution.
It must define whether a post-cutoff verified claim can reverse an earlier charge.

A future diagnosis may be unknown when the contract is signed.
The rules for that outcome must still be complete.
A participant's assertion of a defect is a claim, not verification.
Stage A evaluates authored branches; it does not operate a real warranty workflow or call logistics services.

## 8. Deterministic economics

Implement a supply-specific evaluator with a versioned function identifier.
Its inputs include the whole materialized package and authored role parameters.
Its outputs include constraint results, utility, component breakdown, and branch liability.

Model these effects explicitly:

- base-order price;
- financing value of each lot's advance;
- delivery and split-lot costs;
- integration value of an early first lot;
- reserve stock, fulfillment, and diagnostic costs;
- payment obligations under every supported outcome.

Proposed date-window valuation uses the guaranteed latest arrival date for buyer integration utility.
The earliest endpoint does not count as a guaranteed early arrival.
Capability validation must establish that the promised window can be fulfilled under authored availability.
Seller cost uses an authored conservative window rule, not an assumed best-case date.
Widening a window toward a later date must not gain the value of its earliest endpoint without a guarantee.

Expected utility requires approved authored probabilities.
A conservative branch aggregation is an alternative and must be identified as such.
Do not infer probabilities from conversation or let an LLM estimate utility.
Select the aggregation and coefficients before implementation readiness.

Reserve evaluation must cover joint outcomes across all reserve devices.
For example, one free replacement, one payable unit, and one unresolved diagnosis form one joint state.
Do not assume independent per-device probabilities.
Expected utility requires approved joint outcome probabilities or an explicitly approved independence model.
A conservative evaluator can enumerate the bounded joint state space and apply the approved worst-case rule.
Maximum liability includes each device at most once and excludes charges not authorized by that state's obligations.

Hard budget checks use the scenario's defined liability scope.
The recommended scope includes maximum contractual reserve liability, not only headline base price.
NPC acceptance requires all hard constraints and its own `reservation_utility`.
A human or external agent may accept below its own reservation utility only when every hard constraint passes.
Review must identify that economic failure.

An incomplete preliminary package has no authoritative complete-package utility.
The engine MAY search bounded authored completions to decide whether a conditional discussion is feasible.
Those internal completions MUST NOT populate omitted public terms or appear as promises.
If the engine cannot justify a preliminary concession over the stated conditions, it must request a missing term instead.
Policy ranking uses NPC utility and public proposals, not counterpart private utility.

## 9. Semantic extraction and conversation policy

Keep deterministic parsing for supported exact numeric forms.
Use an optional LLM extractor for compound intent and reference interpretation.
Its actor-safe input includes the current message, relevant public history, active public revisions, public term vocabulary, and permitted operation types.
It receives no private utility, hidden capability values, credentials, or raw scenario source.

Extractor output contains typed proposed actions, conditions, questions, attributed interests, and exact source spans.
It MUST NOT set authoritative confidence, reality, utility, final offer identity, or agreement status.
Validate schema, numbers, references, span membership, condition scope, and scenario support before applying an action.
Provider refusal, malformed output, unsupported semantics, or materially different interpretations produce clarification without an invented edit.
Configuration and provenance remain distinct for extraction and rendering.

Structured output helps validate shape. It does not establish semantic truth.
The OpenAI Docs [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs) documents mistakes and refusal handling.
Use provider-native schema constraints when supported and retain server-side semantic validation for every provider.

The engine selects among bounded actions:

- answer the current question;
- explain one permitted motive;
- ask one material clarification;
- propose a feasible conditional preliminary exchange;
- acknowledge or revise the supported structure;
- summarize unresolved issues;
- present a final formal offer;
- reject an unsupported or unacceptable proposal.

Do not require a complete package after every conversational message.
Do not decrease price on every turn merely to imitate the reference.
Do not repeat a question already answered in the same public proposal context.
Difficulty changes assistance and conversational initiative, not economic truth.
The full generalized belief engine is not a Stage A dependency.
Attributed interests remain claims with sources until the approved knowledge model is implemented.

## 10. Safe natural rendering

Proposed render contract: bounded natural paragraphs plus an immutable engine-authored terms block.
Allow plain paragraphs and simple lists. Escape content in clients. Do not allow arbitrary HTML.
Preserve exact numbers, dates, quantities, counterpart attribution, conditional links, and revision references in engine-controlled fragments.
The LLM MUST NOT change the canonical block or add a new monetary promise outside it.
Novel prose still requires grounding validation.
An unavailable renderer uses a context-appropriate deterministic fallback with explicit telemetry.

Financial confirmation text remains canonical.
Any surrounding explanation must not change its meaning or the confirmed snapshot.
Names, prior relationship, approval authority, and delivery capability must have permitted scenario sources.
Do not add a signature or greeting to every chat turn by default.
Email-like structure may be an authored conversation style.

The current first-disclosure verbatim rule remains active until an approved replacement is synchronized in core specifications.
Stage A may initially keep that rule while allowing safe paragraph structure around selected reasons.
Do not silently replace a validated source fact with an unverified paraphrase.

## 11. Public API and persistence

Keep `POST /api/v1/sessions/{id}/messages` with `message`, `idempotency_key`, and `expected_revision`.
The authenticated token determines the participant.
Perform authentication, revision, and turn checks before creating extractor context.
Humans, CLI clients, Telegram adapters, and external agents use the same natural-language route.
Do not add a public structured action submission route for agents.

Proposed additive response fields:

- `negotiation_contract_version` identifies the opt-in behavior;
- `preliminary_proposals` exposes actor-safe active and referenced preliminary revisions;
- `unresolved_required_terms` remains a list of strings and may include nested paths;
- `unresolved_term_details` adds localized `{path, label}` records without changing the existing list's type;
- `confirmation_kind` distinguishes `accept_offer` from `publish_offer`;
- `pending_offer_publication` includes the exact source preliminary revision, materialized terms, and snapshot digest;
- existing `pending_confirmation` retains the exact formal `offer_id`, `offer_revision`, and full terms for acceptance.

Publication and acceptance confirmation are submitted as natural-language messages.
UI buttons may submit canonical localized messages through that route.
Their semantic meaning is restricted by the matching pending state and exact revision.
Only one pending finalization operation may exist in a session at a time.
It is bound to its authenticated author internally and projected only to that participant.
The participant's session GET response must restore the same pending snapshot after a browser refresh.
The other participant must not receive an actionable publication or acceptance confirmation.
The pending author remains `next_actor` until confirmation, cancellation, or a permitted amendment resolves the operation.
Publication confirmation revalidates both the source revision and materialized snapshot digest.
Cancellation clears only the intended pending operation.
Any relevant amendment invalidates it.
The UI must not conceal composite terms behind a scalar summary at confirmation.

Reuse JSON persistence where suitable, but add typed validators and versioned event payloads.
Proposed events include preliminary creation, amendment, withdrawal, promotion, publication confirmation, and composite validation.
Persist validated operations, materialized snapshots, source revisions, evaluator version, and exact delivered text.
Private evaluation details remain in internal payloads.
Public events contain only actor-safe terms and explanations.

Replay reads recorded validated transitions and stored wording without extraction or generation.
This increment extends replay of existing sessions. It does not implement session forks.
Old scalar records must not gain synthetic lots, dates, payments, or reserve policies on read.
The compiler and formatter versions remain pinned for each session and delivery.
Document safe SQLite migration and restart behavior before deployment.

## 12. UI and participant review

Show a preliminary package card with base price, lots, payments, reserve branches, and open issues.
Use human terms in Russian and English instead of JSON field names.
Show “proposed” and “requires clarification” separately from final confirmation and agreement.
Do not label partial alignment as a binding term agreement.

For each lot, show quantity, delivery window, advance amount, and balance rule.
For reserve, show additional quantity, when it is free, when it is payable, and the unresolved-diagnosis rule.
Show base price separately from possible additional liability.
The final confirmation shows all applicable conditions in one readable package.

Inspector and history show source-linked proposal changes and renderer failures.
Review explains verified price change, advance exposure, delivery tradeoffs, reserve liability, and economic acceptability.
Do not equate a lower headline price with a better overall deal.
Keep human dialogue ratings separate from deterministic economics.
Support dark/light themes, existing readable typography, and narrow screens.

## 13. Acceptance cases

| Case | Required result |
| --- | --- |
| Opening | Authored price and delivery only; no invented advance or payment method |
| Budget question | Direct answer or justified preliminary exchange; no false agreement |
| Advance exploration | Explain its value or ask its size without demanding every other term |
| Conditional advance and date | Preserve their dependency; clarify an ambiguous destination or calendar reference |
| First ten and remaining ninety | Two linked lots; quantities sum to 100; payment scoped per lot |
| Price revision | Update dependent amounts from the exact revision without losing delivery conditions |
| Three reserves | Keep reserve outside base quantity and headline base price |
| Diagnostic proposal | Identify ambiguity and propose only authored outcome rules |
| Complete preliminary package | No automatic NPC acceptance or terminal session |
| Final publication | Exact snapshot confirmation before publishing a user's final offer |
| Final acceptance | Explicit intent, then separate confirmation of one complete active formal revision |
| Refusal/no agreement | Valid outcome when economics or capabilities do not permit the request |

Run each trajectory in RU and EN with different wording.
Do not assert exact model-generated replies or a fixed number of discounts.
Add focused failures for 10+95 quantities, duplicate lot IDs, dangling payments, condition loss, non-divisible prices, expired references, and reserve double charging.
Test late and inconclusive diagnosis rules without executing actual warranty operations.
Test withdrawal, changed base prices, superseded confirmations, and idempotent retry.
Test same-service concurrent sessions, restart, actor-safe projections, secret redaction, and replay without LLM calls.
Run existing scalar-scenario and client regressions.

Live dialogue validation requires separate transmission consent and spending limits.
The reference cannot be declared natural solely because offline fixtures pass.
Record actual provider/model provenance, failures, latency, and source-linked human review.

## 14. Readiness checklist

- [ ] User authorizes a synthetic economic model or supplies economic inputs.
- [ ] Reserve payment interpretation is approved.
- [ ] Repaired-original ownership and inconclusive-diagnosis policy are approved.
- [ ] Calendar, delivery capacity, destination, and payment triggers are authored.
- [ ] Utility coefficients, delivery-window valuation, joint reserve outcome aggregation, and hard-liability scope are authored and checked.
- [ ] Proposed preliminary/publication/acceptance flow is approved and synchronized in core specifications.
- [ ] Proposed renderer contract is approved and synchronized in core specifications.
- [ ] Concrete wire schemas, error categories, and migration tests are complete.

Until these checks are complete, the specification remains a draft and runtime implementation does not begin.
