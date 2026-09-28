# DR-48. Bounded dialogue rewind and player-side reply assistance

Date: 2026-09-26.
Status: accepted and implemented.

## Context

A learner needs to retry a reply before the training session ends.
The selected point must restore the exact committed state after an NPC message.
The learner also needs an explicit action that asks a model to write the next player message.

The service already stores immutable decision checkpoints.
The existing training fork is available only after session completion.
Its usage count is not limited.

## Decision

### Dialogue rewind

The service MUST implement rewind as a new child session.
It MUST NOT delete or rewrite the source session.

The source revision MUST identify both an immutable training checkpoint and a stored built-in-NPC message.
The child MUST restore the session row, structured state, offers, transcript, and public and private events from that checkpoint.
The child MUST exclude later state and history.
The child MUST receive fresh participant credentials.

The root training lineage MUST permit at most three rewind operations.
The service MUST store usage outside checkpoint snapshots.
Every rewind child MUST retain the same root lineage identifier.
Rewind from any descendant MUST use the same root usage count.
An idempotency replay MUST NOT consume another attempt.
When no attempt remains, the service MUST reject every new rewind in that lineage.

The owner observation MUST include the limit, used count, remaining count, and eligible source revisions.
The Web UI MUST show a rewind action only on an eligible earlier NPC message.
The Web UI MUST disable rewind when the remaining count is zero.

### Player-side reply assistance

The service MUST provide an explicit player-side reply assistance operation.
The operation MUST be available only to the owner of an active human training session.
It MUST require the current player turn and the exact current revision.

The provider input MUST contain only the authenticated player projection.
It MAY contain the player's private preparation.
It MUST NOT contain hidden NPC state, private scenario bounds, credentials, raw internal events, or another participant's private data.

Application-owned instructions MUST use STE-style English.
The generated player message MUST use the session language.
The provider MUST return one bounded JSON message.
The service MUST reject malformed, credential-bearing, executable, or binding-control output.
Binding-control output includes final acceptance confirmation, final offer publication confirmation, and walk-away commands.

The assistance operation MUST NOT change negotiation state.
The Web UI MAY submit the validated message through the normal Player message operation after the learner selects **Ответь за меня**.
The normal parser and engine MUST remain authoritative for the submitted message.
Provider failure or validation failure MUST leave session state unchanged.

The live route MUST use the configured review provider for player-side assistance.
The current live route therefore uses `Qwen3.8-Max`.
The call MUST appear in the LLM diagnostics journal as `player_assist`.
Benchmark sessions MUST NOT use player-side assistance.

## Consequences

Rewind feels like dialogue rollback in the Web UI while preserving immutable audit history.
The durable lineage counter prevents a learner from recovering spent attempts through another rewind.
The model can write a player reply but cannot bypass the Player API or deterministic transition rules.
