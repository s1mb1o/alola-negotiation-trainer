# AGENTS.md

## Project purpose

Build an API-first negotiation trainer and simulation engine.

The system should support both training humans and benchmarking negotiation agents. A player may be a human, external LLM, scripted bot, or replay agent.

## Architectural principles

1. **Structured state is the source of truth.**
   Do not let an LLM freely decide deal validity, hidden facts, BATNA, or hard constraints.

2. **Policy decides WHAT; LLM decides HOW TO SAY IT.**
   NPC policy should generate structured intent before natural-language generation.

3. **Never expose hidden state through the Player API.**
   Observations must be derived from:
   `Observation = f(SessionState, Actor, Difficulty)`.

4. **Keep history on two levels.**
   - raw transcript;
   - structured event log.

5. **Design for replay and branching from day one.**
   Each session may have:
   - `parent_session_id`;
   - `fork_event_id`.

6. **Use immutable scenario versions.**
   A session is always attached to a specific scenario version.

7. **Separate negotiation quality from language quality.**
   A grammatically elegant player can negotiate badly, and vice versa.

8. **Support scope boundaries.**
   A commercial negotiation should not automatically become a legal drafting simulator.

9. **MVP first.**
   Prefer a modular monolith and simple piecewise utility functions before complex game-theoretic or RL components.

## Core domain concepts

- Scenario
- ScenarioVersion
- RoleBrief
- Session
- Participant
- Observation
- NegotiationState
- DealState
- BeliefState
- NegotiationEvent
- Offer
- Constraint
- UtilityModel
- AssistancePolicy
- NPCPolicy
- Evaluator
- SessionReview

## Negotiation concepts

- BATNA
- Reservation utility
- ZOPA
- Interests vs positions
- Pareto improvement
- Pareto frontier
- Value creation
- Value claiming
- Information discovery
- Information leakage
- Conditional trading
- Package offers
- MESO
- Contingent agreements
- Objective criteria
- Exploration vs exploitation

## Initial implementation direction

Recommended stack is intentionally unspecified. Choose a simple backend stack with:

- typed request/response models;
- relational persistence;
- JSON fields where domain flexibility is useful;
- deterministic state transitions;
- clean provider abstraction for LLMs;
- testable domain logic independent of HTTP.

## Important MVP rule

Do not over-engineer the utility model. Begin with weighted/piecewise utilities and hard constraints. The architecture should allow richer utility models later.
