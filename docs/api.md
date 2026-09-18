# API Sketch

## Reference supply contract (DR-30)

[DR-30](decisions/2026-09-08_reference-supply-implementation.md) and the [resolved contract](reference-supply-contract.md) define the opt-in implementation.

Scenarios with `negotiation_contract: supply-package-v1` MUST initialize an exact authored preliminary proposal instead of an accept-enabled formal opening offer.
Preliminary proposals MUST remain non-binding even when complete.
The service MUST distinguish preliminary revision, final-offer publication, acceptance intent, and exact-revision confirmation.
A participant's final offer MUST require confirmation of its exact materialized snapshot before publication.
NPC promotion of its own preliminary package MUST present a formal offer without also treating the presentation request as acceptance.
The service MUST permit at most one actor-bound pending finalization operation per session.
An explicit amendment based on a formal offer MUST supersede that offer and invalidate its pending confirmation atomically.
Questions and uncommitted hypotheticals MUST NOT supersede an offer.
Every material amendment MUST use a source revision and preserve dependent conditions atomically.
Composite quantities, monetary allocation, reserve references, and all outcome obligations MUST be validated deterministically.
Incomplete packages MUST NOT receive authoritative complete-package utility.
The NPC MUST select actions using authored rules, NPC utility, and actor-safe public context.
It MUST NOT rank actions using counterpart private utility or expose hidden limits.
New supply rendering MAY use bounded paragraphs around an immutable engine-authored package block.
The LLM MUST NOT alter the block, invent amounts, or establish agreement through prose.
Legacy scalar scenarios, financial confirmation text, and stored renderer versions MUST retain their existing behavior.
Humans and external agents MUST use the same authenticated natural-language Player API.
Public history MUST retain source-linked preliminary revisions and formal offers without exposing private economics.
Replay and restart MUST use persisted validated transitions and stored wording without new LLM calls.
The implementation MUST pass offline reference trajectories and safety regressions before any generalization.
Optional semantic normalization MUST run outside SQLite write transactions.
The service MUST recheck actor authority, session revision, turn, and idempotency before committing its result.
The normalizer MUST preserve numeric tokens and MUST pass its result through deterministic parsing and validation.
Explicit negation, past proposals, and protocol controls MUST NOT become amendments through normalization.
Unsupported conditional clauses and uncertain equivalence MUST produce no package mutation.
Normalization failure MUST produce an observable clarification without exposing raw provider errors.

The API should be player-agnostic.

The Web UI and CLI use the same API.

The MVP language is Russian. Requests and stored sessions identify the language so that later versions can add languages.

Participant identity comes from an authenticated participant context. A client must not select its actor identity in a message body.

The negotiation engine should not care whether the player is:

- human;
- external LLM;
- scripted bot;
- replay agent.

Human participants and external-agent participants use the same natural-language Player API.

The public Player API does not accept typed actions from an external agent.

---

## Grounded dialogue extension (DR-28)

[DR-28](decisions/2026-09-06_grounded-negotiation-dialogue.md) extends the Player API without accepting typed external actions.
The parser MUST distinguish questions, quotations, proposals, relative changes, and short answers before committing terms.
Numeric questions and quotations MUST NOT create offers.
A mixed message MAY commit an explicitly scoped proposal clause while leaving a separate question non-binding.
The service MUST derive parse context after participant authentication, revision checks, and turn checks.
A relative change MUST use one active public offer revision and the scenario currency.
A short numeric answer MAY use one unambiguous public topic or an engine-authored requested term.
An ambiguous reference, missing baseline, or unsupported calculation MUST request clarification without changing offer terms.
Generated NPC prose MUST NOT establish the requested term, an agreement, or ground truth.
Human and external-agent acceptance MUST retain the separate complete-offer confirmation step.

The compiler MUST bound an authored exchange grid and validate its numeric candidates against required term schemas.
The engine MUST select a complete package that passes every role's hard constraints and the NPC reservation utility.
It MUST use only NPC utility, public proposals, and authored rules for exchange selection.
It MUST NOT optimize against counterpart private utility or expose private limits.
The policy SHOULD prefer a monetary concession in return for an authored nonmonetary benefit to the NPC.
It MUST NOT reverse a previous public monetary concession.
Missing terms MUST remain `UNSPECIFIED` during discussion.
The policy MUST NOT complete an omitted opening term implicitly.
An unsupported exchange MUST use a validated fallback or rejection without invented terms.
An exchange explanation MUST describe only the selected public package.

Numeric references MUST use exact attributed engine quote slots tied to an active public offer revision.
Each slot MUST identify its offer, revision, proposer role, term, value, currency, and exact display text.
The provider MUST emit a slot token instead of writing a number.
Unknown, altered, repeated, inactive, or unbound slots MUST be rejected.
The service MUST substitute exact engine text and validate the resolved reply.
A quote MUST NOT authorize a new promise, waiver, calculation, or agreement.
Novel prose MUST still pass the separate grounding check.
Canonical financial actions MUST remain deterministic.
The durable render plan MUST preserve the slots and their revision binding.
Historical plans without slots MUST remain readable.

New scenario versions MAY add grounded reasons, exchange candidates, and an allowlisted stable conversation style.
Existing versions MUST remain unchanged.
The service MUST select a bounded public dialogue profile from the session difficulty.
Guided and Easy profiles SHOULD clarify one term at a time and take conversational initiative.
Normal and Expert profiles SHOULD ask for grounds and reciprocal changes without abusive behavior.
Difficulty and style MUST NOT change hidden truth, utility, hard constraints, or reservation thresholds.
Benchmark sessions MUST use Normal difficulty and disabled assistance.

