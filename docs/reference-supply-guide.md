# Reference supply implementation

Date: 2026-09-08.
Authority: [DR-30](decisions/2026-09-08_reference-supply-implementation.md).
Contract: [resolved supply contract](reference-supply-contract.md).

## Implemented scope

Select **Поставка компьютеров: интеграция и резерв** in the Russian UI.
Select **Computer supply: integration and reserve** in the English UI.
The immutable scenario IDs are `supplier_integration_ru@1` and `supplier_integration_en@1`.
The scenario uses a fictional calendar and synthetic economics.
Existing scenario versions remain unchanged.

If this scenario is missing, restart the API with its existing configuration.
The API loads scenarios at startup.
Refresh the UI and select **Новая сессия**.
Choose the integration-and-reserve scenario named above.
An existing session remains attached to its original scenario after a restart.

**Поставка 100 промышленных компьютеров** (`supplier_001`) is the older scalar scenario.
It supports one whole-order delivery duration in weeks, not DDP or calendar dates.
Its parser rejects the message `Мы готовы внести предоплату 50%, при условии что получим DDP 10 ноября`.
Use a new integration-and-reserve session for that conversation.
Do not remove the legacy validation guard or convert a calendar day into a duration in weeks.

Negotiate the price of the main order.
Split its devices into an early lot and a remaining lot.
Specify an advance and a balance rule for each lot.
Add the bounded reserve policy or explicitly decline reserve.
The engine checks quantities, references, date windows, monetary rounding, and contractual liability.
An incomplete package has no complete-package utility.
An omitted payment is not zero payment.
An omitted reserve policy is not a refusal of reserve.

All calculations use integer minor units and basis points.
The complete reference package has a base price of EUR 109,500.
Its maximum reserve-inclusive liability is EUR 112,785.
Its advance is EUR 60,225, or 55% of the main price.
These are one offline trajectory's results, not a guaranteed discount.

## Discussion and finalization

The opening is a preliminary proposal, not an accept-enabled offer.
A complete preliminary proposal also remains non-binding.
The public observation contains `preliminary_proposals` separately from `active_offers`.
Every revision retains source events.
The Web UI and Session Inspector display lots, payments, reserve rules, and unresolved terms without raw JSON.

To publish your own complete preliminary package, request its publication in a message.
The service returns `pending_offer_publication` and `confirmation_kind: publish_offer`.
Review the exact snapshot.
Confirm with `Подтверждаю окончательное предложение` or `I confirm the final offer`.
The Web UI sends this confirmation when you select its publication button.
The NPC can accept the published offer if the package passes constraints and its own reservation utility.

To accept an NPC formal offer, first state acceptance intent.
The service returns `pending_confirmation` and `confirmation_kind: accept_offer`.
Confirm that exact offer in a separate message.
A request to see the NPC final offer is not acceptance.
An amendment supersedes the formal offer and clears pending finalization.
A question retains the pending snapshot.
Only the pending operation's owner receives actionable confirmation data.

## Language paths

The default supply parser is deterministic and bounded.
It supports the reference trajectory and tested variants, not arbitrary contract language.
Unknown conditions and unsupported quantities produce clarification without partial mutation.
The engine selects the NPC action before rendering.

With an existing OpenAI or Qwen NPC configuration, preliminary proposals and conversational turns can use LLM prose.
The service appends an immutable engine-authored package block.
The LLM cannot rewrite that block.
Novel prose requires a second grounding check.
Publication and acceptance remain deterministic.
Provider failure or invalid wording returns the stored safe fallback.

Optional semantic normalization is disabled by default.
Set this variable with the existing NPC provider configuration before starting a new service process:

```sh
export NEGOTIATION_SUPPLY_SEMANTIC_EXTRACTION=true
```

This feature uses the same configured provider.
It handles eligible text that the bounded parser classified as information.
It does not reinterpret an explicit question, negation, past proposal, confirmation, or unsupported conditional clause as an amendment.
It preserves numeric tokens and source revision.
It requires a semantic-equivalence check, then deterministic parsing and domain validation.
The model receives only current public terms and the current message.
The service rechecks authentication, revision, turn, and idempotency before commit.
Provider calls run outside SQLite write transactions.
Failure returns `extraction_unavailable` without exposing raw provider errors.

An eligible turn can use up to two normalization calls and two rendering calls.
Each call uses the configured timeout and output limit.
Schema validation and equivalence checks reduce errors. They do not prove perfect semantic interpretation.
The exact final confirmation remains necessary.

See [COMMANDS.md](../COMMANDS.md) for the API and UI commands.
Use API port 8172 and UI port 8171 on this machine.
No user service was restarted as part of this implementation.

## Reserve settlement

A reserve unit is additional to the main order.
Unused units become payable after the authored cutoff.
A timely used unit cannot also receive an unused-unit charge.
Confirmed hardware failure or supplier repair gives a free replacement.
A verified buyer-side cause makes the reserve payable.
Inconclusive diagnosis creates no payment before the deadline.
At the deadline, the authored policy gives a free replacement.
The supplier retains the original for a free replacement.
The buyer receives the original back after a payable replacement.

The deterministic settlement function can receive `diagnosed_on`.
This timestamp establishes whether a verified verdict occurred before the deadline.
A later diagnosis cannot reopen a deadline-based free replacement.
When this timestamp is absent, settlement uses the observation date.
This is a simulator outcome rule, not an operational warranty service.

## Verification and remaining gate

Run the focused suite:

```sh
.venv/bin/python -m pytest backend/tests/test_supply*.py
```

Run the full Python suite:

```sh
.venv/bin/python -m pytest backend/tests clients/tests benchmarks/tests
```

Run `npm test -- --run` and `npm run build` from `frontend`.
The [offline transcript report](reports/2026-09-08-supply-offline-dialogue.md) contains four completed API trajectories.
Tests cover both languages, both NPC roles, actor isolation, exact confirmation, retries, restart, and rendering failure.
Fixture tests exercise the LLM rendering and normalization paths without external calls.
Verification on 2026-09-08 passed the 972-test full Python suite and two additional client-contract tests.
The final frontend suite passed 90 tests. The production build passed.
Ruff and `git diff --check` passed.
The five affected core specifications contain the same normative DR-30 block.
Existing Starlette/httpx deprecation and Pydantic field-attribute warnings remain.
The RU Web UI was checked on isolated localhost services with a temporary SQLite database.
The check covered package display, publication, completed review, and reload.
Both temporary server processes were stopped after verification.

No paid model calls were made.
Live naturalness and cross-model quality remain unverified.
The [delivery plan](plans/05_reference-supply-and-generalization.md) keeps that validation gate before Stage B generalization.
The shared general-purpose deal DSL and the second-domain composite scenario are not implemented in this increment.
