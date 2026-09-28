# Decision Records — 2026-08-27 (post-review)

- **Decided by**: Alexander Shmelev.
- **Context**: answers to the open questions in §10 of the review. Recorded by Claude Fable 5 from the discussion; consequences sections are the reviewer's analysis of the decisions.
- **Timeline note**: ~2 weeks remain before the hackathon start. This changes the scope calculus of the review's §6.

---

## DR-1. Agent-vs-agent benchmarking is in scope now

**Decision.** Build for agent-vs-agent play within the pre-hackathon window, not post-hackathon.

**Rationale.** Almost 2 weeks remain before the hackathon start; the extra scope is affordable.

**Consequences.**
- Review gap **G5** (participant identity, tokens, scenario-endpoint gating) moves from "later" to early implementation. It is now required, not optional.
- The session model MUST use `participants: [{id, role, controller}]` from day one. The NPC is a built-in participant, not a special case.
- `GET /sessions/{id}/observation` MUST be scoped by participant token.
- The message-response contract is role-neutral. It returns committed turn results plus `next_actor`. A benchmark runner can drive both seats sequentially over the same synchronous API. The MVP does not require SSE or WebSocket.
- Benchmark integrity: controller history or an unsafe branch observation can contaminate a forked trial. Independent benchmark trials MUST use fresh sessions. Prompt-injection resistance (review G8) becomes a validity requirement for benchmark results.

**Risks.** Added scope two weeks before the deadline. Mitigation: external agents use the same natural-language Player API as humans. Typed actions remain internal controller actions.

---

## DR-2. Bluffing is allowed; evaluated by consequences, not morally penalized

**Decision.**
- Bluffing is a permitted tactic. The bluff itself carries no penalty.
- The evaluator scores the bluff's **result and quality**: did it create leverage; does it contradict facts already known to the counterparty; did it cause a loss of trust.
- If a participant lies and the counterparty exposes the lie, `credibility` MUST decrease. If the lie is never exposed, it stands as an acceptable tactic.
- A separate `deception_risk` metric MAY be computed. It is analytics, not a moral penalty.

**Consequences.**
- Confirms the review's G4 default: the belief state MUST separate `claims` (asserted, unverified) from `revealed_facts` (ground truth disclosed). Claims are never merged into facts without verification.
- The engine needs a claim ledger for each participant. Each claim is recorded as an event. The engine checks a claim against the participant's earlier claims and the facts that the counterparty is permitted to know. Exposure is possible only when the counterparty has evidence for the contradiction.
- `credibility` becomes a tracked state variable. Its relationship with `rapport`, scale, and update function remain open. An exposed lie establishes a negative credibility signal but not a numeric update rule.
- Counterparty policy gains reactions to a detected contradiction: challenge it, silently discount the claim, or harden its position. The deterministic validator (G7) determines which reactions are legal.
- The information-leakage metric counts **true** reveals only; bluffs are not leakage.
- Review output reports bluffs neutrally. It reports counts, evidence, credibility direction, and the observed negotiation consequence. It MUST NOT report a numeric credibility delta until the scale and update rule are defined.

**Risks.** Contradiction detection over free-form Russian text is parser-dependent (review G6). MVP detection SHOULD be limited to claims about canonical dimensions and briefed facts, not arbitrary statements.

---

## DR-3. Two-score model: hints reduce the skill score, never the outcome score

**Decision.**
- `Outcome score`: the economic result. No penalty for hints. Otherwise comparison of negotiated outcomes becomes unfair.
- `Skill / independent performance score`: penalized by the level of assistance actually used.
- The review MUST state assistance usage explicitly, e.g. "result achieved with 2 hints."

**Consequences.**
- The review schema gets `outcome_score`, `skill_score`, and `assistance_usage` (hints used, levels, per-hint event references).
- Every delivered hint MUST be logged as an event (aligns with review C8 and R2). The penalty and the review sentence are computed from these events.
- The assistance **mode** (Guided/Easy/Normal/Expert) is itself assistance. The skill score MUST factor in the mode, not only the hint count.
- Benchmark and leaderboard comparisons of `outcome_score` are valid only within the same assistance mode. `skill_score` is the intended cross-mode comparator. Do not claim cross-mode validity until the scoring formula is calibrated and validated.