Dialogue quality MUST remain separate from utility and agreement rate.
Admin diagnostics MUST use public transcript, public renderer events, and bounded telemetry only.
They MUST distinguish exact repetition, question repetition, latency, fallback rate, and categorized validation failures.
Missing telemetry MUST remain unavailable rather than zero.
Heuristics MUST NOT be presented as proof of relevance or factual correctness.
Offline human scorecards MUST retain versioned source references and rating coverage.
Unrated dimensions MUST remain unrated.
The regression corpus MUST cover connected Russian and English dialogue, numeric questions, relative changes, short replies, corrections, repetitions, and false claims.
Existing privacy, confirmation, immutable-version, and durable-render boundaries remain required.

## Create session

```http
POST /sessions
```

```json
{
  "idempotency_key": "create_01J...",
  "scenario_id": "supplier_001",
  "scenario_version": 5,
  "language": "ru",
  "participants": [
    {
      "role": "buyer",
      "controller": "human"
    },
    {
      "role": "seller",
      "controller": "built_in_npc"
    }
  ],
  "difficulty": "normal",
  "hints_enabled": true,
  "run_mode": "training"
}
```

This contract example uses published `supplier_001` version 5 in a human-versus-built-in-NPC session.
It includes grounded motives, style, and exchange candidates under DR-28.

When `NEGOTIATION_ADMIN_TOKEN` is configured, a `run_mode: benchmark` session requires the administrator Bearer credential on this request. The service returns HTTP `401` with `administrator_unauthorized` otherwise. Training sessions need no credential. This gate stops an unauthenticated client from adding a session to a declared benchmark run and re-sealing its reviews.

Draft version 1 remains an authoring reference and cannot start a session.

Published version 2 remains immutable and available for explicit-version replay.

Version 3 uses a partial `opening_position` that states only the price.

Version 4 retains that opening position and adds authored `dialogue_reasons`.

Version 5 retains the economic rules and adds richer motives, stable styles, and bounded exchange candidates.

Versions 2, 3, and 4 remain available through explicit-version requests.

The session model uses participants and roles. It does not encode human and NPC as fixed domain seats.

An authorized orchestrator creates agent-versus-agent sessions with two external participants.

A benchmark session also includes run-set metadata:

```json
{
  "run_mode": "benchmark",
  "benchmark_run_id": "bench_20260828_01",
  "trial_id": "bench_20260828_01_t0001",
  "benchmark_expected_trials": 4,
  "seed": 1729,
  "difficulty": "normal",
  "hints_enabled": false
}
```

`benchmark_expected_trials` defines the complete run set for review release.

The pinned scenario version supplies `max_rounds`.

Response:

```json
{
  "session_id": "sess_abc123",
  "revision": 0,
  "scenario_version": 5,
  "scenario_content_digest": "sha256:...",
  "scenario_compiler_version": "scenario-compiler-v2",
  "compiled_scenario_digest": "sha256:...",
  "status": "active",
  "round": 1,
  "substantive_turn_count": 0,
  "next_actor": "participant_buyer",
  "observation": {
    "currency": "EUR",
    "role_brief": {
      "summary": "Вы представляете компанию Vector.",
      "objectives": ["Закупить 100 промышленных компьютеров для запуска проекта 1 декабря."],
      "context": "Nord Systems предложила цену 120 000 евро. Остальные условия стороны ещё не согласовали. Утверждённый бюджет не превышает 115 000 евро. Целевая цена составляет 105 000 евро. Срок поставки считается в полных неделях с 1 октября 2026 года. Поставка всего заказа до 15 ноября снижает риск срыва интеграции. Размер предоплаты можно обсуждать.",
      "batna": "Купить комплект за 108 000 евро у другого поставщика. Его оборудование хуже и создаёт дополнительный риск при интеграции.",
      "constraints": {"maximum_price": 115000},
      "priorities": ["price", "delivery_weeks", "prepayment_fraction"]
    },
    "conversation": [],
    "active_offers": [
      {
        "offer_id": "offer_01",
        "offer_revision": 1,
        "proposer_role": "seller",
        "terms": {
          "price": 120000
        },
        "unresolved_required_terms": [
          "prepayment_fraction",
          "delivery_weeks"
        ]
      }
    ],
    "assistance": null
  },
  "language": "ru"
}
```

The order quantity is fixed by the scenario brief.
It is not a negotiable term in version 3.

An absent opening-position term is `UNSPECIFIED`.

The service does not insert zero or another default value.

An explicit zero in an authored artifact or participant proposal remains a real value.

The partial active revision cannot bind while `unresolved_required_terms` is not empty.

An acceptance attempt against this revision returns HTTP `422` with `offer_not_bindable`.

The response preserves the partial active revision and does not create a pending acceptance confirmation.

The example above uses Normal difficulty.

For Easy difficulty, the same built-in NPC opening role presents the partial opening position in the stored conversation:

