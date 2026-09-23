# Training Methodology

## Human training loop (DR-36)

The training configuration MUST be restricted to one human and one built-in NPC in training mode.
The configuration MUST pin profile, relationship, shared background, private preparation, and rule versions.
The engine MUST validate finite numeric targets against the scenario's scalar term grammar.
Only an agreed complete deal MAY satisfy a deal-term target.
Free-text goals MUST NOT receive invented completion percentages.

Social state MUST use bounded rapport, credibility, tension, and patience values.
The classifier MAY propose at most two allowlisted events with exact message excerpts.
The engine MUST apply validated changes once per committed revision.
Positive relationship events MUST have cumulative caps.
Classification failure MUST leave social state unchanged.
Social values MUST NOT override economic acceptability or binding-confirmation rules.

Coaching MUST require an explicit authenticated request after session termination.
The reviewer MUST receive only the owner's permitted evidence, preparation, and economic baseline.
Generation and grounding MUST run outside write transactions.
The service MUST cache the validated result or an unavailable status.
Active and sealed benchmark sessions MUST NOT initiate coaching.
Model failure MUST preserve the deterministic report.
Exact cited excerpts MUST be attached by the service.

Retry MUST require a completed human training session and an existing immutable checkpoint.
The child MUST restore the selected state and history boundary with fresh participant credentials.
It MUST NOT inherit later history, parent credentials, render jobs, or idempotency results.
The comparison MUST use the same role and identify observed results as informed practice.
It MUST NOT claim causal skill improvement.
Legacy sessions without checkpoints and benchmark sessions MUST NOT use this training fork.

The API schemas, formulas, limits, and verification boundary are documented in the [human training guide](human-training-guide.md).

## Separation of responsibilities

The simulation engine answers:

- what the parties want;
- what is possible;
- what is acceptable;
- what information is hidden;
- how deal utility changes.

The training layer answers:

- what skill the player demonstrated;
- what signal they missed;
- what was effective or ineffective;
- what to try differently next time.

---

## Suggested skill taxonomy

### Discovery

- open questions;
- probing;
- clarification;
- checking assumptions;
- uncovering interests;
- identifying constraints.

### Listening

- active listening;
- paraphrasing;
- summarizing;
- labeling;
- mirroring.

### Bargaining

- anchoring;
- conditional concessions;
- reciprocity;
- package offers;
- MESO;
- value claiming.

### Value creation

- identifying differently-valued terms;
- creating validated runtime deal structures;
- split delivery;
- volume/price trades;
- payment/price trades;
- contingent agreements;
- risk allocation.

### Process

- objective criteria;
- BATNA discipline;
- relationship management;
- closing;
- documenting agreement.

---

## Feedback should be evidence-based

### Goal-based final review (DR-33)

Status: accepted requirement. Bounded implementation delivered under [DR-36](decisions/2026-09-24_training-loop.md).

The terminal training review MUST include LLM analysis of progress toward the participant's recorded goals and actionable recommendations.
The engine MUST supply the authoritative outcome, constraints, utility, and any numeric goal-progress measures.
Each evaluative claim and recommendation MUST reference supporting session evidence or an authored goal or rule.
The review MUST distinguish observed results from hypotheses about alternative actions.
The review MUST enforce actor-specific disclosure permissions and the benchmark run-set release gate.
An unavailable or invalid LLM analysis MUST leave the deterministic outcome report available and identify the missing analysis.

Recommendations SHOULD identify the episode, alternative action, relevant goal, and a way to check improvement.
The review MUST distinguish a negotiated result from an unaccepted proposal.
It MUST NOT infer economic success from rapport or positive wording.
It MUST NOT infer negotiation skill from question counts alone.
It MUST NOT penalize a participant for hidden information unavailable at the decision point.
The scenario's authored objectives determine whether a walk-away is successful.
Missing measures MUST remain unknown instead of receiving an invented percentage.

