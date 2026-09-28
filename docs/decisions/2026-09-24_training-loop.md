# DR-36. Bounded human training loop

Date: 2026-09-24.
Status: accepted for implementation by the user's plan, implement, and commit request.

## Contract

An optional `training` configuration enables the new loop for one human and one built-in NPC.
Existing sessions and benchmark contracts remain compatible.
Benchmark creation MUST reject learner-specific preparation and training assistance.
The configuration MUST pin profile, shared background, private preparation, and rule versions.
The private preparation MUST be visible only to its owner and that owner's authorized final reviewer.
It MUST NOT enter NPC context or the public Inspector.

The initial relationship is `first_meeting` or `successful_history`.
Profiles are `concise_skeptical` and `sociable`.
Bounded custom background describes shared context. It has no instruction or economic authority.
The preparation contains a target, unacceptable result, possible exchanges, information to discover, and optional typed scalar-term targets.
Typed targets MUST use finite values and scenario-supported numeric terms.
Incomplete or unaccepted terms MUST NOT count as achieved targets.
Free-text objectives MUST NOT receive invented completion percentages.

Social state uses `rapport`, `credibility`, `tension`, and `patience`, each bounded to 0–100.
These are simulation parameters, not psychological scores.
Baseline values and event deltas MUST have a version.
The LLM MAY propose bounded event classifications with exact supporting excerpts.
The engine MUST validate the event schema and references before applying changes once.
Classification failure MUST leave social state unchanged.
Repeated rapport events MUST have a cumulative cap.
Social changes MUST NOT override hard constraints, economic acceptability, or confirmation rules.

The final LLM review MUST use the actor-safe deterministic report, private preparation, and source-linked evidence.
The report MUST remain available if generation or validation fails.
The review task MUST run outside a database write transaction.
It MUST NOT modify scores, facts, or negotiated terms.
Validated review results MUST be stored with model, prompt, and source-revision metadata.
Only explicit authorized requests may initiate model-backed coaching.
An active session or sealed benchmark MUST NOT initiate a coaching request.

The service MUST capture immutable checkpoints before human decisions.
Retry MUST create a child session with fresh credentials and the exact selected committed state.
It MUST preserve the scenario, preparation, relationship, social state, and profile.
It MUST NOT copy parent credentials, idempotency responses, or later history.
Historical sessions without a checkpoint MUST report that retry is unavailable.
Benchmark sessions MUST NOT fork into training practice.
The comparison MUST report observed outcomes for the same role and identify the shared initial conditions.
It MUST label retries after feedback as informed practice.

## Accepted amendment: recoverable training controls

Date: 2026-09-27.
Status: accepted and implemented by the user's 2026-09-28 implementation request.

The service MUST pin `training-clarification-v1` for each new training session.
A parser clarification MUST NOT terminate a session that uses this rule version.
A failed participant transition with an HTTP 4xx response MUST NOT consume the protocol-control termination allowance.
Opening or cancelling an acceptance confirmation MUST NOT consume this allowance.
These rules apply only to training mode.
The bounded protocol-control rule MUST remain active in benchmark mode.

After three consecutive clarifications, the response MUST include an actor-safe recovery object.
The recovery object MUST contain the rule version, one supported message example, and one canonical session-end message.
The example SHOULD identify unresolved terms when the parser supplies them.
The session MUST remain active.
The participant MUST remain the next actor.
The recovery object MUST NOT change offer state, utility, or turn counters.
The authenticated session projection MUST retain the recovery object while the clarification is pending.
This rule MUST remain true after a service restart.

The rule applies to new sessions.
It does not reopen a terminal historical session.

## Implementation and verification

Use the existing SQLite service and provider interfaces.
Keep all model instructions in English under DR-34.
Use the session language for participant-facing text.
Use the configured Qwen model for live dialogue and coaching.
The offline path MUST remain usable without credentials.
See [implementation plan](../plans/06_human-training-loop.md).
