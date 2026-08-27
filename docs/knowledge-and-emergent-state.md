# Knowledge and Emergent State Model

## Status

This document is normative.

Alexander Shmelev accepted this model on 2026-08-27.

## Core rule

The scenario defines the possible ground truth and the rules that can derive new ground truth.

The session can create new beliefs and new deal structures at runtime.

An LLM does not create ground truth.

An LLM does not update authoritative belief confidence directly.

An LLM does not create utility semantics.

## State layers

The session state contains two major layers:

```text
Authored world
  +
Runtime emergent world
  =
Session state
```

### Authored world

The scenario author defines:

- ground-truth facts;
- interests;
- constraints;
- BATNA inputs;
- capabilities;
- term primitives;
- composition rules;
- deterministic utility rules;
- deterministic truth-derivation rules;
- discoverability rules;
- disclosure rules.

The scenario MAY define a higher-level domain entity instead of every atomic tracking item.

Example entities include an external offer, an interest, a delivery capability, or a reserve policy.

### Runtime emergent world

The session can create:

- evidence records;
- participant beliefs;
- participant hypotheses;
- concrete term instances;
- composite deal structures;
- conditional and contingent structures.

Runtime state MUST remain inside the compiled scenario grammar and validation rules when it affects utility or deal validity.

## Scenario compiler

The scenario compiler expands the scenario DSL into validated runtime definitions.

The compiler can create atomic knowledge-item definitions from higher-level entities.

Example:

```yaml
alternatives:
  seller_batna:
    type: external_offer
    details:
      salary: 325000
      title: senior_engineer
```

The compiler can create these atomic definitions:

```text
alternative.seller_batna.exists
alternative.seller_batna.salary
alternative.seller_batna.title
```

The compiler output is versioned.

A session pins the compiler version and compiled scenario digest.

The compiler MUST NOT use an LLM to invent truth, constraints, utility, or capabilities.

## Knowledge-item definition

An atomic knowledge-item definition contains:

- stable `knowledge_item_id`;
- subject;
- predicate;
- value schema;
- truth source;
- knowledge owner;
- discoverability rule;
- disclosure rule;
- verification rule, when applicable;
- sensitivity classification.

The truth source is one of:

- an authored value;
- a deterministic derivation from authored rules;
- an authored runtime event rule.

A participant claim is not a truth source.

## Reality state

`RealityState` contains the authoritative values that exist in the scenario world.

Each value references its authored or derived source.

A runtime event can change reality only when an authored rule permits the change.

An emergent participant hypothesis MUST NOT create or change `RealityState`.

## Evidence model

The extractor reads a participant message and emits proposed evidence.

Example:

```json
{
  "knowledge_item_id": "interest.seller.title_importance",
  "signal": "positive",
  "strength": 0.45,
  "source_span": "моя роль давно стала шире",
  "source_event_id": "evt_001"
}
```

Extractor output is untrusted.

The engine validates:

- the knowledge-item identifier;
- the observer and subject;
- the evidence source;
- the signal vocabulary;
- the numeric range;
- the actor-safe visibility rule.

The extractor MUST NOT write `BeliefState`.

The extractor MUST NOT classify a participant claim as ground truth.

## Emergent hypothesis proposal

The extractor uses `proposed_hypothesis` when a message introduces a predicate that has no compiled knowledge-item definition.

Example:

```json
{
  "subject": "seller",
  "predicate": "production_capacity_problem",
  "signal": "positive",
  "strength": 0.35,
  "source_span": "возможно, у них проблема с производственной линией",
  "source_event_id": "evt_004"
}
```

The engine derives the observer participant from authenticated context and dialogue direction.

The hypothesis validator checks:

- the subject reference;
- the predicate syntax;
- the evidence source event;
- the source span;
- the signal vocabulary;
- the numeric range;
- collision with compiled knowledge items;
- actor-safe visibility.

If the predicate matches a compiled knowledge item, the engine routes the proposal through the normal evidence flow.

Otherwise, the engine creates a stable runtime `hypothesis_id` with `grounded_in_scenario: false`.

The belief engine assigns initial confidence through the same deterministic and versioned update policy used for other evidence.

The extractor does not assign authoritative initial confidence.

Later evidence can reference the runtime `hypothesis_id`.

## Belief state

Each participant has a separate `BeliefState`.

One belief entry contains:

- observer participant ID;
- subject;
- predicate or knowledge-item ID;
- confidence;
- evidence event IDs;
- provenance;
- last update revision;
- `grounded_in_scenario`;
- optional verification status.

