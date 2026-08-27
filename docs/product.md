# Product Model

## Product thesis

A negotiation trainer should not be only a role-playing chatbot.

A strong trainer needs an explicit model of:

- what each side wants;
- what each side knows;
- what each side incorrectly believes;
- what has been revealed;
- what deal terms are currently proposed;
- how good the deal is for each side;
- which negotiation skills were used;
- whether value was created or merely claimed.

The LLM provides realistic conversation. The negotiation engine provides consistency.

The engine selects and validates each NPC action.

A future fuzzy LLM policy may rank legal actions. It cannot authorize an action, override a constraint, or assign utility to a proposal outside the compiled scenario grammar.

Human participants and external-agent participants use the same natural-language Player API.

The parser proposes an internal action. The engine validates and commits it.

---

## MVP interfaces and language

The Web UI is the hackathon demonstration interface.

The CLI is a required interface for operation, testing, and agent runs.

The MVP conversation language is Russian.

Structured state, utility models, and events must not depend on Russian text labels.

Each scenario and session must identify its language. The contracts must allow additional languages later.

This language extension can support a future proposal for ВАВТ.

STT and TTS are desirable extensions after the text workflow is stable.

Speech recognition produces text before parsing. Speech synthesis consumes an actor-safe public message after generation.

Audio is not the source of truth. The canonical history contains text and structured events.

---

## Player start state

The player receives a role brief, not a complete mathematical utility function.

Information should be divided into four categories.

### 1. Known facts

Facts the character must know.

Examples:

- budget;
- internal deadline;
- current supplier offer;
- production capacity;
- an instruction from management;
- known BATNA.

### 2. Private interests

Motivations the character knows.

Example:

> This client is strategically important because the company is entering the banking market.

These can be stated qualitatively.

### 3. Derived information

Facts are provided, but the correct negotiation implication is not.

Example:

> At volumes above 10,000 units, unit cost falls by 14%.

The system should not explicitly say:

> Use volume to trade for price.

### 4. Unknown information

Must be discovered through negotiation.

Examples:

- counterparty BATNA;
- real deadline;
- real budget;
- hidden operational constraint;
- internal approval problem;
- relative importance of price/payment/delivery.

---

## Beliefs are not reality

The player may start with incorrect assumptions.

Example:

> Your manager believes the buyer is extremely price-sensitive.

Reality:

- price importance: medium;
- delivery importance: very high.

This lets the trainer teach hypothesis testing rather than blind trust in the brief.

The scenario defines ground truth or deterministic rules that derive it.

The extractor emits proposed evidence from dialogue.

The extractor does not write belief state.

The belief engine updates participant-scoped confidence from validated evidence.

The UI can derive `UNKNOWN`, `PARTIAL_SIGNAL`, `PROBABLE`, and `CONFIRMED` labels from confidence.

These labels describe one participant's evidence state. They do not replace ground truth.

A participant can form an ungrounded runtime hypothesis.

The hypothesis can guide questions. It cannot change reality, utility, constraints, or deal validity.

## Emergent deal structures

The scenario author defines term primitives, capabilities, constraints, composition rules, and evaluation rules.

The author does not need to enumerate every concrete package.

A participant can create a split-delivery schedule, staged payment, contingent reserve, option, or another supported composite at runtime.

The extractor maps the proposal to a typed structure.

The engine validates and evaluates that structure through the compiled scenario rules.

A proposal outside the compiled grammar can be discussed. It cannot affect utility or become binding.

See `docs/knowledge-and-emergent-state.md` for the normative model.

## Agreement interaction

The system interprets agreement in context.

The phrase `согласен` can refer to one condition, an agreement in principle, or the complete offer.

Ambiguous agreement returns `clarification_required`.

Complete acceptance requires a second confirmation that displays the complete materialized offer.

The same flow applies to humans and external agents.

See `docs/offer-session-protocol.md` for the normative protocol.

---

## Difficulty / assistance modes

The same scenario can be reused at multiple difficulty levels.

Every mode uses an actor-safe observation projection.

Guided and Easy assistance may use visible evidence and permitted detected signals. It must not read raw counterparty utility, BATNA, constraints, or hidden facts.

Language is independent of difficulty.

### Guided

Shows:

- player's own priorities clearly;
- detected signals;
- likely interpretations;
- coaching about the type of next move.

Example:

> Signal: the supplier repeatedly returns to payment terms. This parameter may be important to them.

### Easy

Shows:

- clear own priorities;
- confirmed or probable counterparty interests;
- no direct recommended wording.

### Normal

Shows:

- role brief;
- conversation;
- current public terms.

No interpretation.

### Expert

May include:

- ambiguous brief;
- conflicting information;
- irrelevant information;
- weak signals;
- fewer explicit goals.

---

## Hint system

Hints should be progressive.

### Hint 1

Where to look.

### Hint 2

What interest may matter.

### Hint 3

What kind of negotiation move could help.

Avoid immediately providing the exact answer.

Every delivered hint must be recorded as an event.

Benchmark trials disable hints and training assistance.

---

## Training feedback

Separate:

- negotiation outcome;
- negotiation process;
- language quality;
- communication quality.

Possible scoring axes:

- Outcome
- Pareto efficiency
- Information discovery
- Information leakage
- Value creation
- Value claiming
- Conditional trading
- Active listening
- Objective criteria
- Relationship / rapport
- BATNA discipline
- Closing quality

A player may speak excellent language but negotiate badly.

Hints never reduce the economic outcome score.

The skill score records assistance usage and assistance mode.

Do not claim that skill scores are comparable across assistance modes until the scoring model is calibrated and validated.

A rational walk-away is a successful outcome when the scenario intentionally has no ZOPA or when every feasible deal is below the player's reservation utility.

---

## Important rule

Do not punish a player for not knowing hidden information.

You may punish or coach them for failing to investigate relevant signals.

---

## Hidden-state release policy

An active player never receives raw hidden state.

A completed training session may reveal selected hidden facts, utilities, or missed signals when the scenario review policy permits the reveal.

A training review must identify which information was revealed and why.

A benchmark trial does not reveal hidden information when the trial ends.

The benchmark system may release configured review information only after the complete run set is finished.

---

## Benchmark integrity

Each independent trial uses a fresh session.

Each tested agent plays both roles.

The runner repeats trials.

The runner fixes the scenario version, language, policy configuration, model configuration, prompt versions, and randomness configuration for a run set.

Benchmark trials disable hints and training assistance.

Forked sessions are training artifacts. They are not independent benchmark trials.