See [DR-33](decisions/2026-09-23_goal-based-llm-review.md) and [the review design](social-state-and-llm-dialogue.md#71-final-goal-based-review-dr-33).

The review MUST distinguish initial relationship advantages from behavior demonstrated during this session.
Successful past deals can establish initial familiarity under [DR-35](decisions/2026-09-23_player-background.md).
They are not evidence of skill demonstrated in the current attempt.
Comparisons between attempts MUST report differences in the initial background and assistance.

All application-owned LLM instructions and task templates MUST be written in English.
The MVP player-facing dialogue, hints, and final review MUST be in Russian.
Russian messages, quotes, authored text, and examples MAY remain in their original language as clearly separated task data.
See [DR-34](decisions/2026-09-23_prompt-language.md).

### Evidence-linked explanation

Bad feedback:

> Good empathy, 8/10.

Better feedback:

> When the supplier said payment terms mattered, you immediately offered flexibility without first asking what they would provide in return. This revealed a valuable resource before pricing it.

Each feedback claim must reference one or more evidence event IDs.

Evidence events include claims, extracted signals, belief updates, contradiction detection, exposed bluffs, runtime term creation, delivered hints, delivered distractors, offers, clarification requests, and accepted state transitions.

---

## Replay / deliberate practice

After the session, identify key moments.

Example:

> At turn 4, you were close to a local optimum because the discussion remained focused on price.

Allow the player to replay from the exact session revision before that action.

This creates:

```text
attempt
  ↓
feedback
  ↓
retry
  ↓
comparison
```

---

## Difficulty-dependent assistance

### Guided

May show:

```text
FACT
You can pay up to 100% upfront.

INFERENCE
Payment terms appear important to the supplier.

COACHING
Try to trade payment flexibility for something valuable to you.
```

### Easy

Show facts and probable interests.

Show one case-specific NPC greeting before the human's first turn.

Do not include deal terms or negotiation advice in the greeting.

Keep the human as the first live negotiation actor.

When an external agent is `next_actor`, retain the canonical Easy opening presentation.

The external-agent presentation states exactly the terms in the authored `opening_offer` or `opening_position`.

Do not fill an omitted required term with a default or placeholder value.

The external-agent presentation describes a partial `opening_position` as a position, not as a complete package.

Store the greeting or presentation and its delivery event at session revision 0.

Do not count it as a turn or a hint.

The labels are actor-safe views derived from belief confidence and visible evidence.

### Normal

Show only brief + public state.

### Expert

Show authored ambiguous, conflicting, outdated, or irrelevant information.

An LLM may paraphrase visible distractor content. It must not invent facts or change numbers.

Store the exact rendered distractor content as a participant delivery event.

Keep the authored `truth_note` and other hidden evaluation data outside the participant observation.

---

## Outcome and skill scores

The outcome score measures the economic result.

Hints and assistance do not reduce the outcome score.

The skill score records assistance usage and assistance mode.

The review lists the delivered assistance and its evidence events.

The skill score is an intended cross-mode comparator. Do not claim cross-mode validity until the formula is calibrated and validated.

A rational walk-away can be a successful outcome in an intentional no-ZOPA scenario.

---

## Bluffing and claims

Bluffing is permitted.

The evaluator does not apply a moral penalty for a bluff.

Each participant has a claim ledger.

The engine keeps claims separate from verified facts and inferred interests.

The extractor records a claim and proposed evidence.

The deterministic belief engine updates confidence.

An ungrounded hypothesis remains participant belief state. It does not become scenario truth.

An unexposed bluff is not information leakage.

An exposed contradiction may reduce credibility and change counterparty policy.

The review reports the evidence and observed consequence without moral language.

---

## Benchmark evaluation

Each independent benchmark trial uses a fresh session.

Each tested agent plays both roles.

The runner repeats trials with a fixed scenario version and fixed run configuration.

Benchmark trials disable hints and training assistance.

The runner reports results by role and across repetitions.

The benchmark keeps hidden information sealed until the complete run set is finished.

---

## Human evaluation

Early product development should include manual review of generated dialogues.

Useful labels:

- natural / unnatural;
- appropriate / inappropriate response;
- revealed hidden information too easily;
- accepted an implausible offer;
- ignored player input;
- repetitive;
- inconsistent with role;
- feedback useful / superficial.

This human evaluation can later inform prompts, policies, and automated evaluators.
