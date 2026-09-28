# DR-47. Relationship-aware opening greetings

Date: 2026-09-26.
Status: partially superseded by [DR-50](2026-09-26_grounded-goal-directed-dialogue.md).

DR-50 supersedes provider independence for a new scenario version that defines `dialogue_strategy`.
This record remains authoritative for scenario versions without `dialogue_strategy`.

## Context

The fixed revision-zero greeting sounds formal and repetitive.
The training setup already distinguishes `first_meeting` from `successful_history`.
The NPC must use this authored relationship without inventing historical facts.
The opening must remain replayable and independent from a model provider.

## Options

| Option | Benefit | Limitation |
| --- | --- | --- |
| Keep one greeting | Simple and fully stable | Repetitive and insensitive to relationship context |
| Generate every greeting with the dialogue model | More variation | Adds latency, provider dependence, and grounding risk before the first turn |
| Select from bounded relationship-aware templates | Natural variation with deterministic replay | Requires an authored template set |

## Decision

The revision-zero greeting MUST remain deterministic.
It MUST NOT call a model provider.

The `first_meeting` relationship MUST use the neutral greeting.
The `successful_history` relationship MUST select one greeting from a bounded authored set.
The selected greeting MUST signal prior familiarity or collaboration.
It MUST NOT invent a past term, concession, promise, event, or current agreement.

The Web UI MUST select `successful_history` by default for a new training setup.
The user MAY select `first_meeting` before session creation.
The service MUST NOT change the pinned relationship of an existing session.

The selection MUST use a stable digest of the template version, session identifier, language, public scenario title, and relationship.
The service MUST store the selected text in the raw transcript.
An idempotency replay MUST return the stored text and MUST NOT select another greeting.

Each greeting MUST use the session language.
Each greeting MUST refer to the public scenario title.
It MUST NOT state deal terms or give negotiation advice.
It MUST NOT change the session revision, round, substantive-turn count, active offer, or `next_actor`.

## Consequences

Separate sessions can start with different wording.
The same session remains stable for replay and audit.
The authored relationship affects the conversational tone before the first player message.
The greeting cannot reveal hidden state or create negotiation evidence.
Existing sessions retain their stored greeting and initial social state.
