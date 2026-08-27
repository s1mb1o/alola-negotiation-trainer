# Negotiation Model

## Multi-dimensional negotiation

A deal is a vector:

\[
x = (price, delivery, payment, volume, warranty, exclusivity, ...)
\]

Each side has a utility function:

\[
U_A(x), \qquad U_B(x)
\]

The utility function does not need to be linear.

For MVP, weighted piecewise functions are sufficient.

---

## BATNA

BATNA is the best alternative to a negotiated agreement.

BATNA utility is an input to the reservation utility.

The reservation utility is the authoritative threshold for economic acceptability and built-in policy acceptance.

A scenario may define a justified difference between BATNA utility and reservation utility. The justification can include switching cost, execution risk, or another authored adjustment.

A deal is acceptable when all hard constraints pass and:

\[
U(deal) \ge reservation\_utility
\]

This is more general than a single price floor.

A human or external-agent participant may bind a deal below its own reservation utility when every hard constraint passes.

The review must identify that economic failure.

A supplier may accept a lower price in exchange for:

- faster payment;
- larger volume;
- lower warranty burden;
- a strategically important customer.

---

## ZOPA

ZOPA is the set of deals acceptable to both parties.

In a multi-dimensional negotiation, it should be thought of as a region in deal space, not only an interval on price.

The ZOPA can be empty.

An intentional no-ZOPA scenario can train BATNA discipline and a correct walk-away decision.

The scenario must declare the expected ZOPA condition or training intent.

The scenario linter reports ZOPA status and compares it with the declared intent. It does not reject an intentional no-ZOPA scenario only because the ZOPA is empty.

---

## Pareto improvement

Deal `Y` Pareto-dominates deal `X` when:

\[
U_A(Y) \ge U_A(X)
\]

and

\[
U_B(Y) \ge U_B(X)
\]

with at least one strict inequality.

This captures value creation.

---

## Pareto frontier

The Pareto frontier contains efficient deals for which one party cannot be improved without making the other party worse off.

Post-session analytics can estimate:

- distance to frontier;
- unused value;
- dimensions that could have created more value.

---

## Local optima

Negotiators often get stuck in a local optimum because they search too few dimensions.

Example:

```text
(price)
```

instead of:

```text
(price, payment, delivery, volume, warranty, risk allocation)
```

A trainer should detect when discussion remains one-dimensional despite signals that other tradeable interests exist.

---

## Value creation vs value claiming

### Value creation

Increasing total available utility by finding trades where parties value dimensions differently.

### Value claiming

Capturing a larger portion of the already-created value.

The trainer should evaluate these separately.

---

## Non-linear utility

Example:

```text
Delivery <= Nov 10      utility 100
Delivery <= Nov 15      utility 90
Delivery <= Nov 20      utility 65
Delivery <= Dec 01      utility 20
Later                   utility 0
```

This is often more realistic than linear utility.

---

## Interaction terms

Utility may depend on combinations of terms.

Example:

- low price + 180-day payment can be bad for the supplier;
- higher price + 100% prepayment can be excellent.

So later versions may use:

\[
U = w_1P + w_2T + w_3PT
\]

MVP does not need this unless required by a scenario.

---

## Authored semantics and runtime structures

Each utility-bearing primitive and evaluation rule must be declared by the immutable scenario version.

The declaration defines the primitive identifier, type, unit, valid domain, capabilities, composition rules, and role-specific value function.

The declaration maps interests to one or more primitives or derived values.

A latent term is authored but may remain unavailable until its activation condition occurs.

A participant may create a concrete composite structure at runtime.

The structure can include a schedule, condition, contingency, obligation, option, or service level.

The engine validates the structure against authored capabilities, constraints, composition rules, and evaluation rules.

A valid runtime structure can affect utility even when the author did not enumerate that concrete package.

A proposal outside the compiled scenario grammar is an `unscored_proposal`.

The engine may let participants discuss, clarify, or decline an `unscored_proposal`.

An `unscored_proposal` cannot affect deal validity, ZOPA, or utility. It cannot become binding.

An LLM must not estimate provisional utility for an `unscored_proposal`.

---

## Information discovery

Players should not see hidden utility weights.

The player learns through dialogue.

The engine may track:

- validated evidence;
- true disclosures;
- participant-scoped beliefs;
- grounded and ungrounded hypotheses;
- confidence levels and evidence event IDs;
- information leakage.

The scenario compiler can create atomic knowledge-item definitions from authored domain entities.

The extractor proposes evidence from dialogue.

The belief engine applies a deterministic and versioned confidence update.

The UI derives display labels from confidence.

See `docs/knowledge-and-emergent-state.md` for the normative state model.

Potential metric:

```text
critical_information_discovered / critical_information_available
```

A more advanced metric can estimate information value.

---

## Exploration vs exploitation

### Exploration

Ask questions to learn about constraints and interests.

### Exploitation

Use already-discovered information to make an offer or trade.

Strong negotiation balances both.

---

## Contingent agreements

When sides disagree about future outcomes, an agreement may depend on what actually happens.

Example:

- 3 reserve devices are supplied;
- if used for confirmed hardware defects, they are FOC;
- if unused after a date, they are purchased.

This converts disagreement about probability into a contract conditional on outcome.

The contingent structure must use compiled DSL primitives and authored evaluation rules.

The engine stores the concrete runtime structure as a validated typed tree.

---

## Objective criteria

Ambiguous conditions should be resolved using mutually acceptable verification rules.

Example:

- DOA criteria;
- reproducible diagnostic test;
- RMA confirmation;
- agreed logs or acceptance procedure.

The negotiation trainer should distinguish between negotiating principles and detailed contract drafting.

An `agreed_in_principle` term is non-binding.

A binding deal requires confirmation of one complete active offer revision under `docs/offer-session-protocol.md`.
