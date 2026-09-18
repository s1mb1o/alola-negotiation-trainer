# DR-28. Grounded negotiation dialogue

Date: 2026-09-06.
Status: accepted for implementation through the user's request `реализуй все`.

## Decision

Implement contextual intent, conditional exchanges, public numeric references, richer authored motives, difficulty-specific dialogue, and separate dialogue evaluation.
Options considered: prompt-only changes, a deterministic grounded pipeline, and an unrestricted LLM negotiator.
Use the deterministic grounded pipeline.
Prompt-only changes do not fix numeric questions that become offers.
An unrestricted negotiator conflicts with structured-state authority.
This decision extends DR-26 and DR-27.
It supersedes the unconditional numeric-output ban only for validated public quote slots.

## Contextual input

The parser MUST distinguish questions, quoted positions, proposals, relative changes, and short answers before committing numeric terms.
A question or quotation MUST NOT become an offer merely because it contains numbers.
A mixed message MAY propose an explicitly scoped clause and ask a separate question.
A relative change MUST resolve against one active public offer revision and the scenario currency.
An ambiguous reference, unsupported calculation, or missing baseline MUST request clarification without changing offer terms.
A short numeric answer MAY use one unambiguous public term focus or one engine-authored requested term.
The parser MUST NOT derive agreement or the requested term from generated NPC prose.
The service MUST obtain parse context from the authenticated session after revision and turn checks.
Separate complete-offer acceptance confirmation remains required.

## Conditional exchange policy

New immutable scenario versions MAY define bounded candidate values for existing authored terms.
The compiler MUST validate those values against the term grammar and bound the candidate search.
The engine MUST evaluate complete packages before selection.
Each selected package MUST pass every role's hard constraints and the NPC reservation utility.
The policy MUST use only NPC utility, public proposals, and authored rules to select an exchange.
It MUST NOT optimize against counterpart private utility or expose private limits.
The policy SHOULD prefer a feasible monetary concession in return for a nonmonetary term with demonstrable NPC utility benefit.
An incomplete offer MUST remain incomplete during ordinary discussion.
The policy MUST NOT silently complete an omitted opening term.
Previous public monetary concessions MUST NOT be reversed by later counteroffers.
If no supported exchange exists, use a validated fallback or reject without inventing terms.
The exchange explanation MUST refer only to the selected public package.

## Numeric references

The renderer MAY use bounded engine-authored quote slots for active public offer terms.
Each slot MUST identify offer ID, offer revision, proposing role, term, value, currency, and exact attributed display text.
The LLM MUST select a slot identifier instead of writing a numeric value.
Unknown, altered, repeated, or unbound slot identifiers MUST be rejected.
The service MUST substitute exact engine text and validate the final reply.
An existing value MUST NOT authorize a new commitment, waiver, calculation, or agreement.
Novel wording still requires the grounding check.
Canonical financial actions remain deterministic.
Slots MUST be stored in the durable render plan and tied to its revision.
Historical plans without slots MUST remain readable.

## Motives and difficulty

Publish new scenario versions for richer authored reasons and candidate values.
Existing versions MUST remain unchanged.
Each reason MUST be supported by that role's authored context or objective.
An explanation MUST NOT invent a capability or change utility independently of authored rules.
Each role MAY define an allowlisted stable conversation style.
The service MUST map difficulty to a bounded public conversation profile.
Guided and easy profiles SHOULD help clarify terms and take conversational initiative.
Normal and expert profiles SHOULD request justification and reciprocal concessions without abusive behavior.
Difficulty MUST NOT change hidden truth, utility, hard constraints, or reservation thresholds.
Benchmarks MUST retain normal difficulty and disabled assistance.

## Dialogue evaluation

Dialogue quality MUST remain separate from utility and agreement rate.
The Admin Inspector SHOULD expose actor-safe technical dialogue diagnostics.
Diagnostics MUST use public transcript, public renderer events, and bounded telemetry only.
Diagnostics MUST distinguish exact repetition, question repetition, latency, fallback rate, and categorized validation failures.
Missing telemetry MUST remain unavailable rather than zero.
Heuristic flags MUST NOT be presented as proof of relevance or factual correctness.
The offline evaluator MUST support source-attributed human scorecards and model-independent comparisons.
Unrated dimensions MUST remain unrated.
The dataset MUST contain connected Russian and English cases, numerical questions, relative changes, short replies, corrections, repetition, and false claims.
No new paid model trial or external reviewer is authorized by this implementation decision.

## Verification and consequences

Tests MUST cover parsing safety, conditional tradeoffs, difficulty profiles, unchanged economic truth, slot injection, restart, concurrency, historical plans, privacy, and missing evaluation data.
New UI diagnostics MUST support Russian, English, dark, and light presentation.
All existing authority, privacy, confirmation, replay, and durable-render rules remain required.
This increment does not implement arbitrary deal-schema generation or the full belief engine.
New scenario versions and policy can change benchmark results. Comparisons MUST pin scenario versions and configuration.