```json
{
  "revision": 0,
  "round": 1,
  "substantive_turn_count": 0,
  "next_actor": "participant_buyer",
  "committed_actions": [],
  "observation": {
    "conversation": [
      {
        "revision": 0,
        "participant_id": "participant_seller",
        "role": "seller",
        "message": "Добрый день. Предлагаю обсудить условия поставки промышленных компьютеров. Моя начальная позиция: цена 120 000 EUR. Остальные условия предлагаю обсудить."
      }
    ]
  }
}
```

This `opening_position` presentation is not a committed turn.

It does not change the active offer or `next_actor`.

It states exactly the authored public term.

It does not imply that the position is a complete package.

The service records it once as `npc.opening_utterance.delivered`.

The event payload contains `speech_act: opening_position` and `opening_kind: opening_position`.

The initial `offer.created` event contains the same `unresolved_required_terms` list as the active offer projection.

A repeated create-session idempotency request does not duplicate it.

The service does not create this message when the opening role is human or external.

`role_brief` is an actor-safe participant projection.
It contains the six fields shown in the example.
`constraints` omits `reservation_utility`.
`batna` contains a description and omits BATNA utility.
`priorities` contains stable identifiers in decreasing importance order.
It omits interest weights.
The projection does not contain role data for the counterpart.

The system issues a separate participant credential to each external controller.

The initial response delivers each external controller credential to the authorized orchestrator.

The service stores a credential-free idempotency result.
A repeated create request returns the same session without credentials and includes `credential_delivery: initial_response_only`.

The service must not expose one participant's credential to another participant.

---

## Submit message

```http
POST /sessions/{id}/messages
```

```json
{
  "message": "Мы готовы рассмотреть предоплату...",
  "idempotency_key": "cmd_01J...",
  "expected_revision": 7
}
```

The server derives the participant and role from the authenticated context.

The message body MUST NOT supply parser context, a baseline offer, or a requested term.
After authentication, revision checks, and turn checks, the server derives `ParseContext` from the same session.
Its internal fields are `active_offer_id`, `active_offer_revision`, `active_offer_terms`, `active_offer_currency`, `focused_term_id`, `expected_term_id`, and `ambiguous_offer_reference`.
It contains at most 12 finite numeric public terms.
`expected_term_id` comes only from an engine-authored `requested_term_id` in the latest relevant delivered NPC event.
The server MUST NOT infer this field from generated NPC wording.

The parser supports one explicit relative change with `на` or `by` against the unique active public baseline.
Monetary changes MAY use an amount or a percentage of the baseline.
Prepayment changes MUST identify percentage points.
Week and quantity results MUST remain integral.
Arbitrary arithmetic, dates, historical baselines, ambiguous units, and several numeric referents require clarification.
`Почему цена 120000 EUR?` is a question, not a proposal.
`Снизить цену на 10000 EUR` proposes a reduction from the checked active price, not an absolute price of 10000.
`105 тысяч` can propose a price only when its term is unambiguous.
The parser MUST preserve these distinctions in Russian and English.

The parser may propose an internal action, evidence, or a typed runtime term structure.

The engine validates runtime terms against the compiled scenario grammar, capabilities, constraints, and evaluation rules.

A proposal outside that grammar cannot receive an LLM-generated utility value or become binding.

When a scalar offer also contains an unsupported schedule, contingency, reserve, or similar composite semantic, the current parser returns `clarification_required` with reason code `unscored_proposal`.
The parser does not mutate the active offer.

The engine validates every extracted action before it changes state.

The parser accepts natural acceptance phrases such as `принимаю ваше предложение целиком` and `we accept your offer`.
It reads number words and thousand or million abbreviations.
A positive, unquoted assertion of the counterpart's complete active package can become an acceptance intent.
A question or reported quotation cannot become an acceptance intent through numeric matching.
The parser ignores a negated ending phrase such as `мы не уйдём из переговоров`.
See `docs/offer-session-protocol.md`.

The response is role-neutral.

The response MUST include the committed post-request session revision and an actor-safe observation.

When the next participant uses the built-in NPC controller, the service runs that controller automatically.

Example successful human-versus-built-in-NPC response:

```json
{
  "result": "turn_committed",
  "round": 4,
  "substantive_turn_count": 7,
  "revision": 9,
  "status": "active",
  "next_actor": "participant_buyer",
  "committed_actions": [
    {
      "participant_id": "participant_buyer",
      "action": "counter_offer",
      "message": "Мы готовы рассмотреть предоплату...",
      "offer": {
        "offer_id": "offer_01",
        "offer_revision": 4
      },
      "offer_lifecycle": {
        "offer_id": "offer_01",
        "offer_revision": 4,
        "status": "active"
      }
    },
    {
      "participant_id": "participant_seller",
      "action": "question",
      "message": "Какую долю предоплаты вы рассматриваете?"
    }
  ],
  "observation": {}
}
```

In an external-agent-versus-external-agent session, one request commits at most one participant action.

### Built-in NPC dialogue rendering

The engine selects and validates the built-in NPC action before it renders the NPC message.

The structured `committed_actions[].action` and structured offer are authoritative.

The `message` field contains the public wording of that action.

A built-in NPC action also contains the engine-approved `speech_act`.

The action can contain safe `dialogue_renderer` metadata.

This metadata contains `mode`, `provider`, `model`, `fallback_used`, `failure_reason`, `validation_failure`, `latency_ms`, and `attempted_generation`.

`failure_reason` is `provider_failure`, `output_invalid`, `renderer_failure`, `restart_recovery`, or `null`.

