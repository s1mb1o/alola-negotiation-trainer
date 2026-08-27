# API Sketch

The API should be player-agnostic.

The Web UI and CLI use the same API.

The MVP language is Russian. Requests and stored sessions identify the language so that later versions can add languages.

Participant identity comes from an authenticated participant context. A client must not select its actor identity in a message body.

The negotiation engine should not care whether the player is:

- human;
- external LLM;
- scripted bot;
- replay agent.

Human participants and external-agent participants use the same natural-language Player API.

The public Player API does not accept typed actions from an external agent.

---

## Create session

```http
POST /sessions
```

```json
{
  "idempotency_key": "create_01J...",
  "scenario_id": "supplier_001",
  "scenario_version": 1,
  "language": "ru",
  "participants": [
    {
      "role": "buyer",
      "controller": "human"
    },
    {
      "role": "seller",
      "controller": "built_in_npc"
    }
  ],
  "difficulty": "normal",
  "hints_enabled": true,
  "run_mode": "training"
}
```

This contract example illustrates a future published `supplier_001` version in a human-versus-built-in-NPC session.

It is not executable against the current draft file until its listed missing definitions pass publication linting.

The session model uses participants and roles. It does not encode human and NPC as fixed domain seats.

An authorized orchestrator creates agent-versus-agent sessions with two external participants.

The pinned scenario version supplies `max_rounds`.

Response:

```json
{
  "session_id": "sess_abc123",
  "revision": 0,
  "scenario_version": 1,
  "scenario_content_digest": "sha256:...",
  "scenario_compiler_version": "scenario-compiler-v1",
  "compiled_scenario_digest": "sha256:...",
  "status": "active",
  "round": 1,
  "substantive_turn_count": 0,
  "next_actor": "participant_buyer",
  "observation": {
    "role_brief": "...",
    "conversation": [],
    "active_offers": [
      {
        "offer_id": "offer_01",
        "offer_revision": 1,
        "proposer_role": "seller",
        "terms": {
          "price": 120000,
          "currency": "EUR",
          "quantity": 100,
          "payment": "net_30_after_delivery",
          "delivery_weeks": 8
        }
      }
    ],
    "assistance": null
  },
  "language": "ru"
}
```

The system issues a separate participant credential to each external controller.

The exact credential-delivery mechanism is an implementation decision. It must not expose one participant's credential to another participant.

---

## Submit message

```http
POST /sessions/{id}/messages
```

```json
{
  "message": "Мы готовы рассмотреть предоплату...",
  "idempotency_key": "cmd_01J...",
  "expected_revision": 7
}
```

The server derives the participant and role from the authenticated context.

The parser may propose an internal action, evidence, or a typed runtime term structure.

The engine validates runtime terms against the compiled scenario grammar, capabilities, constraints, and evaluation rules.

A proposal outside that grammar cannot receive an LLM-generated utility value or become binding.

The engine validates every extracted action before it changes state.

The response is role-neutral.

The response MUST include the committed post-request session revision and an actor-safe observation.

When the next participant uses the built-in NPC controller, the service runs that controller automatically.

Example successful human-versus-built-in-NPC response:

```json
{
  "result": "turn_committed",
  "round": 4,
  "substantive_turn_count": 7,
  "revision": 9,
  "status": "active",
  "next_actor": "participant_buyer",
  "committed_actions": [
    {
      "participant_id": "participant_buyer",
      "action": "counter_offer",
      "message": "Мы готовы рассмотреть предоплату...",
      "offer": {
        "offer_id": "offer_01",
        "offer_revision": 4
      },
      "offer_lifecycle": {
        "offer_id": "offer_01",
        "offer_revision": 4,
        "status": "active"
      }
    },
    {
      "participant_id": "participant_seller",
      "action": "question",
      "message": "Какую долю предоплаты вы рассматриваете?"
    }
  ],
  "observation": {}
}
```

In an external-agent-versus-external-agent session, one request commits at most one participant action.

### Clarification response

The server returns this response when the text has more than one material interpretation:

```json
{
  "result": "clarification_required",
  "revision": 8,
  "round": 4,
  "substantive_turn_count": 6,
  "status": "active",
  "next_actor": "participant_buyer",
  "clarification": {
    "reason_code": "ambiguous_agreement_scope",
    "question": "Вы соглашаетесь только с условием поставки или со всем предложением?",
    "candidate_interpretations": [
      "agree_to_delivery_term",
      "accept_complete_offer"
    ]
  },
  "observation": {}
}
```

The server records the message and ambiguity event.

It does not change the deal or consume a negotiation round.

The same participant remains `next_actor`.

The UI and external-agent runner MUST show the `clarification_required` result explicitly.

### Acceptance confirmation response

An unambiguous intent to accept a complete offer does not bind the deal immediately.

The server returns the exact materialized offer for confirmation:

```json
{
  "result": "confirmation_required",
  "revision": 10,
  "round": 4,
  "substantive_turn_count": 6,
  "status": "active",
  "next_actor": "participant_buyer",
  "pending_confirmation": {
    "offer_id": "offer_01",
    "offer_revision": 4,
    "terms": {
      "price": 109500,
      "currency": "EUR",
      "quantity": 100,
      "payment_schedule": {
        "prepayment_fraction": 0.5,
        "remaining_payment": "net_30_after_delivery"
      },
      "delivery_schedule": [
        {"quantity": 10, "date": "2026-11-07"},
        {"quantity": 90, "date": "2026-11-20"}
      ],
      "reserve_policy": {
        "quantity": 3,
        "defect_verification": "supplier_diagnostic_confirmation",
        "used_units": {
          "when_defect_confirmed": "FOC",
          "otherwise": "contract_unit_price"
        },
        "unused_units": {
          "payable_after": "2026-12-01",
          "price": "contract_unit_price"
        }
      },
      "rma_principle": "supplier_diagnostic_confirmation"
    },
    "unresolved_required_terms": []
  },
  "observation": {}
}
```

