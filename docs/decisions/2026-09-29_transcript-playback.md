# DR-54. Transcript playback through the Player API

Date: 2026-09-29.
Status: accepted at the user's request.

## Decision

The CLI MUST provide a `transcript-playback` command.
The command MUST read an external Markdown transcript.
The transcript MUST use level-three speaker headings and block quotes for messages.
The caller MUST map one speaker to the player role and one speaker to the NPC role.

The command MUST support an `exact` mode.
The `exact` mode MUST create two `scripted_bot` participants.
The command MUST submit each recorded message through the authenticated Player API.
The command MUST NOT bypass turn ownership, revision checks, parsing, validation, or terminal state.
The command MUST stop when the recorded speaker differs from `next_actor`.
The report MUST identify this result as a divergence.

The command MUST support an `npc-comparison` mode.
The `npc-comparison` mode MUST create one human player and one built-in NPC.
The command MUST submit only recorded player messages.
The command MUST retain recorded NPC messages as comparison references.
The command MUST capture the current built-in NPC messages after each player submission.

The command MAY treat one leading recorded NPC message as an opening reference.
It MUST do so only before a recorded message has been submitted.
The scenario opening state remains authoritative.
The command MUST NOT submit the leading message when the scenario already assigns the first live turn to the player.

The command MUST create a fresh training session.
It MUST disable hints.
It MUST use normal difficulty.
It MUST use the selected immutable scenario version.

The report MUST include the source turn, submitted role, revision change, command result, session status, next actor, public terms, active offers, public messages, and public events.
The report MUST exclude participant credentials and hidden state.
The report MUST include the session identifier for inspection in the Admin Session Inspector.

The command MUST support an optional final-review action.
The action MUST require `NEGOTIATION_ADMIN_TOKEN`.
The action MUST close a non-terminal playback session with an explicit source-exhausted reason.
The action MUST NOT invent acceptance or agreement.
The command MUST fetch the resulting actor-safe player review.
The command MUST support a Markdown report that shows the stored player-visible dialogue before the final review.

The command MUST return exit code 1 when playback diverges.
It MUST return exit code 0 when all applicable source turns are processed.
Argument, parse, and API setup errors MUST retain exit code 2.

## Options and rationale

1. Import transcript rows directly into SQLite.
   This option can preserve every recorded message.
   It bypasses the Player API and engine validation.
2. Submit both recorded speakers through the Player API.
   This option tests the exact recorded language against the current engine.
   It exposes turn and protocol divergence.
3. Submit only the player and regenerate NPC replies.
   This option compares current NPC behavior with the recorded NPC.
   It does not reproduce the original two-party path.

Selected options: 2 and 3.
The two modes answer different evaluation questions.
Both modes retain the Player API as the only mutation path.

## Consequences and risks

An exact playback can stop before the end of the file.
This result is evidence of a protocol difference.
It is not a transport failure.

A recorded terminal courtesy message can remain unsubmitted after the engine reaches a terminal state.
The report identifies this difference.

An NPC comparison depends on the configured NPC renderer.
Template mode is deterministic.
A provider-backed renderer can produce different wording.

The Markdown parser supports the documented transcript structure only.
It does not implement a general Markdown abstract syntax tree.

## Acceptance

Automated tests MUST verify speaker extraction and paragraph preservation.
Automated tests MUST verify exact two-party submission.
Automated tests MUST verify turn divergence.
Automated tests MUST verify player-only submission and recorded NPC comparison.
Automated tests MUST verify that reports do not contain participant credentials.
Automated tests MUST verify explicit finalization and actor-safe review rendering.