**Risks.** Penalty calibration is arbitrary at first. Start with a simple published formula (e.g. flat deduction per hint level) so scores are explainable to a jury.

---

## DR-4. Scenario format: external declarative schema from day one; schema + linter before authoring UI

**Decision.**
- The team authors all MVP scenarios.
- The format MUST be an external declarative schema from the start. No hardcoded scenarios.
- Priority order: schema + validator/linter first. A visual editor for end users / corporate methodologists comes later, built on the same schema.

**Consequences.**
- Confirms review next-action #1 (scenario schema v1 with value functions, latent dimensions, units) as the first work item.
- Promotes the scenario linter (review R5), including ZOPA-status calculation and comparison with declared scenario intent, into MVP scope.
- Publish a real JSON Schema in `schemas/` (fixes review C5) so future external tools and the eventual editor validate against the same contract.
- `schemas/scenario-v1.schema.json` is the v1 structural contract. The publication linter performs cross-field and executable-model checks that JSON Schema cannot express safely.
- A session remains attached to one immutable scenario version. The exact version freeze point remains open.

**Risks.** Schema over-design. Mitigation: v1 covers exactly what the current supplier scenario plus DR-5 distractors need — nothing more.

---

## DR-5. Expert-mode ambiguity: authored distractors only; the LLM may paraphrase, never invent facts

**Decision.**
- Distractors are **authored scenario content** with semantic meaning: a manager's erroneous opinion, outdated information, a contradictory letter, an irrelevant fact.
- Generated noise is rejected: poorly reproducible, and it can accidentally change the task.
- The LLM MAY paraphrase authored distractors. It MUST NOT invent new facts.

**Consequences.**
- The scenario schema gets a `distractors` block: `{id, type: wrong_opinion | outdated | contradictory | irrelevant, content, truth_note}`. Each distractor is role-scoped and has a delivery condition. `truth_note` is hidden author and engine data. The current YAML flag `add_ambiguous_context: true` becomes a reference to visible distractor entries.
- Distractor delivery (including the paraphrased text actually shown) MUST be logged as events (review R2) for reproducibility and honest post-session review.
- The "never invent facts" rule is a new invariant for the brief, observation, and dialogue renderers.
- New evaluator opportunity: **distractor resistance** — did the player act on false information or verify it before relying on it? Fits the existing "checking assumptions" skill in the taxonomy.

**Risks.** Paraphrasing can drift semantically. Low temperature is not a sufficient control. Use a deterministic template or fact-preservation validator and store the rendered text.

---

## DR-6. Decision records and synchronized core specifications are authoritative

**Decision.**
- An accepted dated decision record is authoritative.
- Every affected normative specification MUST be updated in the same change.
- A decision record link does not replace the normative rule in a core specification.

**Consequences.**
- `README.md`, `AGENTS.md`, and the affected files in `docs/` must contain the confirmed rules directly.
- Review documents remain historical artifacts. They do not become normative specifications.

---

## DR-7. Web UI demonstration, required CLI, and optional speech adapters

**Decision.**
- The Web UI is the hackathon demonstration client.
- The CLI is a required client for operation, testing, and agent runs.
- STT and TTS are desirable extensions after the core text workflow is stable.

**Consequences.**
- Web UI and CLI use the same Player API and actor-safe observations.
- STT produces canonical text before parsing.
- TTS consumes an actor-safe public message after generation.
- Audio is not the source of truth.
- Voice sentiment and emotion analysis remain outside the MVP.

---

## DR-8. Russian-first language strategy

**Decision.**
- Russian is the MVP conversation language.
- The domain model, scenario format, API, and event model MUST allow additional languages later.

**Consequences.**
- Structured identifiers remain language-neutral.
- Each scenario and session identifies its language.
- Parser, NLG, evaluation, and UI text resources are versioned by language.
- The extension path can support a future proposal for ВАВТ.

---

## DR-9. Reservation utility and intentional no-ZOPA scenarios

**Decision.**
- `reservation_utility` is the authoritative utility acceptance threshold.
- A deal is acceptable only when all hard constraints pass and `U(deal) >= reservation_utility`.
- BATNA utility is an input to reservation utility.
- A scenario MAY intentionally contain no ZOPA.