The participant confirms or cancels in natural language.

The Web UI may render buttons that submit canonical natural-language messages through this endpoint.

The engine binds the deal only after it validates a positive confirmation against the pending offer revision.

The terms in this example are illustrative. The scenario compiler must define every primitive, capability, constraint, and evaluation rule used by the package.

See `docs/offer-session-protocol.md` for all offer and transition rules.

### Conflict responses

An `expected_revision` mismatch returns HTTP `409` with `revision_conflict` and does not create an event.

An attempt to accept a superseded, withdrawn, rejected, or expired offer returns HTTP `409` with `offer_not_active`.

The server records the participant message and failed domain transition before it returns `offer_not_active`.

This response includes the post-recording session revision.

A repeated `idempotency_key` returns the stored original response, including a stored error response.

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

Difficulty and teaching mode never authorize access to raw hidden state.

When a mode exposes detected signals, the observation contains actor-safe belief projections derived from validated evidence.

The projection may contain confidence or the configured `UNKNOWN`, `PARTIAL_SIGNAL`, `PROBABLE`, and `CONFIRMED` label.

It does not expose `RealityState` or another participant's private belief state.

An active participant receives the `active_player` projection.

A completed training participant may receive the configured `training_review` projection.

A benchmark participant receives no hidden review data until the complete benchmark run set is finished.

---

## External-agent behavior

An external LLM agent gets its participant-scoped observation and submits natural-language messages.

It receives the same clarification and acceptance-confirmation flows as a human participant.

It does not submit an intent, offer object, `accept` command, or `walk_away` command directly.

The engine extracts and validates those proposed internal actions from text.

Benchmark agents receive no hints or training assistance.

---

## History

```http
GET /sessions/{id}/messages
GET /sessions/{id}/events
GET /sessions/{id}/metrics
```

Internal events are never returned directly to active participants.

Each endpoint returns a participant-safe event, metric, or review projection.

Teaching mode may release selected information only after session completion and only through the configured training-review projection.

---

## Fork session

```http
POST /sessions/{id}/fork
```

```json
{
  "idempotency_key": "fork_01J...",
  "expected_revision": 12,
  "source_revision": 7,
  "configuration_overrides": {}
}
```

Response:

```json
{
  "session_id": "sess_branch_456",
  "parent_session_id": "sess_abc123",
  "source_revision": 7
}
```

`source_revision` identifies parent state after that exact committed revision.

The branch inherits offer status, pending protocol state, delivered participant information, and run configuration at that revision.

An authorized training orchestrator may record model or policy overrides in `configuration_overrides`.

Forks support training, deliberate practice, and branch comparison.

A forked session is not eligible as an independent benchmark trial.

---

## Administrative close

```http
POST /sessions/{id}/close
```

This endpoint requires administrator authorization.

It changes a non-terminal session to `aborted`.

The request includes `idempotency_key`, `expected_revision`, and an administrative reason.

A participant ends negotiations through a natural-language `walk_away` intent on the message endpoint.

Agreement, expiry, and terminal technical failure use engine-owned transitions.

---

## Review

```http
GET /sessions/{id}/review
```

The evaluator produces a review for `agreement_reached`, `walked_away`, `expired`, `aborted`, and `technical_failure`.

Example response:

```json
{
  "outcome": {
    "agreement": true,
    "termination_reason": "agreement_reached",
    "participant_utilities": {
      "buyer": 89,
      "seller": 81
    },
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

An intentional no-ZOPA scenario can return a successful `walked_away` training outcome.

The review compares a deal with `reservation_utility`. A built-in policy accepts a deal only when every hard constraint passes and `U(deal) >= reservation_utility`.

Exact opponent utility, BATNA, reservation utility, and hidden facts are returned only when the configured post-session reveal policy permits them.

---

## Scenario endpoints

```http
POST /scenarios
GET  /scenarios/{id}
POST /scenarios/{id}/versions
GET  /scenarios/{id}/versions/{version}
```

A session pins an immutable scenario-version snapshot, source content digest, scenario compiler version, and compiled scenario digest.

The authoring lifecycle and publication freeze point remain an open decision.

Scenario create and version endpoints are author or administrator endpoints. Participants receive only scenario metadata through their observation.

A scenario version declares its language, authored world, term primitives, capabilities, composition rules, hard constraints, utility rules, expected ZOPA condition or training intent, and hidden-state reveal policy.

The source document conforms to `schemas/scenario-v1.schema.json`.

The scenario compiler creates atomic knowledge definitions and typed runtime rules.

A concrete composite term may emerge from these compiled rules.

A proposal outside the compiled grammar has no utility and cannot become binding.

See `docs/knowledge-and-emergent-state.md` for the normative model.

---

## Event streaming

Optional:

- SSE
- WebSocket

Public event examples:

```text
session.message.received
session.processing
session.participant.responded
session.clarification.required
session.confirmation.required
session.finished
```

Do not expose internal hidden-state updates over the public event stream.

---

## Benchmark runner contract

Each independent benchmark trial creates a fresh session.

Each tested agent plays both roles.

The runner repeats trials with one fixed run configuration.

The configuration pins the scenario version, language, model and provider versions, prompt versions, policy version, generation parameters, and randomness settings.

Benchmark sessions disable hints and training assistance.

The exact repetition count is a runner configuration value.

---

## Future speech adapters

STT accepts speech and returns canonical text for the standard message flow.

TTS accepts an actor-safe public message and returns audio.

Speech endpoints or client-local adapters are an implementation decision.

Audio never replaces the canonical text transcript or structured event log.
