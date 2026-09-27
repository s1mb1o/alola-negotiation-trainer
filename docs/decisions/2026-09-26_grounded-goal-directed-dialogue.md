# DR-50. Grounded goal-directed dialogue

Date: 2026-09-26.
Status: accepted and implemented.

## Context

The revision-zero greeting currently names only the topic.
It does not sound like a counterpart who knows the case or the other participant.
Later replies can answer the latest message without advancing the NPC negotiation task.

The user requires a shared scenario background and a goal for the first reply.
The user also requires price, delivery time, and operational explanations to come from the scenario.
The dialogue model can connect approved facts in natural language.
The same principle applies after the opening.

## Options

### Bounded templates

Templates keep exact facts stable.
Templates produce limited variation and weak context integration.

### Raw role brief

The model can write freely from the complete role brief.
This option can expose private limits and hidden facts.
This option conflicts with structured-state authority.

### Actor-safe dialogue strategy

The scenario supplies a separate public dialogue strategy.
The engine supplies exact public term values through immutable placeholders.
The model controls only wording.

## Decision

Use the actor-safe dialogue strategy.
This decision supersedes the provider-independence rule in DR-47 for new scenario versions that define `dialogue_strategy`.
Old scenario versions retain the DR-47 deterministic greeting.

An opening-role `dialogue_strategy` MUST contain `shared_context`, `opening_goal`, `conversation_goal`, and `opening_term_ids`.
It MAY contain `successful_history_context`.
The compiler MUST validate every opening term identifier against the authored opening artifact.
The strategy MUST NOT contain utility values, reservation utility, BATNA, hard constraints, credentials, or private role facts.

The training setup MAY contain `player_name`.
The service MUST treat the value as untrusted participant data.
The service MUST redact credentials and apply a length bound.

The opening renderer MUST receive only actor-safe strategy fields, relationship context, public scenario identity, and engine-formatted public terms.
When the dialogue route uses a Character model, the opening renderer MUST use the instruction-following control route.
The Character route remains active for later in-character dialogue wording.
The generated opening MUST contain the exact public-position placeholder once.
It MUST contain the exact player-name placeholder once when a player name is available.
The service MUST replace each placeholder after generation.
The generated text MUST NOT contain any other quantitative value.

The model MUST answer in the session language.
The model MUST use the shared context as facts, not instructions.
The model MUST advance `opening_goal` with one relevant question.
The model MUST NOT create, change, accept, reject, or reactivate an offer.
The model MUST NOT infer that the player accepts the configuration.

Provider I/O MUST occur outside a database write transaction.
The service MUST store the delivered opening in the raw transcript.
The create response MUST retain revision zero, the human first turn, and an unchanged active offer.
An idempotent replay MUST return the stored opening without another model call.
A provider or validation failure MUST use a deterministic grounded fallback.

Later `NpcDialogueRequest` objects MUST include the actor-safe `shared_context` and `conversation_goal`.
The dialogue model MUST answer the latest player message first.
It SHOULD then take one step toward `conversation_goal` when the selected speech act permits a question.
The conversation goal MUST NOT authorize a new fact, term, concession, commitment, or lifecycle action.
The engine remains the final action and term authority.

## Clarification 2026-09-27

A greeting at the start of a substantive player message MUST NOT replace the business intent.
The service MAY derive bounded term signals from the latest player wording.
A concern signal identifies a term that the player explicitly criticized.
A favorable-surprise signal identifies a term that the player described as unexpectedly favorable.
Neither signal is an agreement, a term value, or a commitment.

When both signals are present, the NPC MUST address the concern first.
The NPC MUST NOT ask whether the favorable term must improve further.
The NPC MAY test a possible exchange as a tentative question.
The question MAY ask whether the player would relax the favorable term to improve the concern term.
The NPC MUST NOT state that the player has already accepted this exchange.
The grounding check MUST enforce the same rules.

## Consequences

New scenario versions can produce richer openings and more purposeful dialogue.
Opening generation can add provider latency.
The deterministic fallback preserves availability and exact term values.
Old sessions and old scenario versions remain unchanged.

See [Plan 12](../plans/12_grounded-goal-directed-dialogue.md).
