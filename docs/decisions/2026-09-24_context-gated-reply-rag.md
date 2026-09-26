# DR-38. Context gates for retrieved few-shot replies

Date: 2026-09-24.
Status: accepted and implemented.
Extends: [DR-32](2026-09-23_retrieved-reply-examples.md).

## Decision

The service MUST retain deterministic local retrieval after NPC action selection.
An entry MAY contain up to four additional player-message patterns.
The search MAY compare bounded sentence fragments to these patterns.
The search MUST select a first reply from each matching entry before additional variants.
The search MUST deduplicate reply text and retain the four-example limit.

An entry MAY require up to two approved reason identifiers.
Every required reason MUST be approved for the current turn.
Every reply in that entry MUST contain each approved reason text verbatim.
An entry MAY require exact values of `personal_fact` or `relationship` from `training_context`.
The service MUST check these values against the existing NPC-safe projection.
Player text and shared background MUST NOT satisfy these gates.
An example MUST NOT authorize a fact or rank undisclosed interests.

The service MUST preserve exact selected examples in the durable render plan.
Old plans MUST retain their stored examples after the corpus changes.
Library version 1 MUST remain unchanged.
Library version 2 supplies the new examples.
Existing generation, grounding, and binding-action checks remain mandatory.
Internal instructions remain English. Russian examples remain task data.
The public API contract does not change.

## Options and rationale

1. Expand the existing local search. This option needs no new service or model.
2. Add embedding retrieval. This option adds a model dependency and index lifecycle.
3. Include every example in each prompt. This option adds unrelated context and token cost.

Use option 1 for the small authored corpus.
The previous corpus has eight entries and no SaaS entries.
Improve coverage before introducing embedding infrastructure.

## Verification and limits

Test context isolation, absent approvals, paraphrases, diversity, and replay.
Compare identical approved requests with and without retrieved examples.
Include generation and grounding in the provider call limit.
Store only synthetic input and safe telemetry in the experiment report.
A small comparison does not establish a general quality or latency improvement.
RAG does not repair provider outages, coaching failures, or economic policy.