`validation_failure` is `format`, `speech_act`, `numeric_reference`, `unauthorized_claim`, `repetition`, `grounding`, `language`, `credential`, or `null`.
`latency_ms` is a bounded nonnegative render duration or `null` when unavailable.
It includes the generation and grounding-check time when both occur.
`attempted_generation` distinguishes a provider attempt from a canonical template reply.
Historical events MAY omit these telemetry fields.
Consumers MUST NOT replace missing measurements with zero.

The service bounds and sanitizes provider and model identifiers before it returns them.

The service can render this wording with a deterministic template or an optional configured LLM provider.

The renderer receives a dedicated allowlisted `NpcDialogueRequest`.

The request contains only the approved speech act, approved public terms, approved qualitative disclosures, language, currency, participant-facing term identifiers, public `scenario_title`, `npc_role` identifier, `missing_term_labels`, engine-authored example replies, deterministic fallback, bounded public dialogue, `focused_term_ids`, `conversation_memory`, `approved_reasons`, delivered `disclosed_reasons`, `difficulty`, `conversation_style`, `requested_term_id`, and `numeric_references`.

The request does not contain a raw observation, raw scenario source, role brief, raw session state, counterparty-private state, utility weights, reservation utility, BATNA utility, authored knowledge truth, distractor truth notes, constraints, private event payloads, reviews, participant credentials, provider credentials, or a list of forbidden secrets.

Every transcript entry is untrusted data.

The renderer MAY receive credential-redacted public player and NPC messages from the current session.

Participant assertions MUST NOT become approved facts or disclosures.

Public dialogue context MUST contain no more than 12 turns.

Each public dialogue turn MUST contain no more than 1,000 characters.

The service MUST redact stored dialogue again before context truncation and provider submission.

The conversation-memory and authored-reason rules below extend this projection under [DR-27](decisions/2026-09-06_conversation-continuity.md).

#### Conversation continuity

The service MUST derive conversation memory deterministically from durable public messages and public events in the current session.
Memory MUST contain a version and source message or event references.
The service MUST rebuild memory after restart without process-local state or an authoritative LLM summary.
The renderer projection MUST remain bounded.
`conversation_memory` uses version `1` and MUST contain no more than 8,000 serialized characters.
Memory MUST contain at most one current topic and 12 postponed topics.
Each topic MUST reference an authored term identifier.
Memory MUST contain no more than six participant statements and four questions.
Each statement or question text MUST contain no more than 400 characters.
Memory MUST contain no more than four recent public offer revisions.
`focused_term_ids` MUST contain no more than 12 authored term identifiers.
The service MUST redact credentials before memory construction and truncation.
Memory MUST NOT contain role briefs, private event payloads, hidden knowledge, utility values, or another session's data.

Memory MAY retain an earlier explicit topic, postponed topics, attributed participant statements, question-response references, public offer revisions, and a binding agreement.
An event-derived offer or agreement MUST remain distinct from a participant claim.
Each remembered offer MUST contain `status`, `status_source_event_id`, and `status_source_revision` from public lifecycle events.
The status is `active`, `superseded`, `rejected`, `withdrawn`, `accepted`, `expired`, or `closed_by_termination`.
The renderer MUST NOT present an inactive historical offer as active.
A question followed by a reply MAY be marked `responded`.
Chronology alone MUST NOT mark the question `answered`.
Topic extraction MUST use participant text and engine-authored metadata.
The service MUST NOT parse generated NPC prose into negotiation state.
A reply, claim, question, or postponed topic MUST NOT become an agreement or ground truth.

An explicit request to discuss one authored term MUST take precedence over a generic discussion cue.
An incomplete valid price proposal MUST NOT force an immediate complete-package request when a focused non-binding response is available.
The engine MAY select `focused_discussion` or `acknowledge_partial_offer` before rendering.
An explicit topic switch MUST replace the previous focus.
A postponed topic MUST remain unresolved and MAY resume after a later explicit request.
Omitted required terms MUST remain `UNSPECIFIED`.
Binding acceptance MUST still require a complete validated package.

#### Authored reasons

A role MAY define `dialogue_reasons` in a new immutable scenario version.
Each reason MUST contain `id`, `term_id`, `text`, `source_ref`, and `disclose_when`.
`source_ref` MUST reference that role's `brief.objective` or `brief.context`.
`disclose_when` MUST be `on_topic_question` in this increment.
The compiler MUST validate identifiers, uniqueness, topic references, source references, limits, and plain nonnumeric text.
Each role MAY define at most six reasons.
Each reason text MUST contain at most 300 characters.
The author remains responsible for semantic grounding in the referenced authored source.

The engine MAY select at most two reasons per reply when the participant asks about the matching term or asks a contextual follow-up about the current topic.
The renderer MUST receive only selected reason identifiers and texts, plus previously delivered public reason history.
It MUST NOT receive the private source text or unselected private reasons.
`approved_reasons` contains at most two `(id, text)` pairs.
`disclosed_reasons` contains at most six `(id, text, source_event_id)` records for earlier delivered disclosures.
The provider payload presents `conversation_memory` as `public_conversation_memory` and each reason as an object with named fields.
Only delivered disclosures MAY enter persistent disclosed-reason history.
A pending or failed render MUST NOT prove disclosure.
The renderer MUST include every text from `approved_reasons` verbatim in the reply.
It MUST reject generated text that omits or paraphrases a selected reason instead of including the exact text.
After a reason is delivered, the engine MUST NOT select it again for `approved_reasons`.
The renderer MAY use that reason from `disclosed_reasons` without verbatim repetition.
Only an exact reason text in the delivered message qualifies for `disclosed_reason_ids` in the public `npc.utterance.delivered` event.
A paraphrase alone MUST NOT prove disclosure.
Reasons MUST NOT change utility, acceptance thresholds, hard constraints, or capabilities.
Old scenario versions MUST remain unchanged and valid without reasons.
Historical render plans without conversation memory or authored reasons MUST remain readable.
An absent `conversation_memory` defaults to an empty object.
Absent focused-term and reason fields default to empty collections.

