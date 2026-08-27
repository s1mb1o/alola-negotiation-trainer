# API Sketch

The API should be player-agnostic.

The negotiation engine should not care whether the player is:

- human;
- external LLM;
- scripted bot;
- replay agent.

---

## Create session

```http
POST /sessions
```

```json
{
  "scenario_id": "supplier_001",
  "scenario_version": 1,
  "player_role": "buyer",
  "player_type": "human",
  "difficulty": "normal"
}
```

Response:

```json
{
  "session_id": "sess_abc123",
  "status": "active",
  "observation": {
    "role_brief": "...",
    "conversation": [],
    "current_public_terms": null,
    "assistance": null
  }
}
```

---

## Submit message

```http
POST /sessions/{id}/messages
```

```json
{
  "actor": "player",
  "message": "Мы готовы рассмотреть предоплату..."
}
```

Response:

```json
{
  "turn": 4,
  "status": "active",
  "npc_message": "Да, для нас это интересно...",
  "public_state": {}
}
```

---

## Get observation

```http
GET /sessions/{id}/observation
```

The returned observation is actor- and difficulty-specific.

Conceptually:

```text
Observation = f(SessionState, Actor, Difficulty)
```

Never return hidden state through this endpoint.

---

## Agent API

External LLM agents may work in text mode or structured mode.

### Text mode

Agent receives public observation and returns natural language.

### Structured mode

Agent may return:

```json
{
  "message": "Если мы увеличим аванс...",
  "intent": "conditional_offer",
  "offer": {
    "prepayment": 0.7,
    "price": 108000
  }
}
```

Structured metadata must still be validated.

---

## History

```http
GET /sessions/{id}/messages
GET /sessions/{id}/events
GET /sessions/{id}/metrics
```

Internal events should not be exposed to active players unless the difficulty/teaching mode explicitly allows it.

---

## Fork session

```http
POST /sessions/{id}/fork
```

```json
{
  "fork_event_id": "evt_123"
}
```

Response:

```json
{
  "session_id": "sess_branch_456",
  "parent_session_id": "sess_abc123",
  "fork_event_id": "evt_123"
}
```

---

## Finish session

```http
POST /sessions/{id}/close
```

---

## Review

```http
GET /sessions/{id}/review
```

Example response:

```json
{
  "outcome": {
    "agreement": true,
    "player_utility": 89,
    "npc_utility": 81,
    "pareto_efficiency": 0.93
  },
  "skills": {
    "probing": 0.72,
    "conditional_trading": 0.91,
    "value_creation": 0.88,
    "information_leakage": 0.34
  },
  "key_moments": []
}
```

---

## Scenario endpoints

```http
POST /scenarios
GET  /scenarios/{id}
POST /scenarios/{id}/versions
GET  /scenarios/{id}/versions/{version}
```

Scenario versions should be immutable once used by a session.

---

## Event streaming

Optional:

- SSE
- WebSocket

Public event examples:

```text
session.message.received
session.processing
session.npc.responded
session.finished
```

Do not expose internal hidden-state updates over the public event stream.
