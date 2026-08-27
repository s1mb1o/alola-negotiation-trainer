# Negotiation Trainer

Headless negotiation simulation and training engine with API-first architecture.

The hackathon product uses a Web UI for the demonstration and includes a CLI for operation, testing, and agent runs.

The MVP language is Russian. The structured domain model and API allow additional languages later.

STT and TTS are desirable extensions. Text and structured events remain the canonical inputs and history.

The system models negotiations as a stateful process. The MVP supports two parties. The architecture may support more parties later.

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

Human participants and external-agent participants use the same natural-language interaction contract.

The LLM is **not** the source of truth for the scenario. The source of truth is a structured negotiation state. The engine selects and validates NPC actions. LLMs are used for natural-language parsing, response generation, evaluation, and optional future ranking of engine-approved actions.

A concrete deal structure may emerge at runtime from authored primitives, capabilities, and evaluation rules.

A proposal outside the compiled scenario grammar does not receive an LLM-generated utility value and cannot become binding.

Accepted dated decision records are authoritative. The core specifications must be synchronized with each accepted decision.

## Core pipeline

```text
Player
  ↓
Public Observation
  ↓
Player Speech, when present
  ↓
Optional STT Adapter
  ↓
Player Message
  ↓
Parser / Extractor
  ├─ Proposed Internal Action
  ├─ Proposed Evidence
  └─ Proposed Typed Deal Structure
  ↓
Negotiation Engine
  ├─ Deal State
  ├─ Belief State
  ├─ Utility
  ├─ Constraints
  ├─ Scope
  └─ Assistance Policy
  ↓
Legal NPC Actions
  ↓
Engine Selection + Validation
  └─ Optional Future Fuzzy LLM Ranker
  ↓
Natural Language Generator
  ↓
Optional TTS Adapter
  ↓
Transcript + Event Store
  ↓
Evaluator / Review
```

The NPC branch runs only while the session is active and `next_actor` uses the `built_in_npc` controller.

An external-agent-versus-external-agent request commits one participant action and returns `next_actor`.

## Clients

The core product is a service with an API.

- Web UI — required hackathon demonstration client
- CLI — required operational, testing, and agent client
- External LLM player
- Scripted bot
- Replay bot
- Benchmark / tournament runner
- Mobile app — future client

## Suggested MVP

1. Modular monolith backend.
2. REST API + optional SSE/WebSocket events.
3. Scenario definitions in YAML/JSON.
4. Persistent sessions and event log.
5. One human-vs-NPC mode.
6. Agent-vs-agent benchmark runner in text mode.
7. Web UI for the demonstration.
8. CLI for operation, tests, and agent runs.
9. Simple weighted/piecewise utility functions and hard constraints.
10. Guided / Easy / Normal / Expert assistance modes.
11. Post-session review.
12. Session forking / replay from an exact committed revision.
13. Russian dialogue with language-extensible scenarios and APIs.
14. Optional STT/TTS adapters when the core text flow is stable.

Independent benchmark trials use fresh sessions. Each tested agent plays both roles. Trials are repeated with a fixed configuration. Hints and training assistance are disabled.

An intentional no-ZOPA scenario is valid. It can evaluate a correct walk-away decision.

The current `examples/scenario_supplier_001.yaml` file is a draft specification example. It is not a publishable or executable scenario until the `missing_required_definitions` list is empty.

The offer protocol uses immutable materialized revisions. Human and external-agent acceptance uses contextual intent and separate confirmation. A built-in NPC uses one typed engine-confirmed transition. The engine returns `clarification_required` when text such as `согласен` does not identify complete acceptance.

The scenario defines ground truth, term primitives, capabilities, constraints, and evaluation rules. The session may create validated composite deal structures and participant hypotheses at runtime.

See `docs/architecture.md`, `docs/negotiation-model.md`, `docs/knowledge-and-emergent-state.md`, `docs/offer-session-protocol.md`, `docs/example-session.md`, `schemas/scenario-v1.schema.json`, `schemas/negotiation-event-v1.schema.json`, `docs/decisions/2026-08-27_post-review-decisions.md`, and `SMOKE_TESTS.md`.
