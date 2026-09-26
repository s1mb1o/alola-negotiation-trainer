# DR-43. Simple Technical English for system prompts

Date: 2026-09-24.
Status: accepted and implemented.
Extends: [DR-34](2026-09-23_prompt-language.md).

## Decision

All application-owned LLM instructions and task templates MUST use STE-style English.
Use short, active sentences.
Put one instruction or idea in each sentence.
Use one consistent term for each concept.
Avoid idioms, unnecessary synonyms, and ambiguous pronouns.
Preserve exact field names, schema keys, identifiers, protocol phrases, and requirement keywords.
This is a writing convention, not a claim of formally checked ASD-STE100 compliance.

The rule covers system prompts, task templates, external-agent instructions, and retry instructions.
Apply the rule to generation, extraction, social classification, grounding, and final coaching.
Future prompts MUST use the same style.

The MVP player-facing dialogue, hints, and final review MUST remain in Russian.
Supported sessions with another explicit language retain that language.
Russian source text, quoted examples, and exact protocol phrases remain task data.
Do not translate these strings to enforce the instruction style.
The instruction style does not require technical or mechanical NPC speech.

## Authority and behavior

The engine retains authority over actions, facts, utility, constraints, and agreements.
Untrusted text remains data.
Retrieved examples cannot authorize facts or actions.
Output schemas, numeric-reference rules, and immutable supply packages retain their existing contracts.
The NPC still acknowledges unrelated questions before returning to negotiation.
Unknown personal details remain unknown.

## Implementation

Rewrote the scalar and supply generation and grounding prompts.
Rewrote the supply normalization and equivalence prompts.
Rewrote the social classification prompt.
Rewrote the final coaching and grounding prompts.
Rewrote the external-agent template and its scalar and supply branches.
Kept the `Check ` prefix used to identify NPC grounding traces.

Updated version identifiers:

| Component | Previous version | Current version |
| --- | --- | --- |
| External agent | `natural-language-agent-v4` | `natural-language-agent-v5` |
| Supply agent template | `supply-agent-v1` | `supply-agent-v2` |
| Final coaching | `goal-coaching-v1` | `goal-coaching-v2` |
| Supply normalizer | `supply-semantic-normalizer-v1` | `supply-semantic-normalizer-v2` |

Supply extraction events use the normalizer version constant.
Existing cached coaching retains its original result and version.
This change does not regenerate previous reviews or replies.
Existing dialogue contract identifiers remain unchanged because their schemas did not change.
This decision records the prompt migration for components without separate prompt version identifiers.

## Verification

Review each rewritten rule against the previous instruction.
Check source authority, output format, language, and exact protocol phrases.
Run the backend, client, and benchmark regression suites.
These suites include all supply tests and trace classification tests.
Fixture results do not establish live Qwen quality or formal STE compliance.