**Consequences.**
- A scenario can define a justified difference between BATNA utility and reservation utility.
- A scenario with no ZOPA can train correct walk-away behavior.
- The scenario MUST declare its expected ZOPA condition or training intent.
- The linter reports ZOPA status and compares it with the declared intent. It MUST NOT reject an intentional no-ZOPA scenario only because no ZOPA exists.

---

## DR-10. Compiled term semantics and future fuzzy NPC policy

**Decision.**
- A proposal outside the compiled scenario grammar MUST NOT receive an LLM-generated utility value.
- The engine selects and validates the authoritative NPC action.
- A future fuzzy LLM policy MAY rank legal action candidates that the engine provides.

**Consequences.**
- The MVP supports authored primitives, authored latent terms, and validated runtime composites.
- A runtime composite can emerge from authored primitives, capabilities, and evaluation rules.
- A proposal with semantics outside the compiled scenario grammar remains outside the utility model until a new scenario version defines it.
- The NPC may clarify, discuss, or decline a proposal outside the compiled scenario grammar. The proposal cannot affect deal validity or utility.
- A fuzzy ranker cannot add a term, authorize disclosure, override a hard constraint, or accept below reservation utility.

---

## DR-11. Tiered hidden-state release

**Decision.**
- An active participant never receives raw hidden state.
- A completed training session may reveal selected hidden information under an explicit review policy.
- A benchmark trial does not reveal hidden information until the complete run set is finished.

**Consequences.**
- Every Player API response uses an actor-safe projection.
- Training review output records what hidden information was released and why.
- Benchmark output remains sealed between trials in the same run set.
- Scenario author and administrator access remain separate from participant access.

---

## DR-12. Independent benchmark protocol

**Decision.**
- Each independent benchmark trial uses a fresh session.
- Each tested agent plays both roles.
- The runner repeats trials.
- The runner fixes the scenario version and run configuration for the run set.
- Hints and training assistance are disabled.

**Consequences.**
- The run configuration records language, model and provider versions, prompt and policy versions, generation parameters, and randomness settings.
- The report separates results by role and includes aggregate results across repetitions.
- Forked sessions remain valid training and replay artifacts. They are not independent benchmark trials.
- The exact repetition count is a benchmark configuration value.

---

## DR-13. Text-first offer and session protocol

**Decision.**
- Human participants and external-agent participants use the same natural-language Player API.
- The public Player API does not give an external agent a typed action advantage.
- The parser proposes a typed internal action. The engine validates and commits the action.
- A client can propose a delta. The engine stores an immutable complete offer revision.
- A participant can remove an authored optional term through an explicit natural-language `unset` instruction.
- An ordinary counteroffer supersedes the referenced revision. A superseded offer cannot be accepted.
- Multiple active alternatives require an explicit MESO offer set.
- Acceptance of one MESO alternative expires its siblings.
- Binding acceptance by a human or external-agent participant uses a context-aware intent step and a separate confirmation step.
- The parser must distinguish agreement with one condition from acceptance of the complete offer.
- The phrase `согласен` is not binding without context and confirmation.
- `agreed_in_principle` and partial acceptance are non-binding.
- Ambiguity returns `clarification_required` and does not change the deal state or consume a round.
- The engine computes `next_actor` and serializes session writes.
- A clarification keeps the same `next_actor` and does not consume a round.
- `pass` is legal only when scenario policy permits it.
- A built-in NPC runs automatically after a valid human or external-agent action when it is the next actor.
- An external-agent-versus-external-agent request commits one action.
- A built-in NPC can ask, hold, reject, or walk away without a counteroffer.
- An offer remains active until withdrawal, supersession, rejection, acceptance, or session termination.
- An accepted offer cannot be withdrawn.
- The terminal states are `agreement_reached`, `walked_away`, `expired`, `aborted`, and `technical_failure`.
- The MVP uses `max_rounds` for expiry.
- `POST /sessions/{id}/close` is an administrative abort operation.
- A fork identifies an exact source session revision.

