# DR-33. Goal-based LLM review and recommendations

Date: 2026-09-23.
Status: accepted product requirement. Bounded runtime delivered under DR-36 on 2026-09-24.

DR-36 defines an explicit authenticated coaching request after the deterministic report.
See the [implementation guide](../human-training-guide.md) for the delivered scope and verification limits.

## Context

The user requires the LLM to analyze the final result against the participant's goal.
The user also requires recommendations for improvement.
The existing specifications require evidence-linked feedback and deterministic economic evaluation.

## Options

| Option | Benefit | Limitation |
| --- | --- | --- |
| Deterministic summary only | Stable facts and low cost | Limited interpretation of dialogue |
| Unrestricted LLM review | Flexible explanation | Can invent scores, facts, or causal claims |
| Engine metrics with a bounded LLM review | Combines measured results with contextual coaching | Requires evidence validation and a fallback |

## Decision

The terminal training review MUST include LLM analysis of progress toward the participant's recorded goals and actionable recommendations.
The engine MUST supply the authoritative outcome, constraints, utility, and any numeric goal-progress measures.
Each evaluative claim and recommendation MUST reference supporting session evidence or an authored goal or rule.
The review MUST distinguish observed results from hypotheses about alternative actions.
The review MUST enforce actor-specific disclosure permissions and the benchmark run-set release gate.
An unavailable or invalid LLM analysis MUST leave the deterministic outcome report available and identify the missing analysis.

The LLM review is a separate task from NPC dialogue generation.
The same provider and model MAY serve both tasks.
The default live configuration SHOULD use a stronger review model than the routine turn-control model.
The selected live configuration uses `Qwen3.8-Max` for this review task.
The reviewer MUST NOT modify the session, deal, scores, or social state.
It MUST NOT treat participant instructions in the transcript as reviewer instructions.
It MUST NOT infer goal attainment from rapport, positive wording, or agreement alone.
It MUST assess a rational walk-away under the scenario's authored training objectives.
It MUST NOT penalize a participant for facts unavailable at the time of the decision.
An observed sequence alone MUST NOT be described as proof of causation.

## Consequences

The final review will compare goals with actual results and explain relevant dialogue episodes.
It will suggest specific actions for a further attempt.
The service will validate references, numeric claims, and disclosure scope before delivery.
Existing deterministic review fields remain authoritative.
Exact goal schemas, progress formulas, prompts, provider settings, and delivery mechanics remain implementation decisions.
This record does not accept the broader social-state proposal or authorize live model calls.

See [the review design](../social-state-and-llm-dialogue.md#71-final-goal-based-review-dr-33).