The belief engine updates confidence with a deterministic and versioned update policy.

The update policy receives validated evidence.

The belief update policy does not receive raw hidden truth.

Truth comparison belongs to a separate disclosure or evaluator path.

The event log records the confidence before and after each update.

Confidence is the stored value.

Labels such as `UNKNOWN`, `PARTIAL_SIGNAL`, `PROBABLE`, and `CONFIRMED` are derived views.

The label thresholds are versioned configuration.

The UI does not write a belief label or confidence value.

`CONFIRMED` describes the observer's evidence state.

It does not replace `RealityState`.

## Claims and true disclosures

A direct statement creates a claim event first.

The belief engine can use the claim as evidence for the observer.

The engine separately determines whether the statement matches an authored or derived truth.

Only a matching and permitted disclosure can become a true-disclosure event.

The observer can believe a bluff.

Such a belief does not change reality.

## Emergent hypotheses

A participant can form a hypothesis that does not match a compiled knowledge-item definition.

Example stored result after a deterministic belief update:

```json
{
  "type": "participant_hypothesis",
  "observer_participant_id": "buyer",
  "subject": "seller",
  "predicate": "production_capacity_problem",
  "confidence": 0.28,
  "evidence_event_ids": ["evt_004"],
  "grounded_in_scenario": false
}
```

The extractor does not supply this authoritative confidence value.

The session MAY store this hypothesis in the participant belief graph.

The hypothesis MUST NOT become ground truth.

The hypothesis MUST NOT change utility, constraints, or deal validity.

The participant and NPC can discuss or test the hypothesis.

The review can evaluate hypothesis-testing behavior.

## Emergent deal structures

A participant can propose a concrete structure that was not enumerated as a complete term in the scenario file.

Examples include:

- a split-delivery schedule;
- a staged payment schedule;
- a contingent reserve policy;
- an option;
- a service-level condition.

The extractor maps the proposal to a typed abstract syntax tree.

The tree uses compiled term primitives.

Example:

```json
{
  "type": "delivery_schedule",
  "entries": [
    {"quantity": 10, "date": "2026-11-07"},
    {"quantity": 90, "date": "2026-11-20"}
  ]
}
```

The engine validates the tree against:

- the compiled type grammar;
- authored capabilities;
- authored hard constraints;
- authored composition rules;
- authored utility rules.

A valid tree becomes a runtime term instance.

The runtime instance can affect utility when the compiled rules define its effect.

The scenario author does not need to enumerate each valid concrete schedule or package.

## Unauthored semantics

A runtime composite built from authored primitives and authored rules is not an unauthored term.

A proposal has unauthored semantics when the compiled scenario cannot type, validate, or evaluate it.

An LLM MUST NOT estimate utility for such a proposal.

The engine marks it as `unscored_proposal` or requests clarification.

An `unscored_proposal` can be discussed.

It cannot become part of a binding agreement.

A later immutable scenario version MAY add the required primitive or rule.

## Controlled DSL primitives

The MVP DSL SHOULD use a small set of versioned primitives.

Candidate primitives include:

- numeric value;
- money;
- date;
- quantity;
- percentage;
- schedule;
- condition;
- contingency;
- obligation;
- option;
- penalty;
- service level.

The exact v1 primitive set belongs in the scenario schema.

The runtime MUST NOT mutate the schema or create an arbitrary new primitive.

## Responsibility matrix

| Component | Responsibility |
| --- | --- |
| Scenario author | Defines entities, truth, capabilities, constraints, primitives, and rules. |
| Scenario compiler | Produces atomic knowledge definitions and typed runtime rules. |
| LLM extractor | Proposes evidence and typed term structures from text. |
| Belief engine | Updates participant confidence from validated evidence. |
| Deal engine | Validates and materializes runtime term structures. |
| NPC policy | Selects actions from its actor-safe beliefs and legal actions. |
| UI and coaching | Derives labels and explanations from actor-safe confidence and evidence. |
| Evaluator | Uses event evidence and authorized truth projections for review. |

## Replay requirements

Replay MUST NOT invoke the extractor or an LLM.

The event log stores:

- extractor evidence output;
- extractor hypothesis proposals;
- evidence validation result;
- hypothesis validation and creation result;
- belief update policy version;
- confidence before and after;
- runtime term abstract syntax tree;
- term validation result;
- utility and constraint results;
- source message event IDs.

Replay applies the recorded validated transitions.