**Consequences.**
- Web UI controls submit canonical natural-language messages through the same Player API flow.
- The engine stores a pending confirmation before it can bind a natural-language participant's agreement.
- All required terms and hard constraints must pass before binding.
- A human or external agent may accept below its own reservation utility. The review reports the failure.
- A built-in NPC cannot accept below reservation utility.
- A parser transport or schema failure permits one retry.
- An eligible non-binding NPC turn uses at most one provider attempt in the MVP and then uses the precomputed deterministic template.
- A stale acceptance returns HTTP `409` with `offer_not_active`.
- A recoverable processing failure resumes from the last committed revision without duplicating an action.
- The evaluator produces a review for every terminal state.
- Forks inherit state, delivered information, open offers, and configuration at the exact source revision.

The normative contract is in [the offer and session protocol](../offer-session-protocol.md).

---

## DR-14. Authored knowledge and runtime emergent state

**Decision.**
- The scenario defines ground truth or deterministic rules that derive ground truth.
- The scenario defines capabilities, term primitives, composition rules, constraints, and utility rules.
- A scenario compiler may expand high-level entities into atomic knowledge-item definitions.
- The LLM extractor proposes evidence. It does not write belief state.
- The belief engine updates confidence with deterministic versioned rules.
- UI labels such as `UNKNOWN`, `PARTIAL_SIGNAL`, `PROBABLE`, and `CONFIRMED` are derived from confidence.
- A participant may form a runtime hypothesis that is absent from the authored world.
- An ungrounded hypothesis is a belief. It is not ground truth and cannot change utility.
- A concrete deal structure may emerge at runtime from authored primitives, capabilities, and evaluation rules.
- A proposal outside the compiled grammar or evaluation rules has no utility and cannot become binding.

**Consequences.**
- Session state contains an authored world and a runtime emergent world.
- Concrete split-delivery schedules and contingent terms do not need to be enumerated in the scenario.
- The engine stores emergent deal structures as validated typed abstract syntax trees.
- Claims, evidence, participant beliefs, true disclosures, and reality remain separate.
- Replay stores and reapplies validated evidence and deterministic belief updates without an LLM.

The normative contract is in [the knowledge and emergent state model](../knowledge-and-emergent-state.md).

---

## DR-15. Administrator Session Inspector

**Decision.**
- The Web UI contains a separate administrator Session Inspector.
- The Inspector uses administrator endpoints that require the `NEGOTIATION_ADMIN_TOKEN` Bearer credential.
- The Inspector can list SQLite sessions and filter by status, scenario, language, and run mode.
- A session detail can contain participant metadata, raw transcript messages, public event payloads, immutable offer revisions, and an allowed public review.
- The administrator projection MUST omit participant credentials, credential hashes, raw session state, scenario source, private event payloads, and private review data.
- An active session MUST NOT expose review data.
- A benchmark review MUST remain sealed until its complete declared run set is terminal.
- A terminal training session and a released benchmark session MAY expose `reviews.public_json`.
- The browser MUST keep the administrator credential in memory or `sessionStorage` only.

**Consequences.**
- The administrator API is separate from the Player API.
- Administrator access does not change participant observation or review-release rules.
- The Inspector is read-only in this increment.
- The Inspector does not expose scenario-authoring secrets or utility models.


---

## DR-16. Optional LLM rendering for built-in NPC dialogue

Accepted on 2026-08-28.

The exact-option and NPC-only-context rules below are historical.
[DR-26](2026-09-05_contextual-npc-dialogue.md) supersedes those rules from 2026-09-05.
DR-26 preserves deterministic action selection, canonical messages, credential protection, and durable rendering.

