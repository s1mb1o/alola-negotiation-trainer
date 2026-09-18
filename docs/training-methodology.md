# Training Methodology

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

When the built-in NPC is the opening role, show one canonical opening message before the player's first turn.

Show exactly the terms in the authored `opening_offer` or `opening_position`.

Do not fill an omitted required term with a default or placeholder value.

Describe a partial `opening_position` as a position, not as a complete package.

Store this message and its delivery event at session revision 0.

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