#### Numeric references, dialogue profiles, and durable fields

`difficulty` is `guided`, `easy`, `normal`, or `expert`.
`conversation_style` is `pragmatic`, `analytical`, or `relationship_focused`.
These identifiers map to fixed provider instructions under `dialogue_profile` and `conversation_style`.
They MUST NOT authorize new disclosures or change economic rules.
The Easy canonical opening behavior remains unchanged.

`requested_term_id` is an authored participant-facing term or `null`.
The engine selects this field before rendering.
When it is present, a generated numeric-answer question MUST concern that term only.
The service records it in the public `npc.intent.committed` and `npc.utterance.delivered` payloads.
A pending intent MUST NOT establish the next parser's requested term.

`numeric_references` contains at most 12 objects.
The durable form contains these fields:

```json
{
  "slot_id": "quote_a",
  "offer_id": "offer_01",
  "offer_revision": 4,
  "proposer_role": "buyer",
  "term_id": "price",
  "value": 105000,
  "currency": "EUR",
  "display_text": "В вашем предложении: цена 105 000 EUR.",
  "format_version": 1
}
```

The slot identifier MUST be `quote_a` through `quote_l` and MUST be unique in the request.
`display_text` MUST contain no more than 400 characters.
The versioned formatter MUST preserve the exact value and proposer attribution.
Each slot MUST match one active public memory offer and the request currency.
The provider receives the same fields plus `token: [[quote_a]]` and the exact resolved `text`.
It MUST return the token in `reply` instead of spelling the number itself.
An absent opening term MUST NOT have a slot.
An inactive historical offer MUST NOT have a slot.
Unknown, altered, repeated, or unbound tokens MUST fail validation.
The 1,200-character reply limit MUST apply before and after substitution.
The grounding check MUST evaluate the resolved reply.
A valid quotation MUST NOT imply that a proposal was accepted.

The enclosing durable plan contains `render_id`, `session_id`, `intent_revision`, `npc_participant_id`, `action`, and `request`.
The service MUST persist the complete allowlisted request before provider I/O.
Recovery MUST revalidate its stored slots and retain the original revision binding.
Legacy requests default to `difficulty: normal`, `conversation_style: pragmatic`, `requested_term_id: null`, and an empty `numeric_references` list.

#### Output validation

Prompt delimiters are not a security boundary.

`approved_reply_options` contains no more than six engine-authored actor-safe strings.

Each approved reply option contains no more than 1,200 characters.

All approved reply options together contain no more than 4,000 characters.

An approved reply option does not interpolate or quote raw participant or transcript text.

A non-binding approved reply option does not contain a number, date, percentage, currency symbol, or currency code.
Novel non-binding wording MAY contain numbers only through validated DR-28 quote substitution.

For a non-binding speech act, an external provider MAY generate new wording.

`approved_reply_options` are examples and fallback candidates, not exclusive vocabulary.

The provider returns one strict JSON object with only `speech_act` and `reply`.

The deterministic validator MUST check speech-act equality, output size, requested language, structure, credentials, numeric terms, and prohibited commitments.

The validator rejects invalid JSON, unexpected fields, empty output, unsafe structure, multiple speakers, markup, tool output, URLs, and output that exceeds a bound.

Novel prose MUST pass a separate LLM grounding check before delivery.

An exact engine-authored reply option MAY bypass the grounding check.

The check receives only the same actor-safe input and the candidate reply.

The check MUST reject unsupported facts, unauthorized disclosures, commitments, and contradictions of the approved intent.

The check can approve or reject presentation only.

The check MUST NOT change the action, utility, truth, or session state.

The semantic check is probabilistic, not a formal guarantee.

Deterministic checks cannot prove arbitrary natural-language meaning.

The service MUST NOT parse generated NPC prose back into negotiation state.

Provider output cannot create or change a structured action, offer revision, binding term, disclosure permission, or terminal transition.

`opening_offer`, `opening_position`, `offer_acceptance`, `offer_rejection`, and `complete_counteroffer` bypass the provider.

Each binding message uses the canonical deterministic template and canonical engine-approved terms.

The service uses an actor-safe deterministic template when no provider is configured.

The service uses the precomputed deterministic template when provider execution fails, times out, returns invalid output, or violates the output contract.

The service calls an external provider outside SQLite write transactions.

The service atomically claims one pending render job before one render attempt.

Concurrent service instances MUST NOT make more than one render attempt for the same render identity.

That attempt MAY include a generation call and a separate grounding-check call.

Both calls MUST occur outside SQLite write transactions.

An invalid or failed check MUST produce the precomputed deterministic fallback.

Provider failures use `provider_failure`.

Invalid presentation or grounding results use `output_invalid`.

An unvalidated candidate and the check's raw response MUST NOT enter persistence, telemetry, or public output.

