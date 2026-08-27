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
- creating new dimensions;
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

---

## Replay / deliberate practice

After the session, identify key moments.

Example:

> At turn 4, you were close to a local optimum because the discussion remained focused on price.

Allow the player to replay from that turn.

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

### Normal

Show only brief + public state.

### Expert

Show ambiguity and noisy information.

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
