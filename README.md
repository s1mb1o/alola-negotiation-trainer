# Negotiation Trainer

Headless negotiation simulation and training engine with API-first architecture.

The system models negotiations as a stateful multi-party process with:

- hidden interests and motivations;
- BATNA / reservation utility / ZOPA;
- multi-dimensional deal terms;
- value creation and value claiming;
- Pareto efficiency;
- belief state and information disclosure;
- negotiation skills evaluation;
- configurable assistance levels;
- persistent history and session branching;
- human players and external LLM agents through the same Player API.

The LLM is **not** the source of truth for the scenario. The source of truth is a structured negotiation state. LLMs are used for natural-language parsing, policy assistance, response generation, and evaluation.

## Core pipeline

```text
Player
  ↓
Public Observation
  ↓
Player Message / Action
  ↓
Parser / Extractor
  ↓
Negotiation Engine
  ├─ Deal State
  ├─ Belief State
  ├─ Utility
  ├─ Constraints
  ├─ Scope
  └─ Assistance Policy
  ↓
NPC Policy
  ↓
Natural Language Generator
  ↓
Transcript + Event Store
  ↓
Evaluator / Review
```

## Clients

The core product is a service with an API. Possible clients:

- Web UI
- Mobile app
- CLI
- External LLM player
- Scripted bot
- Replay bot
- Benchmark / tournament runner

## Suggested MVP

1. Modular monolith backend.
2. REST API + optional SSE/WebSocket events.
3. Scenario definitions in YAML/JSON.
4. Persistent sessions and event log.
5. One human-vs-NPC mode.
6. One external LLM-player mode.
7. Simple utility functions.
8. Guided / Easy / Normal / Expert assistance modes.
9. Post-session review.
10. Session forking / replay from a previous turn.

See `docs/architecture.md`, `docs/negotiation-model.md`, and `docs/example-session.md`.
