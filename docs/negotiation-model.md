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

A deal is acceptable when:

\[
U(deal) > U(BATNA)
\]

This is more general than a single price floor.

A supplier may accept a lower price in exchange for:

- faster payment;
- larger volume;
- lower warranty burden;
- a strategically important customer.

---

## ZOPA

ZOPA is the set of deals acceptable to both parties.

In a multi-dimensional negotiation, it should be thought of as a region in deal space, not only an interval on price.

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

## Information discovery

Players should not see hidden utility weights.

The player learns through dialogue.

The engine may track:

- facts discovered;
- critical facts discovered;
- inferred interests;
- confidence levels;
- information leakage.

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

---

## Objective criteria

Ambiguous conditions should be resolved using mutually acceptable verification rules.

Example:

- DOA criteria;
- reproducible diagnostic test;
- RMA confirmation;
- agreed logs or acceptance procedure.

The negotiation trainer should distinguish between negotiating principles and detailed contract drafting.
