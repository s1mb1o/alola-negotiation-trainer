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

---

## Difficulty / assistance modes

The same scenario can be reused at multiple difficulty levels.

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

---

## Important rule

Do not punish a player for not knowing hidden information.

You may punish or coach them for failing to investigate relevant signals.
