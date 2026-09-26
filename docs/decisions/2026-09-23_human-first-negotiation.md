# DR-31. NPC greeting before the human's first negotiation turn

Date: 2026-09-23.
Status: partially superseded by [DR-50](2026-09-26_grounded-goal-directed-dialogue.md).

DR-50 supersedes deterministic provider bypass and the prohibition on public term restatement for a new scenario version that defines `dialogue_strategy`.
This record remains authoritative for older scenario versions.

## Decision

In a training session with one human and one built-in NPC, the human MUST be `next_actor` at session creation.
This rule applies when either role owns the authored opening artifact.
The authored opening artifact MUST remain structured session state.
The built-in NPC MUST send one polite greeting before the human's first message.
The greeting MUST refer to the public scenario title in the session language.
The greeting MUST NOT state deal terms, make a concession, or give negotiation advice.
The service MUST store the greeting at `session_revision = 0`.
The service MUST record one `npc.greeting.delivered` event.
The greeting MUST NOT commit an action or change the session revision, round, substantive-turn count, active offer, or `next_actor`.
The greeting MUST use a deterministic template and MUST NOT call a dialogue provider.
A repeated create-session request MUST NOT duplicate the greeting or event.

This rule supersedes the Easy opening presentation in DR-17 and DR-18 for human-versus-built-in-NPC training sessions.
The Easy opening presentation remains available when the next participant is an external agent.
Benchmark session initialization does not change.

## Rationale

The NPC opens the conversation without starting the negotiation.
The human chooses the first live negotiation action.
The authored opening artifact remains available as scenario setup and does not become NPC prose.

## Consequences

Web, CLI, and other Player API clients receive the same stored greeting.
The first human message starts the live turn sequence.
Replay uses the stored greeting and event.