**Decision.**
- The engine MUST select and validate the authoritative built-in NPC action before dialogue rendering.
- The engine MUST select each fact that the NPC can disclose before dialogue rendering.
- The dialogue renderer MUST receive a dedicated allowlisted `NpcDialogueRequest`.
- The request MUST contain only the approved speech act, approved public offer terms, approved qualitative disclosures, scenario language, scenario currency, participant-facing term identifiers, approved reply options, the deterministic fallback, and bounded previously delivered NPC reply context.
- The request MUST NOT contain a raw observation, raw scenario source, role brief, raw session state, counterparty-private state, utility weights, reservation utility, BATNA utility, authored knowledge truth, distractor truth notes, constraints, private event payloads, reviews, participant credentials, provider credentials, or a list of forbidden secrets.
- Participant text is untrusted data.
- The renderer request MUST NOT contain raw participant text.
- Renderer context MAY contain only engine-authored or validated NPC messages that the service already delivered.
- NPC reply context MUST contain no more than six turns.
- Each NPC reply context turn MUST contain no more than 1,000 characters.
- The service MUST redact the authenticated participant token and credential-shaped fragments before it parses or persists a participant message.
- `approved_reply_options` MUST contain no more than six engine-authored actor-safe strings.
- Each approved reply option MUST contain no more than 1,200 characters.
- All approved reply options together MUST contain no more than 4,000 characters.
- An approved reply option MUST NOT interpolate or quote raw participant or transcript text.
- A non-binding approved reply option MUST NOT contain a number, date, percentage, currency symbol, or currency code.
- An external provider MAY process only a non-binding speech act.
- For a non-binding speech act, the provider MUST select one approved reply option without changes.
- The provider response MUST be one strict JSON object with only `speech_act` and `reply`.
- A deterministic validator MUST require speech-act equality and exact reply-option membership.
- The validator MUST reject invalid JSON, unexpected fields, empty output, unsafe structure, multiple speakers, markup, tool output, URLs, and output that exceeds a bound.
- Provider output MUST NOT synthesize public prose, an offer, a term, an acceptance, a rejection, a disclosure, or a lifecycle action.
- `opening_offer`, `offer_acceptance`, `offer_rejection`, and `complete_counteroffer` MUST bypass the provider.
- Each binding speech act MUST use the canonical deterministic template and canonical engine-approved terms.
- The service MUST use a deterministic actor-safe template when no dialogue provider is configured.
- The service MUST use the precomputed deterministic template when provider execution fails, times out, returns empty or invalid output, or violates the output contract.
- A provider call MUST occur outside a SQLite write transaction.
- Dialogue rendering failure MUST NOT roll back or duplicate an authoritative action.
- Provider credentials MUST remain in process environment variables.
- Provider credentials, unvalidated provider output, raw provider errors, and prompts MUST NOT enter the database, transcript, events, API responses, logs, reviews, or benchmark artifacts.

**Consequences.**
- The built-in NPC policy remains deterministic.
- An optional `NpcDialogueRenderer` selects one engine-approved wording for an approved non-binding action.
- The renderer supports deterministic template, OpenAI, and Qwen modes.
- The default mode is deterministic template rendering.
- The service persists the approved NPC intent before an external provider call.
- A render attempt has a stable session and intent-revision identity.
- The service atomically claims a pending render job with a compare-and-swap update before one provider attempt.
- Concurrent service instances MUST NOT make more than one provider attempt for the same render job.
- The service delivers at most one validated provider message or deterministic fallback for that identity.
- The service delivers a deterministic fallback for an unfinished durable render job during startup recovery.
- A pending render job blocks a new participant message, hint, or administrative close until delivery finishes.
- A create-time built-in NPC binding action uses its canonical deterministic message in the create transaction and does not invoke a provider.
- The public Player API returns the authoritative structured action and the delivered public message.
- A client MUST use the structured action and offer as the source of truth.
- A client MUST NOT infer a lifecycle action from generated prose.
- Russian and English renderers use the same structured speech-act contract.
- Prompt injection can affect only the selection among options for the same approved speech act.
- Concurrent sessions MUST NOT share dialogue, actor state, renderer request state, or write-transaction time.
- Failure telemetry uses safe provider metadata and the bounded reason codes `provider_failure`, `output_invalid`, `renderer_failure`, and `restart_recovery`.
- OpenAI rendering defaults to `gpt-5.6-luna`.
- Qwen rendering defaults to `qwen3.8-max` and the QwenCloud Token Plan endpoint.
- The service does not send `temperature` when `NEGOTIATION_NPC_TEMPERATURE` is empty.

**Risks.** A provider can follow untrusted dialogue instructions or receive the wrong credential through unsafe custom configuration. Mitigation requires a strict input allowlist, closed reply options, provider-bound credential configuration, exact-match output validation, bounded context, deterministic binding messages, and deterministic fallback.

---

## DR-17. Built-in NPC opens Easy sessions

Accepted on 2026-08-28.

