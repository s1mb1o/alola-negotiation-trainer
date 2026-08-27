# Architecture

## High-level architecture

The product is a headless service with API clients.

```text
                    ┌────────────── Web UI
                    ├────────────── Mobile app
                    ├────────────── CLI
                    ├────────────── External LLM agent
                    ├────────────── Scripted bot
                    └────────────── Benchmark runner
                                   │
                                   ▼
                         Negotiation Service API
                                   │
                         ┌─────────┴─────────┐
                         ▼                   ▼
                   Session Manager     Scenario Service
                         │
                         ▼
                  Negotiation Engine
                  ├─ Deal State
                  ├─ Belief State
                  ├─ Utility
                  ├─ Constraints
                  ├─ Scope
                  └─ Assistance Policy
                         │
                         ▼
                     NPC Policy
                         │
                         ▼
                     LLM Gateway
                         │
                         ▼
                Transcript + Event Store
                         │
                         ▼
                Evaluator / Analytics
```

---

## Modular monolith for MVP

Do not begin with microservices.

Suggested module layout:

```text
negotiation-service/
├── api/
├── sessions/
├── scenarios/
├── engine/
├── agents/
├── llm/
├── evaluator/
├── storage/
└── analytics/
```

Later, heavy components can be extracted if necessary.

---

## Core processing pipeline

```text
User text
  ↓
Structured action extraction
  ↓
State transition
  ↓
Constraint / utility evaluation
  ↓
NPC decision
  ↓
Natural-language response
  ↓
Persist transcript + events
```

---

## LLM responsibilities

### Parser / Extractor

Input:

- player message;
- visible context;
- selected state information.

Output:

- speech acts;
- proposed deal changes;
- revealed information;
- questions;
- ambiguities;
- possible negotiation skills.

### NPC policy assistant

Input:

- structured state;
- deterministic utility calculations;
- allowed actions;
- disclosure rules.

Output:

- structured NPC intent.

Example:

```json
{
  "action": "counter_offer",
  "offer": {
    "price": 111000
  },
  "disclosure": [
    "delivery_flexibility"
  ],
  "must_not_disclose": [
    "cashflow_pressure",
    "reservation_price"
  ],
  "tone": "constructive"
}
```

### Dialogue generator

Turns structured NPC intent into realistic natural language.

Rule:

> Policy decides WHAT. LLM decides HOW TO SAY IT.

---

## Session state

A session may contain:

```json
{
  "id": "sess_abc123",
  "scenario_id": "supplier_001",
  "scenario_version": 1,
  "round": 8,
  "status": "active",
  "candidate_deal": {},
  "player_revealed": {},
  "npc_revealed": {},
  "belief_state": {},
  "rapport": 0.74,
  "agreement_status": {}
}
```

---

## History

Store both:

### Raw transcript

Human-readable conversation.

### Structured event log

Example:

```text
ROUND 5

PLAYER_MOVE:
  conditional_offer

STATE_EFFECT:
  revealed_delivery_interest
  created_split_delivery_dimension

UTILITY:
  player 76 -> 84
  npc    74 -> 79
```

This enables replay, analytics, and branching.

---

## Event sourcing

Recommended from the beginning.

Example:

```text
Event 1: NPC_OFFER
Event 2: PLAYER_PROBE
Event 3: NPC_CONCESSION
Event 4: PLAYER_PROBE
Event 5: NPC_REVEAL
Event 6: PLAYER_CONDITIONAL_OFFER
```

Current state can be reconstructed from events or accelerated with snapshots.

---

## Branching

Store:

```text
parent_session_id
fork_event_id
```

This enables:

- retry from a weak move;
- compare two strategies;
- decision tree visualization;
- educational replay.

---

## Scope handling

A scenario defines which topics are negotiable and at what depth.

Example:

```yaml
scope:
  price:
    depth: full
  payment:
    depth: full
  delivery:
    depth: full
  warranty:
    depth: medium
  rma:
    depth: principle_only
  governing_law:
    depth: excluded
```

If the user dives into out-of-scope legal drafting, the NPC should acknowledge and move back to agreed commercial principles.

---

## Agreement completeness

Track required and optional dimensions.

Example:

```text
price            agreed
quantity         agreed
delivery         agreed
payment          agreed
FOC              agreed
RMA principle    agreed_in_principle
```

Completeness should encourage closing but must not force the player to accept a deal worse than BATNA.

A bad deal may be completed and accepted. The post-game review should identify that failure.

---

## Provider abstraction

The LLM gateway should support multiple providers without leaking provider-specific logic into the domain engine.

Possible providers:

- OpenAI
- Anthropic
- local models
- custom HTTP inference

Keep model/provider/version/temperature/seed metadata for reproducibility.
