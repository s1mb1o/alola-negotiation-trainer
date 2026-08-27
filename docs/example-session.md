# Example Negotiation Session

This is a condensed example based on the design discussion.

## Scenario

Player: Vector, buyer of 100 industrial computers.

NPC: Nord Systems, supplier.

Language: Russian (`ru`).

Assistance mode: Normal.

Assistance usage: none.

Session participants:

- `buyer`: human controller;
- `seller`: built-in NPC controller.

### Player brief

- Nord offer: €120,000.
- Budget ceiling: €115,000.
- Preferred target: €105,000.
- Alternative supplier: €108,000, but worse hardware and additional integration risk.
- Preferred delivery: before Nov 15.
- Player can be flexible on prepayment.
- Project launch: Dec 1.

### Hidden NPC state

- Target price: €112,000+.
- BATNA equivalent value: about €103,000.
- Early payment: very valuable.
- Delivery acceleration: relatively cheap.
- Cash-flow pressure: hidden.
- Future business: moderately valuable.

---

## Round 1

### Open channel

Player:

> Качество нас устраивает полностью, но предложение выходит за выделенный бюджет. Имеется ли возможность оптимизировать стоимость?

NPC:

> Определённый запас есть. При стандартных условиях можем рассмотреть около €116,000.

### Under the hood

Player did well:

- did not reveal exact budget;
- did not reveal BATNA;
- used external constraint.

Player also revealed:

- product is strongly preferred;
- price is an obstacle.

NPC makes a small test concession.

---

## Round 2

### Open channel

Player:

> У нас есть возможность предложить вам оплату части продукта авансом. Насколько это будет интересно?

NPC:

> 50% аванса позволит обсуждать около €113,000.

### Under the hood

Hidden interest discovered:

- early payment matters.

The player moved from pure price bargaining toward integrative negotiation.

---

## Round 3

### Open channel

Player:

> Мы готовы внести 50% предоплаты при условии DDP 10 ноября.

NPC:

> €113,000, 50% аванс, DDP 10 ноября выглядит реализуемо.

### Under the hood

This is a conditional trade:

```text
50% prepayment ↔ earlier delivery
```

The player revealed that Nov 10 has value, but received something concrete in exchange.

---

## Round 4

### Open channel

Player:

> Мы готовы внести 100% предоплаты за 10 единиц, чтобы завершить интеграцию, если получим их в начале ноября. Остальные приемлемо получить 20 ноября.

NPC:

> 10 единиц — 5–7 ноября, 90 — до 20 ноября. При такой структуре можем обсуждать €111,000.

### Under the hood

A concrete runtime deal structure was created:

```text
split delivery
```

The structure uses an authored delivery-schedule primitive and an authored split-delivery capability.

The extractor proposes the concrete schedule. The engine validates it.

The scenario author does not need to enumerate this exact 10/90 schedule.

The player moved from the position:

> all 100 units early

to the underlying interest:

> enough units early to reduce integration risk.

This move is intended to create a Pareto improvement. The executable utility model must verify the improvement.

---

## Round 5

### Open channel

Player:

> Мы достаточно гибки по предоплате, особенно при хорошей цене.

NPC:

> Тогда могу предложить €109,500 при сохранении согласованного графика.

### Under the hood

Positive:

- player signaled a trade direction.

Negative:

- player revealed that prepayment flexibility is cheap without first forcing the supplier to price it.

This is information leakage.

The event model first records the statement as a participant claim. The engine records a true disclosure only after it compares the claim with the participant's private authored state.

---

## Round 6

### Open channel

Player:

> Ещё хотели обсудить % Free of Charge на случай брака.

NPC:

> Обычно можем предложить 1% FOC. Для 2–3% нужно обсуждать структуру.

### Under the hood

An authored latent term became active:

```text
quality reserve / FOC
```

Again, the player moves away from pure price bargaining.

---

## Round 7

### Open channel

Player:

> Желательно иметь 3 устройства и быструю замену. После 1 декабря готовы оплатить лишние устройства, если они окажутся невостребованными.

NPC:

> Три устройства могут быть резервом до 1 декабря. Использованные при подтверждённом браке — FOC. Неиспользованные — оплачиваются.

### Under the hood

This is a contingent agreement.

The player is buying availability and risk reduction, not simply asking for free hardware.

A runtime contingent structure was created:

```text
risk allocation
```

The structure combines authored quantity, date, condition, obligation, and payment primitives.

The engine can score it only when the scenario provides capabilities and deterministic evaluation rules for this composition.

---

## Round 8

### Open channel

Player proposes:

- immediate substitution from reserve;
- failed unit returned for diagnosis;
- payment outcome depends on diagnosis.

NPC accepts the principle but asks to clarify the defect criteria.

### Under the hood

The negotiation moves into objective criteria.

The trainer should detect a boundary:

- commercial principle is in scope;
- detailed legal/RMA drafting may be out of scope.

The scenario can mark:

```text
FOC principle = agreed
RMA wording = agreed_in_principle
legal drafting = out_of_scope
```

The NPC accepts only a commercial principle in this turn. This is not formal acceptance of a complete deal.

The transcript intentionally stops before a formal terminal transition.

A complete version must materialize one offer revision and use the contextual confirmation flow in `docs/offer-session-protocol.md`.

## Protocol appendix

This appendix illustrates the accepted interaction protocol.

It assumes that a published successor to the draft scenario defines every required term and evaluation rule.

The engine has one complete active offer revision.

The preceding dialogue discussed both the RMA principle and the complete commercial package.

Participant:

> Согласен.

The context permits two meanings.

The participant may agree only with the RMA principle, or with the complete offer.

The engine does not bind an agreement.

It returns:

```text
result = clarification_required
next_actor = same participant
question = "Вы соглашаетесь только с принципом RMA или принимаете всё предложение?"
```

Participant:

> Принимаю всё предложение целиком.

The engine validates one complete active revision.

It returns `confirmation_required` and the complete materialized terms.

Participant:

> Подтверждаю полное принятие этого предложения.

The engine validates the pending revision again.

It atomically freezes the deal and enters `agreement_reached`.

---

## Training observations

Strong moves in the example:

- conditional trading;
- discovering payment importance;
- split delivery;
- moving from position to underlying interest;
- contingent agreement;
- risk allocation.

Possible weaknesses:

- revealing product preference;
- revealing payment flexibility too cheaply;
- not testing supplier BATNA;
- not explicitly testing how much earlier payment is worth;
- risk of over-negotiating once the deal is already strong.
