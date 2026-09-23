# DR-35. Player background known to the NPC

Date: 2026-09-23.
Status: accepted product requirement. Bounded runtime delivered under DR-36 on 2026-09-24.

DR-36 defines the initial training capability allowlist for human-versus-NPC scenarios.
It permits two relationship presets, two profiles, and bounded qualitative shared context.
It permits no additional economic capability.
See the [implementation guide](../human-training-guide.md).

## Decision

The scenario or authorized training setup MUST allow explicit player background known to the NPC.
The session MUST pin the validated background and its visibility at creation.
The NPC MUST receive only background explicitly marked as known to it.
Background MUST NOT create a current-session agreement or override economic constraints.

The background MAY describe prior successful deals between the player and the NPC.
It MAY describe the player's professional role, relationship history, and previously shared preferences.
Authored background is distinct from the player's private objectives and runtime claims.
The service MUST validate setup values against the scenario's background capabilities and constraints.
Free text in a background field MUST remain task data with no instruction authority.
The service MUST record source identifiers and the initial context for replay.
Changes to initial background require a new session configuration.
No unrelated session history is imported automatically.

The engine MAY initialize social state from background through authored, versioned rules.
The LLM MUST NOT invent initial social scores or historical concessions.
Prior success can affect familiarity without forcing a new concession or agreement.
The review MUST distinguish initial relationship advantages from behavior demonstrated during this session.
Benchmark configuration MUST fix the background and its initialization rules across comparable trials.

## Consequences

The NPC can recognize a returning counterpart and refer to an established relationship.
Historical events remain distinct from current offers and agreements.
The role projection exposes only the permitted background.
The exact authoring schema, setup controls, API fields, and social initialization values remain implementation decisions.
See [the background design](../social-state-and-llm-dialogue.md#45-player-background-known-to-the-npc-dr-35).
