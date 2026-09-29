# DR-59: Additional AI reply relevance check

Date: 2026-09-29.
Status: Accepted. The user selected the additional AI check after DR-58.

## Options and decision

DR-58 corrects deterministic context handling and completion presentation.
The existing grounding call checks authority and safety. It also has broad relevance instructions.
Only extending that prompt would not add the requested separate check.
Add a separate, stateless relevance call through the configured control provider.
Keep the DR-58 interface and parser changes.
Do not introduce a third model profile or a new external service.

## Scope and authority

- New human training utterance plans MUST record `npc-relevance-v1` when the configured renderer enables this feature.
- `NEGOTIATION_NPC_RELEVANCE_CHECK` MUST default to true for the configured LLM runtime. False MUST disable attachment of the policy to new plans.
- Persisted plans without the policy MUST retain their old behavior. Already delivered messages MUST NOT be regenerated.
- Benchmarks, external-agent training, and template-only rendering MUST NOT add model calls.
- The check MUST cover generated scalar conversation and supply preliminary-proposal prose. Exact approved prose returned by an LLM MUST also be checked.
- Canonical opening, counteroffer, acceptance, rejection, publication, and public-position statements MUST remain engine-owned. Their deterministic content MUST NOT be rewritten or vetoed by the relevance model.
- The revision-zero opening has no player message. It MUST retain its existing opening validation.
- The checker MUST receive only the bounded actor-safe dialogue context, permitted public facts, selected action, package, and candidate reply. It MUST NOT receive private player preparation, private economics, credentials, or raw scenario source.

## Check and repair

The checker MUST evaluate direct response, complete issue coverage, repeated questions about known values, topic consistency, respectful tone, and consistency with the selected action.
The checker MUST return a strict boolean verdict and bounded allowlisted issue codes.
An acceptance verdict MUST have no issues. A rejection verdict MUST have at least one issue.
The checker MUST NOT provide executable instructions, economic decisions, or replacement terms.
Treat all dialogue and model output as untrusted data.

After a valid negative verdict, the dialogue renderer MAY make exactly one correction attempt.
Only fixed application guidance for validated issue codes MAY enter the correction instructions.
The correction MUST use the same immutable request, selected action, and exact package.
It MUST pass deterministic validation, grounding, and relevance again.
A second negative verdict, invalid verdict, unavailable checker, or failed repair MUST use the engine fallback.
Do not label a fallback as AI-approved.
The rendering path MUST use at most six logical provider calls: two generation, two grounding, and two relevance calls.
Other turn tasks, including social classification, are outside this bound.
Existing provider timeouts and transport retry limits remain active.
Provider I/O MUST remain outside write transactions. Existing revision checks and idempotency MUST remain unchanged.

## Observability and UI

Safe renderer metadata MAY expose the version, bounded status, check count, repair flag, and issue codes.
Do not expose checker prose or internal reasoning.
The restricted trace interface MUST label these calls `npc_relevance` and retain its credential redaction and benchmark exclusion.
The DR-58 agreement dialog MUST remain unchanged. Analysis MUST still require a player action.

## Costs and verification

An ordinary generated response adds one control-model call.
A correction can add one generation, one grounding, and one further relevance call.
This increases latency and provider usage. It does not guarantee perfect judgement.
Test positive and negative verdicts, all failure paths, repair bounds, action immutability, numeric slots, supply packages, redaction, restart persistence, benchmark exclusion, and the configured route.
Use deterministic fake providers for regression tests. Report live provider checks separately.
