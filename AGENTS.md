# AGENTS.md

## Project purpose

Build an API-first negotiation trainer and simulation engine.

The system should support both training humans and benchmarking negotiation agents. A player may be a human, external LLM, scripted bot, or replay agent.

## Specification authority

A dated decision record is authoritative for an accepted decision.

The affected core specifications MUST contain the same normative rule.

Update the decision record and the affected core specifications in the same change.

If a core specification conflicts with a newer accepted decision, the decision record takes precedence until the core specification is corrected.

## Architectural principles

1. **Structured state is the source of truth.**
   Do not let an LLM freely decide deal validity, hidden facts, BATNA, reservation utility, utility values, or hard constraints.
   A proposal outside the compiled scenario grammar MUST NOT receive an LLM-generated utility value.

2. **Policy decides WHAT; LLM decides HOW TO SAY IT.**
   The engine MUST select and validate the NPC action before natural-language generation.
   A future fuzzy LLM policy MAY rank actions that the engine has already classified as legal.
   The engine remains the final authority for action selection.

3. **Never expose hidden state through the Player API.**
   Observations must be derived from:
   `Observation = f(SessionState, Actor, Difficulty)`.
   Active players MUST receive only actor-safe projections.
   A completed training session MAY reveal selected hidden information through an explicit review policy.
   A benchmark run MUST keep hidden information unavailable until the complete benchmark run set is finished.

4. **Keep history on two levels.**
   - raw transcript;
   - structured event log.

5. **Design for replay and branching from day one.**
   Each session may have:
   - `parent_session_id`;
   - `source_revision`.

6. **Use immutable scenario versions.**
   A session is always attached to a specific scenario version.

7. **Separate negotiation quality from language quality.**
   A grammatically elegant player can negotiate badly, and vice versa.

8. **Support scope boundaries.**
   A commercial negotiation should not automatically become a legal drafting simulator.

9. **MVP first.**
   Prefer a modular monolith and simple piecewise utility functions before complex game-theoretic or RL components.

10. **Use Russian for the MVP.**
    Keep structured state independent of natural language.
    Scenario and session contracts MUST allow additional languages later.

11. **Support the required MVP clients.**
    The Web UI is the hackathon demonstration client.
    The CLI is a required operational and testing client.
    STT and TTS are desirable extensions and MUST remain outside the source-of-truth path.

12. **Make benchmark runs comparable.**
    Use fresh sessions for independent benchmark trials.
    Run each tested agent in both roles.
    Repeat trials with a fixed scenario version and fixed run configuration.
    Disable hints and training assistance for benchmark trials.

13. **Use the same Player API for humans and external agents.**
    Human and external-agent participants MUST submit natural-language messages.
    The parser proposes a typed internal action.
    The engine validates and commits the action.
    Context-free text such as `согласен` MUST NOT bind an agreement.
    Binding acceptance by a human or external-agent participant MUST use a separate confirmation of one complete offer revision.

14. **Separate authored reality from emergent session state.**
    Ground truth MUST be authored or deterministically derived from authored rules.
    An extractor MAY propose evidence or a typed runtime term.
    The belief engine MUST update participant confidence with versioned deterministic rules.
    A runtime deal structure MAY combine authored primitives and capabilities.
    An ungrounded participant hypothesis MUST remain a belief and MUST NOT become truth.

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
- Evidence
- KnowledgeItem
- NegotiationEvent
- Offer
- OfferSet
- RuntimeTerm
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

The scenario MUST define the truth model, term primitives, capabilities, constraints, composition rules, and evaluation rules that the MVP scenario needs.

The scenario compiler MAY create atomic knowledge items from authored domain entities.

A concrete composite deal structure MAY emerge at runtime when every primitive and evaluation rule is authored.

A proposal outside the compiled grammar MAY be discussed. It MUST NOT affect utility or become part of a binding agreement.

Use `reservation_utility` as the authoritative threshold for economic acceptability and built-in policy acceptance.

A deal is acceptable only when all hard constraints pass and `U(deal) >= reservation_utility`.

A human or external-agent participant MAY bind a deal below its own reservation utility when all hard constraints pass. The review MUST identify the economic failure.

BATNA utility is an input to reservation utility. A scenario MAY define a justified difference between them.

A scenario MAY intentionally contain no ZOPA. The scenario MUST declare this training intent. The linter MUST report ZOPA status and MUST NOT reject an intentional no-ZOPA scenario.