Fallback does not change the committed action, offer state, session revision, status, or `next_actor`.

The API does not return provider credentials, prompts, raw provider output, or raw provider error bodies.

A client MUST use the structured action and offer as the source of truth.

A client MUST NOT derive an acceptance, rejection, or counteroffer from generated prose alone.

The service MUST replace the authenticated participant token, credential-shaped fragments, and known configured provider, custom-key, and administrator credential values with `[REDACTED_CREDENTIAL]` before parsing, truncation, persistence, or provider submission.

If an earlier NPC render job is unfinished, a new message, hint, or administrative close returns HTTP `409` with `npc_render_pending`.

The client SHOULD retry the original uncertain message with the same `idempotency_key`.

On startup, the service completes each unfinished durable render job with the precomputed deterministic fallback.

A create-time built-in NPC binding action uses its canonical deterministic message in the create transaction.

The create-time binding action does not create a render job or invoke a provider.

OpenAI rendering defaults to `gpt-5.6-luna`.

Qwen rendering defaults to `qwen3.8-max` and the QwenCloud Token Plan endpoint.

The service does not send `temperature` when `NEGOTIATION_NPC_TEMPERATURE` is empty.

### Clarification response

The server returns this response when the text has more than one material interpretation:

```json
{
  "result": "clarification_required",
  "revision": 8,
  "round": 4,
  "substantive_turn_count": 6,
  "status": "active",
  "next_actor": "participant_buyer",
  "clarification": {
    "reason_code": "ambiguous_agreement_scope",
    "question": "Вы соглашаетесь только с условием поставки или со всем предложением?",
    "candidate_interpretations": [
      "agree_to_delivery_term",
      "accept_complete_offer"
    ]
  },
  "observation": {}
}
```

The server records the message and ambiguity event.

It does not change the deal or consume a negotiation round.

The same participant remains `next_actor`.

The UI and external-agent runner MUST show the `clarification_required` result explicitly.

Contextual numeric clarification can use `numeric_answer_requires_term`, `numeric_answer_requires_unit`, `relative_change_requires_baseline`, `ambiguous_numeric_reference`, or `ambiguous_relative_change`.
Currency mismatch still uses `currency_mismatch`.
These results preserve active offer terms and turn ownership.

### Acceptance confirmation response

An unambiguous intent to accept a complete offer does not bind the deal immediately.

The server returns the exact materialized offer for confirmation:

```json
{
  "result": "confirmation_required",
  "revision": 10,
  "round": 4,
  "substantive_turn_count": 6,
  "status": "active",
  "next_actor": "participant_buyer",
  "pending_confirmation": {
    "offer_id": "offer_01",
    "offer_revision": 4,
    "terms": {
      "price": 109500,
      "currency": "EUR",
      "quantity": 100,
      "payment_schedule": {
        "prepayment_fraction": 0.5,
        "remaining_payment": "net_30_after_delivery"
      },
      "delivery_schedule": [
        {"quantity": 10, "date": "2026-11-07"},
        {"quantity": 90, "date": "2026-11-20"}
      ],
      "reserve_policy": {
        "quantity": 3,
        "defect_verification": "supplier_diagnostic_confirmation",
        "used_units": {
          "when_defect_confirmed": "FOC",
          "otherwise": "contract_unit_price"
        },
        "unused_units": {
          "payable_after": "2026-12-01",
          "price": "contract_unit_price"
        }
      },
      "rma_principle": "supplier_diagnostic_confirmation"
    },
    "unresolved_required_terms": []
  },
  "observation": {}
}
```

The participant confirms or cancels in natural language.

The Web UI may render buttons that submit canonical natural-language messages through this endpoint.

The engine binds the deal only after it validates a positive confirmation against the pending offer revision.

The terms in this example are illustrative. The scenario compiler must define every primitive, capability, constraint, and evaluation rule used by the package.

See `docs/offer-session-protocol.md` for all offer and transition rules.

### Conflict responses

An `expected_revision` mismatch returns HTTP `409` with `revision_conflict` and does not create an event.

An attempt to accept a superseded, withdrawn, rejected, or expired offer returns HTTP `409` with `offer_not_active`.

The server records the participant message and failed domain transition before it returns `offer_not_active`.

This response includes the post-recording session revision.

A repeated `idempotency_key` returns the stored original result, including a stored error result.

Create-session credential delivery is the exception described above.

---

## Get session

```http
GET /sessions/{id}
```

The response contains the session identity and counters, `hints_enabled`, the actor-safe `observation`, and the participant's own pending protocol state: `pending_confirmation` (the exact offer revision awaiting confirmation) and `clarification` (reason code and question). Both are `null` when nothing is pending for the authenticated participant. A client uses this endpoint to restore a session after a reload.

## Get observation

```http
GET /sessions/{id}/observation
```

The returned observation is actor- and difficulty-specific.

Conceptually:

```text
Observation = f(SessionState, Actor, Difficulty)
```

Never return hidden state through this endpoint.

Difficulty and teaching mode never authorize access to raw hidden state.

When a mode exposes detected signals, the observation contains actor-safe belief projections derived from validated evidence.

The projection may contain confidence or the configured `UNKNOWN`, `PARTIAL_SIGNAL`, `PROBABLE`, and `CONFIRMED` label.

It does not expose `RealityState` or another participant's private belief state.

An active participant receives the `active_player` projection.

