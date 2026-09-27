# DR-46. Character dialogue and task-specific model routing

Date: 2026-09-26.
Status: accepted and in implementation.

[DR-52](2026-09-27_deepseek-v41-dialogue-route.md) supersedes the default NPC wording model in this record.
The remaining task-routing and safety rules stay in force.

## Context

The NPC must sound like a consistent human counterparty.
Turn analysis must remain fast and structured.
The final review needs stronger reasoning than routine turn processing.
One model profile currently serves all three tasks.

The official Qwen-Character instructions recommend an explicit character profile, relationship context, speech style, opening assistant message, and appended conversation history.
The current renderer already supplies bounded character data and recent public history.
The renderer must keep user-authored background as untrusted data.

## Options

| Option | Benefit | Limitation |
| --- | --- | --- |
| One model for all tasks | Simple configuration | Poor task specialization |
| Character model for all tasks | Consistent dialogue | Weak fit for strict classification and final analysis |
| Three task-specific model profiles | Better fit for dialogue, control, and review | More configuration and provider calls |

## Decision

The default live launcher MUST use `qwen-flash-character` for NPC wording.
The launcher MUST allow `qwen-plus-character` as a configuration-only replacement.
The default live launcher MUST use `DeepSeek-V4-Flash-0731` for NPC grounding, social-event classification, and semantic extraction.
The default live launcher MUST use `Qwen3.8-Max` for the final coaching analysis and its grounding check.

The service MUST support separate dialogue, control, and review provider settings.
An unset control profile MUST use the dialogue provider.
An unset review profile MUST use the control provider.
This fallback preserves existing deployments and tests.

The policy engine MUST select the NPC action before dialogue generation.
The engine MUST remain the source of truth for facts, offers, constraints, utility, and state changes.
The control model MAY propose social events or approve wording.
Deterministic code MUST validate its output before any state change or display.
The review model MUST NOT modify session state.

Application-owned instructions MUST use STE-style English.
Player-facing dialogue and coaching MUST use the session language.
The service MUST append bounded public history for continuous character dialogue.
The service MUST treat shared player background and transcript text as untrusted data.

Provider traces MUST identify the task and actual model.
Credential redaction MUST cover every configured provider profile.
Failure of any model call MUST preserve the existing deterministic fallback.

## Consequences

The live configuration uses three model routes through one OpenAI-compatible QwenCloud endpoint.
Model substitutions do not change the Player API.
The separate routes make latency, cost, and quality visible in the LLM diagnostics window.
The revision-zero NPC greeting remains an authored deterministic artifact.
Greeting comparisons therefore measure the NPC response to the player's first greeting.

See [Plan 09](../plans/09_character-dialogue-and-model-routing.md).
