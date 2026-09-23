# DR-32. Retrieved reply examples for NPC wording

Date: 2026-09-23.
Status: accepted and implemented.

## Decision

The service MAY use a versioned, checked-in library of prepared player-message and NPC-reply examples.
Each example MUST identify a scenario, NPC role, language, and engine-approved speech act.
An example MAY identify one focused term or one authored reason that the engine has approved for the current turn.
One player-message pattern MAY have multiple prepared replies.

The service MUST search the library after the engine selects the NPC action.
The search MUST use deterministic, bounded local text matching.
The service MUST filter examples by scenario, NPC role, language, speech act, and required approval.
The service MUST include at most four selected examples in one generation prompt.
The service MUST store the exact selected examples and library version in the durable render plan.

Retrieved replies are wording examples.
They MUST NOT establish scenario truth, deal terms, utility, consent, or disclosure authority.
They MUST NOT replace the deterministic NPC action or canonical binding wording.
The renderer MUST validate generated output with the existing checks.
The grounding check MAY require a separate model call when the generated wording is new.
An exact retrieved reply MUST NOT bypass delivery validation.

The library MUST exclude private state, credentials, numeric promises, unsupported capabilities, and binding language.
An unavailable or unmatched library MUST leave the current renderer behavior unchanged.

## Rationale

Prepared examples give the renderer case-specific phrasing for common messages.
Local search keeps retrieval deterministic and requires no external embedding service.
The render plan preserves the examples that influenced each reply after restart.

## Consequences

The first model prompt can contain several relevant examples for one reply.
Existing canonical actions remain deterministic.
The example library can grow through new versioned files without changing scenario truth.