A completed training participant may receive the configured `training_review` projection.

A benchmark participant receives no hidden review data until the complete benchmark run set is finished.

---

## External-agent behavior

An external LLM agent gets its participant-scoped observation and submits natural-language messages.

It receives the same clarification and acceptance-confirmation flows as a human participant.

It does not submit an intent, offer object, `accept` command, or `walk_away` command directly.

The engine extracts and validates those proposed internal actions from text.

Benchmark agents receive no hints or training assistance.

---

## History

```http
GET /sessions/{id}/messages
GET /sessions/{id}/events
GET /sessions/{id}/history
```

Internal events are never returned directly to active participants.

Each endpoint returns a participant-safe event, metric, or review projection.

Teaching mode may release selected information only after session completion and only through the configured training-review projection.

---

## Fork session

Status: not implemented in the current service. The endpoint is a specification target and currently returns HTTP `404`.

```http
POST /sessions/{id}/fork
```

```json
{
  "idempotency_key": "fork_01J...",
  "expected_revision": 12,
  "source_revision": 7,
  "configuration_overrides": {}
}
```

Response:

```json
{
  "session_id": "sess_branch_456",
  "parent_session_id": "sess_abc123",
  "source_revision": 7
}
```

`source_revision` identifies parent state after that exact committed revision.

The branch inherits offer status, pending protocol state, delivered participant information, and run configuration at that revision.

An authorized training orchestrator may record model or policy overrides in `configuration_overrides`.

Forks support training, deliberate practice, and branch comparison.

A forked session is not eligible as an independent benchmark trial.

---

## Administrative close

```http
POST /sessions/{id}/close
```

This endpoint requires administrator authorization.

It changes a non-terminal session to `aborted`.

The request includes `idempotency_key`, `expected_revision`, and an administrative reason.

A participant ends negotiations through a natural-language `walk_away` intent on the message endpoint.

Agreement, expiry, and terminal technical failure use engine-owned transitions.

---

## Administrative Session Inspector

```http
GET /admin/sessions
GET /admin/sessions/{session_id}
```

Both endpoints require this header:

```http
Authorization: Bearer <NEGOTIATION_ADMIN_TOKEN>
```

The service returns HTTP `503` with `administrative_access_disabled` when `NEGOTIATION_ADMIN_TOKEN` is not configured.

The service returns HTTP `401` with `administrator_unauthorized` when the credential is absent or invalid.

`GET /admin/sessions` accepts these optional query parameters:

- `status`;
- `scenario_id`;
- `language`;
- `run_mode`;
- `limit`, from 1 through 200;
- `offset`, from 0.

The response contains `items`, `total`, `limit`, and `offset`.

Each item contains safe session metadata, participant controller provenance, counts, and `review_state`.

`review_state` is `not_ready`, `sealed`, or `available`.

`GET /admin/sessions/{session_id}` returns the same metadata plus:

- participants without credentials or credential hashes;
- transcript messages;
- public event payloads;
- immutable offer revisions;
- public `dialogue_quality` diagnostics;
- the stored public review when `review_state` is `available`.

The detail response MUST NOT contain `state_json`, scenario source, private event payloads, or private review data.

An active session returns `review_state: not_ready` and `review: null`.

A benchmark session returns `review_state: sealed` and `review: null` until the complete declared run set is terminal.

A terminal training session and a released benchmark session return only `reviews.public_json`.

### Dialogue diagnostics

`dialogue_quality` is independent of the economic review and is available for active sessions.
It MUST use only public transcript rows, public `npc.utterance.delivered` events, and safe renderer telemetry from the selected session.
Its `version` is `1` and `heuristic_only` is `true`.

- `turns` contains total, player, and NPC message counts.
- `repetition` contains exact-reply and question-repeat counts, bounded source references, and `flags_truncated`.
- `rendering` contains delivered and telemetry counts, generation attempts, fallback observations and rate, categorized failures, and latency sample count, average, and p95.
- `human_review` contains `rubric_version`, `status`, the four dimensions, and rating coverage.

Repetition normalizes case and whitespace and counts each NPC participant separately.
The response contains at most 100 repetition flags.
Counts still include all observed repeats.
Canonical replies without generation MUST NOT enter generation latency or fallback-rate denominators.
Missing latency and missing fallback observations MUST yield `null` metrics.
The API MUST NOT infer a humanity score or populate human ratings automatically.
The four human dimensions are `relevance`, `continuity`, `attribution`, and `unsupported_claims`.
They remain `null` in the Inspector API in this increment.
The offline evaluator supports source-checked human ratings from 0 to 4 and records per-dimension sample counts.
The diagnostic response MUST NOT reveal hidden facts or alter benchmark-review release rules.
See the [dialogue evaluation rubric](dialogue-evaluation-rubric.md) for the exact definitions and offline procedure.

---

## Hints

```http
POST /sessions/{id}/hints
```

The request carries `idempotency_key` and `expected_revision`. The response delivers one actor-safe hint and records a `hint.delivered` event. Benchmark sessions and sessions with `hints_enabled: false` reject the request.

## Statistics

```http
GET /stats
```

The endpoint returns `totals`, `by_model`, `by_scenario`, `by_language`, `by_difficulty`, `benchmark_runs`, and `privacy`. Every group row contains `session_count` (distinct sessions), `seat_count` (participant seats), `completed_count`, `agreement_rate`, `avg_outcome_score`, and `avg_skill_score`. Score averages appear only when the group has at least the configured minimum number of completed sessions. A benchmark session contributes no agreement or score until its run set is released.

