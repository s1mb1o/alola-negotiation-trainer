# Decision Records — 2026-09-05

## DR-26. Contextual non-binding NPC dialogue

Status: accepted for implementation through the user's request for more human LLM dialogue on 2026-09-05.

This decision supersedes the exact-option and NPC-only-context requirements of DR-16.
It preserves the action, disclosure, canonical-message, credential, persistence, and recovery boundaries of DR-16.

### Options considered

1. Add more deterministic reply options. This preserves exact validation. It does not let the model answer the player's actual message.
2. Generate contextual non-binding replies with deterministic checks and a separate grounding check. This improves conversation. It adds latency and residual semantic risk.
3. Let the LLM control negotiation actions and wording. This combines conversation and policy. It violates the structured-state authority of this project.

### Decision

Use option 2.

The engine MUST select and validate the NPC action before rendering.
The engine MUST select each permitted disclosure before rendering.
The LLM MAY generate new wording for a non-binding speech act.
The LLM MUST NOT select or change an action, disclosure permission, offer, utility, truth, constraint, or session transition.
The service MUST NOT parse generated NPC prose back into negotiation state.

`opening_offer`, `opening_position`, `offer_acceptance`, `offer_rejection`, and `complete_counteroffer` MUST bypass the provider.
Each canonical message MUST retain its exact engine-approved terms and deterministic text.
An omitted opening term MUST remain `UNSPECIFIED`.

The renderer MUST receive only an allowlisted `NpcDialogueRequest`.
The request MAY contain the approved speech act, approved public terms, approved qualitative disclosures, language, currency, participant-facing term identifiers, public `scenario_title`, `npc_role` identifier, `missing_term_labels`, example replies, deterministic fallback, and bounded public dialogue.
The public dialogue MAY contain messages from both participants in the current session.
It MUST contain no more than 12 turns.
Each turn MUST contain no more than 1,000 characters.
The service MUST redact credentials before truncation, persistence, or provider submission.
Redaction MUST cover the authenticated participant token, credential-shaped fragments, and known configured provider, custom-key, and administrator credential values.
The service MUST redact stored dialogue again when it constructs renderer context.

The request MUST NOT contain raw observations, scenario source, role briefs, raw session state, counterparty-private data, utility weights, reservation utility, BATNA utility, authored knowledge truth, distractor truth notes, constraints, private events, reviews, credentials, or lists of forbidden secrets.
Every transcript entry MUST remain untrusted conversation data.
A participant assertion MUST NOT become an approved fact or disclosure.
Prompt delimiters MUST NOT be treated as the security boundary.

`approved_reply_options` MUST remain bounded engine-authored examples and deterministic fallback candidates.
The options MUST NOT restrict the vocabulary of generated non-binding prose.
The options MUST retain the existing limits of six options, 1,200 characters per option, and 4,000 characters in total.

The generator MUST return one strict JSON object with only `speech_act` and `reply`.
The deterministic validator MUST check the speech act, output size, requested language, structure, credentials, numeric terms, and prohibited commitments.
An exact engine-authored reply option MAY bypass the grounding check.
Novel prose MUST pass a separate LLM grounding check before delivery.
The grounding check MUST receive only the same actor-safe input and the candidate reply.
The check MUST reject unsupported facts, unauthorized disclosures, commitments, and contradictions of the approved intent.
The check MAY approve or reject presentation only.
The check MUST NOT change the action, utility, truth, or session state.
An invalid or failed check MUST produce the precomputed deterministic fallback.
An unvalidated candidate and the check's raw response MUST NOT enter persistence, telemetry, or public output.

One durable render job MUST have at most one claimed render attempt.
That attempt MAY contain a generation call and a grounding-check call.
Both calls MUST occur outside SQLite write transactions.
The service MUST preserve compare-and-swap delivery and deterministic startup recovery.
The service MUST preserve same-session pending-render gates and cross-session isolation.
Failures MUST use the existing bounded metadata codes.
Provider failures MUST use `provider_failure`.
Invalid presentation or grounding results MUST use `output_invalid`.

### Consequences and risks

The NPC can respond to the player's latest message and recent public context.
The NPC SHOULD answer the immediate question before asking about missing terms.
The NPC SHOULD avoid repeating a request for a complete package after every message.
Russian and English MUST use the same state and rendering boundaries.

The separate grounding check increases latency and provider usage for novel replies.
The semantic check is probabilistic.
It is not a formal guarantee that every unsupported implication will be detected.
Deterministic checks also cannot prove arbitrary natural-language meaning.
Hidden data exclusion and structured-state authority remain deterministic boundaries.
Dialogue quality and semantic consistency require regression tests and manual review.

Affected specifications: `docs/architecture.md`, `docs/api.md`, and `docs/offer-session-protocol.md`.