**Supersession note.** DR-31 replaces this presentation with a neutral greeting for human-versus-built-in-NPC training sessions. This rule remains in effect when the next actor is an external agent.

**Decision.**
- An Easy training session MUST present the authored opening offer in the transcript when the opening-offer participant uses the built-in NPC controller.
- The service MUST use the canonical `opening_offer` template.
- The message MUST contain only the complete public opening-offer terms and actor-safe scenario language.
- The message MUST use `session_revision = 0`.
- The message MUST NOT create, revise, counter, accept, reject, or withdraw an offer.
- The message MUST NOT increment the session revision, round, or substantive-turn count.
- The message MUST NOT change `next_actor`.
- The message MUST NOT create negotiation evidence, a belief update, or a detected-interest signal.
- The message MUST bypass an external dialogue provider.
- The service MUST record one `npc.opening_utterance.delivered` event.
- A repeated create-session request MUST NOT duplicate the message or event.
- The service MUST NOT synthesize a message for a human or external-agent opening-offer participant.

**Consequences.**
- The built-in opponent starts an Easy session before the player sends a message.
- The authored opening offer remains the structured source of truth.
- Web, CLI, Telegram, replay, and Inspector clients receive the same stored transcript.
- Guided, Normal, and Expert creation behavior does not change.

**Supersession note.** DR-18 supersedes the complete-offer assumption in DR-17 only when a scenario uses `opening_position`. All other DR-17 rules remain in effect.

---

## DR-18. Partial authored opening positions do not use placeholder values

Accepted on 2026-08-28.

**Decision.**
- Exactly one scenario role MUST define exactly one authored opening artifact.
- The artifact MUST be either `opening_offer` or `opening_position`.
- `opening_offer` MUST contain every required term.
- `opening_position` MAY omit required terms.
- `opening_position` MUST contain at least one authored term.
- An omitted required term in `opening_position` is `UNSPECIFIED`.
- The omitted term MUST remain in `unresolved_required_terms` until a participant proposes it.
- The compiler and service MUST NOT infer, copy, default, or substitute a value for an omitted term.
- An explicit zero is a real term value. The compiler and service MUST NOT interpret zero as `UNSPECIFIED`.
- The initial active offer revision MUST expose only the terms that the authored opening artifact contains.
- A partial opening position MUST NOT become binding.
- The service MUST NOT create an acceptance confirmation for a partial opening position.
- In Easy training, a built-in NPC opening role MUST present exactly the authored public terms.
- The Easy presentation MUST use a deterministic canonical template.
- The Easy presentation speech act MUST match the authored artifact: `opening_offer` or `opening_position`.
- `opening_position` MUST bypass an external dialogue provider.
- The Easy presentation MUST NOT imply that an `opening_position` is a complete package.
- The Easy presentation MUST NOT add a hidden active term or expose a private term.
- Published scenario versions remain immutable.
- `supplier_001` version 2 MUST retain its authored zero-prepayment and eight-week opening offer for replay.
- `supplier_001` version 3 becomes the current published version and uses `opening_position: {price: 120000}`.

**Consequences.**
- A participant must resolve every required term before binding acceptance.
- An active partial offer revision reports the missing term identifiers in `unresolved_required_terms`.
- A counteroffer can add an omitted required term through the standard natural-language message flow.
- Existing complete `opening_offer` scenarios keep their current behavior.
- Public metadata MAY retain the compatibility field name `opening_offer_role`. This field identifies the opening role for either artifact.
- Clients must use `unresolved_required_terms` to distinguish a partial opening position from a complete offer.
- A scenario author omits an unannounced term instead of inserting `0`, `null`, an empty string, or another placeholder.

**Risks.** A client can describe a partial opening position as a complete offer if it ignores `unresolved_required_terms`. Contract tests and UI tests must cover this case.

**Supersession note.** DR-31 replaces the Easy opening presentation with a neutral greeting for human-versus-built-in-NPC training sessions. The authored opening artifact and unresolved-term rules remain in effect.

---

## Open decisions

- The implementation stack.
- The scenario-version freeze point.
- Credibility scale and update rules.
- Skill-score calibration across assistance modes.
- The exact v1 controlled-DSL primitive set.
- Belief-confidence update policy and display thresholds.
