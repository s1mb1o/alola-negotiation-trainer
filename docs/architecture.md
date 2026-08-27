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
                         │                   │
                         │             Scenario Compiler
                         │                   │
                         ▼
                  Negotiation Engine
                  ├─ Reality State
                  ├─ Deal State
                  ├─ Belief State
                  ├─ Evidence Validator
                  ├─ Term DSL Validator
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

The Web UI and CLI are required MVP clients.

The Web UI is the hackathon demonstration client.

The CLI supports operation, tests, scripted agents, and benchmark runs.

STT and TTS are optional boundary adapters. STT converts speech to canonical text before parsing. TTS converts an actor-safe public message to audio after generation.

The canonical transcript remains text. The canonical history remains the structured event log.

The MVP conversation language is Russian. Scenario, session, prompt, and rendering contracts carry language metadata so that later versions can add languages without changing domain identifiers.

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
User speech, when present
  ↓
Optional STT
  ↓
Participant text
  ↓
Extract proposed internal action, evidence, and typed term structures
  ↓
Validate against compiled knowledge definitions and term grammar
  ↓
Validate command and expected session revision
  ↓
Meaning ambiguous? ── yes ──→ Persist message and ambiguity
  │                              ↓
  │                         Return clarification_required
  no
  ↓
Apply deterministic evidence and belief updates
  ↓
Evaluate constraints and utility
  ↓
Atomically commit the authoritative action event and session revision
  ↓
Session active and next_actor uses built_in_npc? ── no ──→ Return turn result
  │
  yes
  ↓
Generate legal NPC action candidates
  ↓
Optional future fuzzy ranking of legal candidates
  ↓
Engine selection and validation
  ↓
Atomically commit the NPC intent event and session revision
  ↓
Natural-language response from actor-safe intent and public context
  ↓
Persist the delivered public message
  ↓
