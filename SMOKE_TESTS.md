# Smoke Tests

## Specification acceptance tests

### Versioned schemas

- Validate `examples/scenario_supplier_001.yaml` against `schemas/scenario-v1.schema.json`.
- Verify that structural schema validation passes for the declared draft state.
- Attempt to publish the draft.
- Verify that the publication linter rejects every item in `missing_required_definitions`.
- Verify that a published scenario requires controlled composition-rule and evaluation-rule catalogs.
- Validate `schemas/event-example.json` against `schemas/negotiation-event-v1.schema.json`.

### Client parity

- Start the same human-versus-built-in-NPC session from the Web UI and CLI.
- Verify that both clients receive equivalent actor-safe observations.
- Verify that the Web UI and CLI use the same Player API.
- Run one human participant and one external-agent participant through the same natural-language message flow.
- Verify that neither participant can submit a typed public action.

### Context-aware agreement

- Submit `Согласен на 50% предоплаты` while a complete offer is active.
- Verify that the engine does not classify the message as complete acceptance.
- Submit `Согласен, если доставка будет раньше`.
- Verify that the engine creates a counteroffer.
- Submit `Согласен` when one complete active offer is the only possible referent.
- Verify that the response is `confirmation_required` and not `clarification_required`.
- Submit `Согласен` when the context can refer to one condition or the complete offer.
- Verify that the response is `clarification_required`.
- Submit an unambiguous complete-offer acceptance intent.
- Verify that the response is `confirmation_required` and shows the complete materialized offer.
- Confirm in natural language.
- Verify that the exact active revision becomes immutable and the session enters `agreement_reached`.

### Offer revisions and MESO

- Submit a delta against an active offer.
- Verify that the engine stores a new immutable complete offer revision.
- Verify that unchanged terms carry from the base revision.
- Unset an authored optional term in natural language.
- Verify that the materialized revision removes the term.
- Attempt to unset a required term.
- Verify that validation fails.
- Counter an active offer.
- Verify that the referenced revision becomes `superseded`.
- Attempt to accept the superseded revision.
- Verify HTTP `409`, `offer_not_active`, and the post-recording session revision.
- Create an explicit MESO offer set.
- Accept one alternative.
- Verify that every sibling alternative expires.
- Withdraw an active offer as its proposer.
- Verify that the withdrawn revision cannot be accepted.
- Attempt to withdraw an accepted offer.
- Verify that the engine rejects the transition.

### Clarification and retries

- Submit semantically ambiguous text.
- Verify that the server records the message and ambiguity but does not change the deal or consume a round.
- Verify that `next_actor` remains the same participant.
- Submit a clarification response that resolves to a substantive action.
- Verify that only the resolved action consumes a turn.
- Force one parser execution failure.
- Verify that the parser runs one retry.
- Force the parser retry to fail.
- Verify that the server records `parser_failure`, preserves deal state, and returns `clarification_required` with reason `parser_unavailable`.
- Force NLG failure through the initial attempt and two retries.
- Verify that the server uses an actor-safe deterministic template without duplicating the committed action.

### Revision and idempotency

- Repeat session creation with the same `idempotency_key`.
- Verify that the server returns the original session instead of creating another session.
- Submit a mutating request with a stale `expected_revision`.
- Verify HTTP `409` with `revision_conflict` and no new event.
- Repeat a successful request with the same `idempotency_key`.
- Verify that the server returns the stored response without another event.
- Repeat a stored `offer_not_active` request with the same `idempotency_key`.
- Verify that the server returns the same stored domain-error response without another event.

### Turn and terminal state machine

- Complete one default two-party round.
- Verify that both participants committed a substantive action before the round increments.
- Verify that a valid `pass` consumes a turn only when scenario policy permits it.
- Verify that the built-in NPC runs automatically only when the session is active and it is `next_actor`.
- Verify that agent-versus-agent mode commits at most one participant action per request.
- Reach scenario `max_rounds` without another terminal transition.
- Verify that the session enters `expired` after the complete round.
- Submit an unambiguous walk-away message.
- Verify that the session enters `walked_away` without a second confirmation.
- Call `/close` as a participant.
- Verify that authorization fails.
- Call `/close` as an administrator.
- Verify that the session enters `aborted` with an administrative reason.
- Force a recoverable processing failure after an authoritative action commit.
- Verify that the session remains active and resumes from the last committed revision.
- Exhaust the configured retry budget.
- Verify that the session enters `technical_failure` without duplicating an action.
- Generate a review from each terminal state.
- Verify that every terminal state has a review and terminal reason.

