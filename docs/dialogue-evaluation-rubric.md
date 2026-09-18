# Dialogue evaluation

This guide implements the evaluation contract in [DR-28](decisions/2026-09-06_grounded-negotiation-dialogue.md).
Dialogue diagnostics are separate from agreement rate and utility.
The evaluator does not call a provider or an external judge.

## Technical diagnostics

The Admin Inspector shows diagnostics in the session overview.
The service derives them from public messages and public delivery events.
The service does not expose private scenario state.

- `exact_repeat_count` counts repeated NPC messages after case and whitespace normalization.
- `question_repeat_count` counts repeated question segments with a question mark.
- Repetition is counted separately for each NPC participant.
- Flags contain the current message source and the earlier message source.
- The response contains at most 100 flags. Counts still include all observed repetitions.
- `fallback_rate` divides observed fallback deliveries by generation attempts with a known fallback result.
- Canonical template replies do not count as generation attempts.
- `latency_ms.average` uses recorded generation latency only.
- `latency_ms.p95` uses the nearest-rank percentile.
- Missing latency and missing fallback observations remain `null`.
- Failure counts contain allowlisted categories. They do not contain raw provider errors.

These checks cannot determine semantic repetition, relevance, or factual correctness.
A repeated question can be appropriate.
A fluent and varied answer can contain an unsupported assertion.
Source references support manual investigation.

## Public artifact

The offline CLI accepts one public Admin Inspector session detail.
It also accepts an object with a `sessions` array.
Each session requires a unique `session_id`, `participants`, `messages`, and public `events`.
The evaluator scores participants with controller `built_in_npc` or `external_agent`.
It groups results by provider, model, language, role, scenario version, difficulty, assistance, and configuration digest.
Set `prompt_version`, `seed`, `max_turns`, and `configuration_id` for comparable trials.
Participant prompt metadata takes precedence over session metadata.
The evaluator does not infer comparability from missing metadata.

Use only already-redacted public exports.
Do not provide raw database rows or private scenario files.
The scorecard export selects public message fields and public offer-event fields.
It removes credential patterns and configured process credentials from public text.
It does not copy participant tokens, private payloads, or arbitrary session fields.

```sh
.venv/bin/python -m benchmarks.dialogue_quality export-scorecard public-sessions.json
.venv/bin/python -m benchmarks.dialogue_quality analyze public-sessions.json
.venv/bin/python -m benchmarks.dialogue_quality analyze public-sessions.json --scorecard human-ratings.json
```

Commands write JSON to standard output.
Save the scorecard output as `human-ratings.json` before editing ratings.
The CLI does not overwrite input artifacts.

## Human scorecard

The rubric version is `dialogue-human-v1`.
Each evaluated reply has four dimensions.
Every dimension uses an integer from 0 to 4.
A higher value indicates fewer observed problems.
Use `null` when the public evidence is insufficient.

| Dimension | Review question |
| --- | --- |
| `relevance` | Does the reply address the current player intent? |
| `continuity` | Does the reply preserve the topic, corrections, and unresolved questions? |
| `attribution` | Does the reply distinguish a claim, proposal, quotation, and agreement? |
| `unsupported_claims` | Does the reply avoid unsupported commitments and factual assertions? |

| Rating | Anchor |
| --- | --- |
| 0 | Clear, material failure. |
| 1 | Several substantial problems. |
| 2 | Mixed or partly adequate. |
| 3 | Adequate with a minor issue. |
| 4 | No observed issue in this dimension. |

For each rated reply, enter `reviewer_id` and at least one `evidence_source_ids` reference.
Use references from the scorecard context or public offer events.
Add a short explanation in `note` when useful.
Do not edit source context, source identifiers, or the source digest.
The analyzer rejects changed sources, unknown references, duplicate ratings, and invalid ratings.
The analyzer requires all four dimension keys.
It permits a different subset of dimensions to be rated for each reply.
It reports per-dimension sample counts and reply coverage.
Unrated dimensions remain `null` in aggregates.
The API does not store human ratings in this increment.
The Inspector therefore shows those dimensions as unrated.
Completed ratings appear in the offline analysis artifact.

Human review uses public evidence only.
A score of 4 does not prove that an NPC claim matches hidden reality.
Review negotiation correctness against the deterministic state separately.
For multiple reviewers, export separate scorecards and compare their disagreements before combining conclusions.

## Regression corpus

`benchmarks/fixtures/dialogue_quality_cases.json` contains synthetic connected Russian and English dialogues.
The corpus contains numerical questions, relative proposals, short replies, corrections, deferred topics, false claims, and prompt injection.
The adversarial cases include deliberate repeated questions.
These records are evaluation fixtures, not evidence of live model quality.
The fixture scenario is a public-only example. It is not a published executable game scenario.

```sh
.venv/bin/python -m benchmarks.dialogue_quality analyze benchmarks/fixtures/dialogue_quality_cases.json
.venv/bin/python -m pytest backend/tests/test_dialogue_quality.py benchmarks/tests/test_dialogue_quality.py
```