Optional TTS
```

An LLM failure must not roll back an already committed participant action or create a duplicate turn. The processing worker must resume from the last committed session revision.

---

## Action and language-model boundary

### Parser / Extractor

Input:

- participant message;
- actor-safe visible context;
- pending actor-safe protocol context.

Output:

- proposed internal action;
- proposed claims and evidence;
- proposed typed runtime term structures;
- ambiguities;
- source spans;
- possible negotiation-skill signals.

The parser output is untrusted.

The engine validates proposed evidence against compiled knowledge definitions.

The engine validates proposed runtime terms against the compiled term grammar and authored rules.

The parser may propose an internal action, evidence record, or typed runtime term structure.

The parser cannot create ground truth, a primitive type, utility function, hard constraint, authoritative belief update, agreement, or terminal transition.

Human participants and external-agent participants use this same natural-language flow.

The public Player API does not provide typed action submission to an external agent.

### NPC action policy

Input:

- structured state;
- deterministic utility calculations;
- allowed actions;
- disclosure rules.

The engine generates legal action candidates from this input.

The engine selects and validates the authoritative NPC action.

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

The dialogue generator receives the approved `action`, approved public `offer`, approved `disclosure`, and tone. It does not receive `must_not_disclose`, raw hidden facts, reservation utility, or counterparty-private state.

### Future fuzzy policy ranker

A later policy implementation may use an LLM to rank legal action candidates.

The ranker is advisory.

The ranker cannot create a candidate, add a primitive or semantic rule, authorize a disclosure, override a hard constraint, or accept below reservation utility.

The engine remains the final selector and validator.

### Dialogue generator

Turns structured NPC intent into realistic natural language.

The generator receives only actor-safe public context and approved structured intent.

The generated message must preserve all approved facts, numbers, and terms.

Rule:

> Policy decides WHAT. LLM decides HOW TO SAY IT.

---

## Session state

A session may contain:

```json
{
  "id": "sess_abc123",
  "session_revision": 15,
  "parent_session_id": null,
  "source_revision": null,
  "scenario_id": "supplier_001",
  "scenario_version": 1,
  "compiled_scenario_digest": "sha256:...",
  "scenario_compiler_version": "scenario-compiler-v1",
  "language": "ru",
  "round": 8,
  "substantive_turn_count": 15,
  "round_opener": "buyer",
  "status": "active",
  "next_actor": "buyer",
  "reveal_policy": "active_player",
  "active_offers": [],
  "active_offer_sets": [],
  "pending_clarification": null,
  "pending_acceptance_confirmation": null,
  "candidate_deal": {
    "runtime_terms": []
  },
  "reality_state": {},
  "revealed_by_participant": {
    "buyer": {},
    "seller": {}
  },
  "belief_state_by_participant": {
    "buyer": {},
    "seller": {}
  },
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

PARTICIPANT_ACTION:
  conditional_offer

STATE_EFFECT:
  evidence_validated:
    interest.buyer.delivery.importance
  belief_updated:
    observer=seller confidence=0.10->0.52
  true_disclosure_checked:
    result=matching_permitted_disclosure
  runtime_term_validated:
    type=delivery_schedule
  offer_lifecycle:
    revision_2=active->superseded
    revision_3=null->active

UTILITY:
  buyer  76 -> 84
  seller 74 -> 79
```

This enables replay, analytics, and branching.

Also store the exact observation, assistance, hint, distractor, and public message delivered to each participant.

Each delivery record identifies the participant, language, reveal policy, and source event.

State reconstruction never invokes an LLM.

The event log stores validated evidence, belief updates, runtime term trees, and utility results.

Replay reapplies these validated transitions.

---

## Event sourcing

Recommended from the beginning.

Example:

```text
Event 1: SELLER_OFFER
Event 2: BUYER_PROBE
Event 3: SELLER_CONCESSION
Event 4: BUYER_PROBE
Event 5: SELLER_REVEAL
Event 6: BUYER_CONDITIONAL_OFFER
```

Current state can be reconstructed from events or accelerated with snapshots.

---

## Branching

Store:

```text
parent_session_id
source_revision
```

`source_revision` identifies state after the exact committed parent revision.

The child inherits offer status, `next_actor`, pending clarification, pending acceptance confirmation, delivered information, and run configuration at that revision.

The child preserves inherited offer IDs and revisions.

The child starts at `session_revision = source_revision`.

Its first child-local event uses `source_revision + 1`.

An authorized training orchestrator may override model or policy configuration in the child.

The child records each override.

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

An authored latent term may become available when its authored activation condition occurs.

A participant may create a concrete composite term at runtime.

The composite must use compiled term primitives and authored capabilities, constraints, composition rules, and evaluation rules.

Examples include a split-delivery schedule and a contingent reserve policy.

A valid composite is a runtime term instance. It can affect utility without being enumerated as a complete package in the scenario file.

A proposal outside the compiled term grammar is an `unscored_proposal`.

The NPC may clarify, discuss, or decline an `unscored_proposal`.

An `unscored_proposal` cannot affect deal validity or utility. It cannot become part of a binding agreement.

See `docs/knowledge-and-emergent-state.md` for the normative state model.

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

Completeness should encourage closing but must not force a participant to accept a deal below reservation utility.

The authoritative acceptance threshold is `reservation_utility`.

An acceptable deal must satisfy every hard constraint and `U(deal) >= reservation_utility` for each accepting participant controlled by the built-in policy.

A human or external agent may accept a deal below its own reservation utility when every hard constraint passes.

The post-game review should identify that failure.

A scenario may intentionally have no ZOPA. A rational walk-away is a successful training outcome for such a scenario.

Every formal offer revision is immutable and contains a complete materialized package.

An ordinary counteroffer supersedes its referenced revision.

Several active alternatives require an explicit MESO offer set.

Binding acceptance by a human or external-agent participant requires a context-aware acceptance intent and a separate confirmation of one complete active offer revision.

A built-in NPC uses one typed engine-confirmed acceptance transition after deterministic validation.

Text such as `согласен` cannot bind an agreement when the context can refer to one condition or an agreement in principle.

The engine returns `clarification_required` for ambiguous meaning.

The terminal states are `agreement_reached`, `walked_away`, `expired`, `aborted`, and `technical_failure`.

See `docs/offer-session-protocol.md` for the normative state machine.

---

## Provider abstraction

The LLM gateway should support multiple providers without leaking provider-specific logic into the domain engine.

Possible providers:

- OpenAI
- Anthropic
- local models
- custom HTTP inference

Keep model/provider/version/temperature/seed metadata for reproducibility.

Also keep language, scenario digest, prompt versions, policy version, engine version, assistance configuration, and reveal policy.

---

## Hidden-state release

An active participant receives only an actor-safe projection.

A completed training session may receive selected hidden information when the scenario review policy permits it.

The review records each released item and its training purpose.

A benchmark trial keeps hidden information sealed until the complete run set is finished.

Author and administrator access uses a separate privileged projection.

---

## Benchmark execution

Each independent benchmark trial uses a fresh session.

Each tested agent plays both roles.

The runner repeats trials under one fixed run configuration.

The run configuration pins the scenario version and digest, language, model and provider versions, prompts, policy, generation parameters, and randomness settings.

Benchmark trials disable hints and training assistance.

Forked sessions support training and branch comparison. They are not independent benchmark trials.