## Health

```http
GET /health
```

The response contains `status`, `database`, `journal_mode`, and `scenario_count`.

## Review

```http
GET /sessions/{id}/review
```

The evaluator produces a review for `agreement_reached`, `walked_away`, `expired`, `aborted`, and `technical_failure`.

Example response:

```json
{
  "outcome": {
    "agreement": true,
    "termination_reason": "agreement_reached",
    "participant_utility": 89,
    "participant_utilities": {
      "buyer": 89
    },
    "reservation_comparison": "above"
  },
  "skills": {
    "probing": 72,
    "conditional_trading": 91,
    "package_design": 88,
    "clarity": 84
  },
  "scores": {
    "outcome_score": 89,
    "skill_score": 84
  },
  "assistance_usage": {
    "hints_used": 0
  },
  "key_moments": [
    {
      "event_id": "evt_...",
      "type": "offer.countered",
      "title": "Встречное предложение",
      "summary": "Покупатель сделал встречное предложение: цена 106 000 €, предоплата 20%, срок поставки 6 недель.",
      "detail": "«Предлагаю пакет: цена 106 000 евро, предоплата 20%, поставка 6 недель.»"
    }
  ],
  "recommendations": [
    {
      "skill": "probing",
      "text": "Задайте больше открытых вопросов об интересах партнёра до того, как менять цену."
    }
  ]
}
```

`key_moments[].summary` names the acting role and the package in the session language. `key_moments[].detail` quotes the participant message that produced the event when one exists. `recommendations` lists actor-specific coaching sentences derived from the deterministic skill scores and the outcome. Both fields are optional for clients.

An intentional no-ZOPA scenario can return a successful `walked_away` training outcome.

The review compares a deal with `reservation_utility`. A built-in policy accepts a deal only when every hard constraint passes and `U(deal) >= reservation_utility`.

Exact opponent utility, BATNA, reservation utility, and hidden facts are returned only when the configured post-session reveal policy permits them.

For `after_complete_run_set`, the service returns HTTP `409` with `benchmark_review_sealed` until all declared trials exist and are terminal.

Public score aggregates omit the sealed benchmark scores.

---

## Scenario endpoints

```http
GET  /scenarios
POST /scenarios
GET  /scenarios/{id}
POST /scenarios/{id}/versions
GET  /scenarios/{id}/versions/{version}
```

Status: the current service implements the three `GET` endpoints. Scenario versions load from the configured scenario directories at startup. The `POST` authoring endpoints are specification targets and currently return HTTP `404` or `405`.

`GET /scenarios` returns the latest published version of each scenario ID.
The explicit version endpoint keeps earlier immutable versions available for replay.

A session pins an immutable scenario-version snapshot, source content digest, scenario compiler version, and compiled scenario digest.

The authoring lifecycle and publication freeze point remain an open decision.

Scenario create and version endpoints are author or administrator endpoints. Participants receive only scenario metadata through their observation.

A scenario version declares its language, authored world, term primitives, capabilities, composition rules, hard constraints, utility rules, expected ZOPA condition or training intent, and hidden-state reveal policy.

Exactly one role defines exactly one authored opening artifact.

`opening_offer` is a complete artifact and contains every required term.

`opening_position` can omit required terms.

`opening_position` must contain at least one authored term.

The compatibility metadata field `opening_offer_role` identifies the opening role for either artifact.

The `opening_kind` metadata field is `opening_offer` or `opening_position`.

The source document conforms to `schemas/scenario-v1.schema.json`.

New versions MAY define `exchange_policy.candidate_values` and role `conversation_style`.
The exchange grid MUST contain between two and 12 required terms, including `price` or `annual_rent`.
Each term MUST have between one and 16 distinct finite numeric values that pass its authored schema.
The complete candidate product MUST contain at most 512 packages.
Unknown or optional terms, duplicate values, booleans, and invalid numeric values MUST fail compilation.
These authored rules do not authorize the renderer to invent a tradeoff.

The target scenario compiler creates atomic knowledge definitions and typed runtime rules.

A future runtime can create a concrete composite term from these compiled rules.

A proposal outside the compiled grammar has no utility and cannot become binding.

See `docs/knowledge-and-emergent-state.md` for the normative model.

---

## Event streaming

Optional:

- SSE
- WebSocket

Public event examples:

```text
session.message.received
session.processing
session.participant.responded
session.clarification.required
session.confirmation.required
session.finished
```

Do not expose internal hidden-state updates over the public event stream.

---

## Benchmark runner contract

Each independent benchmark trial creates a fresh session.

Each tested agent plays both roles.

The runner repeats trials with one fixed run configuration.

The configuration pins the scenario version, language, model and provider versions, prompt versions, policy version, generation parameters, and randomness settings.

Benchmark sessions disable hints and training assistance.

The exact repetition count is a runner configuration value.

The runner sends that value as `benchmark_expected_trials` for every trial in the run.

The runner collects actor-scoped reviews after the full declared set becomes terminal.

---

## Future speech adapters

STT accepts speech and returns canonical text for the standard message flow.

TTS accepts an actor-safe public message and returns audio.

Speech endpoints or client-local adapters are an implementation decision.

Audio never replaces the canonical text transcript or structured event log.
