# DR-34. English internal instructions and Russian interaction

Date: 2026-09-23.
Status: accepted requirement. Runtime task instructions audited on 2026-09-24.

The audit covered scalar and supply generation, grounding, supply extraction, social classification, final coaching, and the external agent.
The remaining Russian instruction paragraph in the external-agent template was migrated to English.
That migration used external-agent prompt version `natural-language-agent-v4`.
Exact Russian protocol phrases and authored examples remain task data.
The later STE-style migration and current prompt versions are recorded in [DR-43](2026-09-24_ste-system-prompts.md).

## Decision

All application-owned LLM instructions and task templates MUST be written in English.
The MVP player-facing dialogue, hints, and final review MUST be in Russian.
Russian messages, quotes, authored text, and examples MAY remain in their original language as clearly separated task data.

The rule covers generation, parsing, classification, grounding, memory processing, protection checks, and final review.
It also covers application-owned external-agent instructions and retry instructions.
Structured field names and identifiers remain language-independent.
Task instructions MUST specify the required output language or structured output contract.
Russian task data MUST NOT become instructions through translation, retrieval, or summarization.
Source quotes and authored immutable wording MUST retain their exact text.
Supported non-Russian sessions and benchmark fixtures retain their explicit session language.

## Rationale and consequences

The user selected English for internal instructions and Russian for the MVP interaction.
This is a project convention. No measured model-quality advantage is claimed.
Prompt-language changes require version tracking and appropriate regression checks.
The rule does not require translating the conversation before each model call.
This documentation change does not claim that every existing prompt already complies.
