# Decision Records — 2026-08-27 (post-review)

- **Decided by**: Alexander Shmelev.
- **Context**: answers to the open questions in §10 of [the review](../reviews/claude-fable-max-20260827.md). Recorded by Claude Fable 5 from the discussion; consequences sections are the reviewer's analysis of the decisions.
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
- NLG permits two retries after the first failure and then uses a deterministic template.
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

## Open decisions

- The implementation stack.
- The scenario-version freeze point.
- Credibility scale and update rules.
- Skill-score calibration across assistance modes.
- The exact v1 controlled-DSL primitive set.
- Belief-confidence update policy and display thresholds.
