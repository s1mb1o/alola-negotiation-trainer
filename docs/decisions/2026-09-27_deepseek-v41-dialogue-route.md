# DR-52. DeepSeek V4.1 Flash dialogue route

Date: 2026-09-27.
Status: accepted and implemented.

## Context

The live dialogue review used `qwen-flash-character` for seven eligible NPC replies.
The wording guard accepted two replies.
The guard rejected five replies and used the safe fallback.
The rejected replies contained unsupported causes, terms, names, amounts, or commitments.
The fallback replies were safe but less natural.

Alibaba Cloud lists `deepseek-v4.1-flash` as a current recommended DeepSeek model.
The QwenCloud Chat Completions API supports multi-turn input and structured output for this model.
A live Singapore endpoint check returned the exact requested readiness response with thinking disabled.

## Decision

The default live launcher MUST use `deepseek-v4.1-flash` for NPC wording.
The launcher MUST disable thinking for NPC wording.
The launcher MUST use a 30-second NPC timeout unless the operator supplies an override.

The control route MUST continue to use `deepseek-v4-flash-0731` with thinking disabled.
The review route MUST continue to use `qwen3.8-max` with thinking disabled.

The policy engine MUST select the NPC action before wording generation.
The engine MUST remain the source of truth for facts, offers, constraints, utility, and state changes.
The wording guard MUST validate generated dialogue.
An unsafe, invalid, empty, failed, or late response MUST use the deterministic fallback.

This change MUST NOT modify the Player API, scenario truth, or negotiation state.
An operator MAY select `qwen-flash-character` or `qwen-plus-character` through configuration.

This record supersedes only the default NPC wording model in [DR-46](2026-09-26_character-dialogue-and-model-routing.md).

## Consequences

The default NPC wording route no longer uses a Character model.
The service keeps the same system prompt, bounded history, action plan, wording guard, and fallback.
A four-session check accepted all seven eligible generated replies without fallback.
The equivalent earlier check accepted two of seven `qwen-flash-character` replies.
The measured NPC generation latency was 5.18 through 24.99 seconds.
The sample does not establish production latency or a general model ranking.

## Evidence

- [Alibaba Cloud recommended models](https://www.alibabacloud.com/help/en/model-studio/models)
- [Alibaba Cloud DeepSeek API](https://www.alibabacloud.com/help/en/model-studio/deepseek-api)
- [Dialogue correctness review](../reports/2026-09-27-dialogue-correctness-review.md)
- [DeepSeek V4.1 Flash dialogue check](../reports/2026-09-27-deepseek-v41-dialogue-check.md)
