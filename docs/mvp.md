# MVP Plan

## Phase 1 — Domain skeleton

Implement:

- ScenarioVersion
- Session
- Participant
- Observation
- NegotiationState
- DealState
- NegotiationEvent
- Offer
- UtilityModel
- AssistancePolicy

Acceptance:

- scenario can be loaded;
- session can be started;
- public observation can be generated;
- events are persisted;
- state can be reconstructed.

---

## Phase 2 — Human vs NPC

Implement:

- message endpoint;
- parser/extractor;
- simple deterministic state transition;
- NPC policy;
- response generation;
- transcript.

Acceptance:

- one complete supplier scenario works end-to-end.

---

## Phase 3 — Evaluation

Implement:

- skill event detection;
- utility metrics;
- agreement result;
- BATNA comparison;
- simple Pareto efficiency approximation;
- post-session review.

---

## Phase 4 — Assistance modes

Implement:

- Guided;
- Easy;
- Normal;
- Expert;
- progressive hint API.

---

## Phase 5 — External agent

Implement generic Player API:

- get observation;
- submit action/message;
- text and structured modes.

Acceptance:

- external LLM can play the same scenario as a human.

---

## Phase 6 — Replay and branching

Implement:

- parent_session_id;
- fork_event_id;
- replay from event;
- compare branch metrics.

---

## Non-goals for first MVP

Do not initially build:

- distributed microservices;
- RL training;
- complex probabilistic beliefs;
- perfect Pareto-frontier solver;
- legal contract drafting;
- multi-party negotiation;
- voice/video sentiment analysis.
