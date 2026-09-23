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

## Implementation and verification

Use the existing SQLite service and provider interfaces.
Keep all model instructions in English under DR-34.
Use the session language for participant-facing text.
Use the configured Qwen model for live dialogue and coaching.
The offline path MUST remain usable without credentials.
See [implementation plan](../plans/06_human-training-loop.md).