### Exact-revision fork

- Fork from `source_revision = N`.
- Supply the current parent `expected_revision` and a new `idempotency_key`.
- Verify that child initial revision is `N` and its first local event uses `N + 1`.
- Verify that offer IDs, offer lifecycle state, `next_actor`, pending protocol state, and delivered participant information match parent state after revision `N`.
- Override model policy as an authorized training orchestrator.
- Verify that the child records the override and the parent remains unchanged.

### Russian-first language support

- Start the supplier scenario with language `ru`.
- Verify that the session, prompts, transcript, and rendered messages record the language.
- Verify that structured term and event identifiers do not contain localized labels.

### Reservation boundary

- Evaluate a valid deal with utility equal to `reservation_utility`.
- Verify that the built-in policy treats the deal as acceptable.
- Evaluate a deal below `reservation_utility`.
- Verify that the built-in policy rejects the deal.
- Confirm the same below-reservation deal as a human participant and as an external-agent participant when every hard constraint passes.
- Verify that the engine permits the confirmation and that the review identifies the economic failure.
- Attempt to confirm a deal that violates a hard constraint as each controller type.
- Verify that the engine blocks binding for every controller type.

### Intentional no-ZOPA scenario

- Load a scenario that declares an intentional no-ZOPA training objective.
- Verify that the linter reports an empty ZOPA without rejecting the scenario.
- Verify that a rational walk-away can receive a successful outcome score.

### Unauthored term

- Submit a composite split-delivery schedule built from authored primitives and capabilities.
- Verify that the engine validates the typed tree and uses authored evaluation rules.
- Submit a proposal outside the compiled term grammar.
- Verify that no LLM or engine component assigns utility to the proposal.
- Verify that the proposal cannot become part of a binding agreement.
- Verify that the NPC may clarify, discuss, or decline it without changing deal utility.

### Knowledge and belief state

- Compile a high-level authored external-offer entity.
- Verify that the compiler creates stable atomic knowledge-item definitions.
- Extract evidence from a participant message.
- Verify that the extractor cannot write belief confidence or ground truth directly.
- Apply the validated evidence through the versioned belief-update policy.
- Verify that the event records confidence before and after with evidence event IDs.
- Verify that UI labels are derived from confidence and do not write state.
- Create an ungrounded participant hypothesis.
- Verify that the engine creates a stable `hypothesis_id` and deterministic initial confidence from evidence.
- Verify that it remains belief state and cannot change reality, constraints, utility, or deal validity.
- Replay the session.
- Verify that replay recreates hypotheses and reapplies stored evidence and belief transitions without an LLM.

### NPC action authority

- Supply a fuzzy ranker result that prefers an illegal action.
- Verify that the engine rejects the ranking and selects only a legal action.
- Verify that the dialogue generator receives no raw hidden facts or secret identifiers.

### Hidden-state release

- Request observations, history, metrics, and review during an active session.
- Verify that every response uses an actor-safe projection.
- Complete a training session with a selective reveal policy.
- Verify that the review releases only configured items and records the reason.
- Run a benchmark set.
- Verify that hidden review data remains sealed until the run set is finished.

### Benchmark integrity

- Create repeated benchmark trials with a fixed run configuration.
- Verify that each independent trial uses a fresh session.
- Verify that each tested agent plays both roles.
- Verify that hints and training assistance are disabled.
- Verify that a forked session is rejected as an independent benchmark trial.

### Future speech adapters

- Convert speech to text through STT before parsing.
- Verify that the canonical stored input is text plus structured events.
- Convert an actor-safe public message to audio through TTS.
- Verify that TTS does not receive raw hidden state.
