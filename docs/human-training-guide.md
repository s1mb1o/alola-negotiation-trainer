# Human negotiation training

Date: 2026-09-26.
Contracts: [DR-36](decisions/2026-09-24_training-loop.md) and [DR-48](decisions/2026-09-26_rewind-and-player-assist.md).
## Use the Web UI

[DR-51](decisions/2026-09-26_negotiation-methodologies.md) adds Harvard, BATNA/ZOPA, and Voss to NPC wording and final coaching.
The NPC can ask about interests, explain an authorized exchange, or tentatively reflect a stated concern.
It must answer a direct question first.
The engine still selects the action and validates the terms.
Warm wording does not change the acceptable economic range.

The completed report shows agreement surplus over your BATNA and margin over your reservation utility.
These numbers use scenario utility units.
Without agreement, no deal surplus is shown.
An exit alone does not prove success or failure.
The report does not infer an exact ZOPA from the conversation.

New coaching has three evidence-linked cards: economics, negotiation process, and communication.
The coach can report insufficient evidence for a dimension.
This is not a negative skill rating.
Voss techniques are optional. A technique name does not earn a score.
Old cached coaching remains readable and is not regenerated automatically.

### Steps

1. Select a scenario and your role.
2. Select a counterpart profile and relationship history.
3. Enter the optional player name and shared background.
4. Open the private preparation card.
5. Record your goal, unacceptable outcome, possible exchanges, and questions.
6. Optionally set a numeric target for a supported scalar term.
7. Start the negotiation.
8. Select **Ответь за меня** when you want the configured review model to send one player reply.
9. Select **Вернуться сюда** under an earlier NPC message when you want to retry from that point.
10. End the negotiation through an agreement or an explicit exit message.
11. Select **Получить разбор** after the deterministic report appears.
12. Read the evidence excerpts and proposed alternatives.
13. Select a saved decision point and start a completed-session retry.
14. Complete the retry and compare the observed results.

The dialogue starts with a **Ваш бриф** card before the NPC greeting.
The card shows the authenticated player's role brief, objectives, context, BATNA, limits, and priorities.
The card remains visible at the top when a new conversation starts.
After the player sends a message, the dialogue scrolls to the latest reply.
The card also appears at the start of a restored or completed transcript.
The card is private UI content. It is not a negotiation message and is not sent to the NPC.
The card also contains additional scenario context that the Player API permits the player to see.
The Web UI has no separate **Ваш контекст** panel.
The dialogue occupies the main column. Offers, the private plan, and assistance appear in the right column.
Four live social indicators appear at the bottom of the right column.
They show contact, credibility, tension, and patience on a 0–100 scale.
The current number beside each axis matches the marker position.
The value with the `Δ` label shows the engine-applied change after the player's latest message.
The indicators show zero after a message that causes no validated change.
They are simulation parameters and not psychological measurements.
On narrow screens, these supporting cards appear below the dialogue.

The UI uses Russian by default.
The UI also supports English.
Session language is independent of UI language.
Internal model instructions use STE-style English under [DR-43](decisions/2026-09-24_ste-system-prompts.md).
Each sentence contains one instruction or idea.
This instruction style does not require technical or mechanical dialogue.
Russian quotes and canonical protocol phrases retain their exact text.

The private card is available only to its owner and the final coach.
The NPC receives shared background, its profile, an authored personal detail, and a derived tone.
It does not receive the private card or raw social values.
Only the training owner receives `training.social_state` through the Player API.
The projection contains current values, the latest aggregate delta, and its source revision.
It contains no classifier quote or hidden event history.
The browser stores the active credential in session storage.
The local progress summary excludes the private card, detailed coaching, and its transcript excerpts.

## API contract

`POST /api/v1/sessions` accepts an optional `training` object.
The object is available only for one `human` and one `built_in_npc` in `training` mode.
Omission retains the previous behavior.
The Web UI supplies the object by default.

```json
{
  "profile": "sociable",
  "relationship": "successful_history",
  "player_name": "Александр",
  "shared_background": "Мы успешно завершили предыдущую поставку.",
  "personal_detail": true,
  "preparation": {
    "target": "Согласовать приемлемую цену без срыва запуска.",
    "unacceptable_result": "Поставка после запуска проекта.",
    "available_trades": "Можно обсудить более раннюю предоплату.",
    "information_to_discover": "Что ограничивает срок поставки?",
    "targets": [{"term_id": "price", "operator": "lte", "value": 115000}]
  }
}
```

Use this object as the `training` field of the existing create request.
The example numeric target uses the scalar supplier scenario's EUR price term.
It is not a default target for other scenarios.
`GET /scenarios` exposes `training_terms` with supported numeric identifiers and display labels.
The service does not expose private term bounds in that metadata.
Composite targets are not supported in this version.
The API permits up to six distinct targets.
The initial Web UI edits one numeric target.

| Field | Contract |
| --- | --- |
| `profile` | `concise_skeptical` or `sociable` |
| `relationship` | `first_meeting` or `successful_history` |
| `player_name` | At most 100 characters; letters, spaces, hyphens, apostrophes, and periods; can be empty |
| `shared_background` | At most 800 characters; no instruction or economic authority |
| `personal_detail` | Enables the authored dog fact; default `false` |
| Preparation text | Four optional strings; at most 1000 characters each |
| `targets[].term_id` | A numeric primitive in the pinned scenario |
| `targets[].operator` | `lte`, `gte`, or `eq` |
| `targets[].value` | A finite number in that term's units |

An older scenario version without `dialogue_strategy` uses the neutral or relationship-aware revision-zero greeting.
`successful_history` selects one of six authored greetings in the session language for these versions.
The wording signals prior familiarity or collaboration.
It does not invent a past term, concession, promise, event, or current agreement.
The selected text is stable for the session and its replay.
The Web UI selects `successful_history` by default for new sessions.
Select `first_meeting` in **Общий опыт** when the participants do not have shared history.
An existing session retains the relationship and greeting that were stored at creation.

A new scenario version can define `dialogue_strategy` for the opening NPC role.
The Web UI sends `player_name` as untrusted training data.
The opening renderer uses an exact name placeholder when this field is not empty.
The engine inserts the exact public scenario title and selected opening terms.
The model connects these items to actor-safe scenario context.
It asks one question that advances the authored opening goal.
Later replies answer the player first and then advance the authored conversation goal.
These goals cannot authorize a new fact, value, concession, commitment, or agreement.

All following endpoints require the participant Bearer credential.
The participant must own the training configuration.

| Method and route | Result |
| --- | --- |
| `GET /sessions/{id}/review` | Deterministic report and cached coaching status; no provider calls |
| `POST /sessions/{id}/coaching` | One cached generation and grounding job for the completed session |
| `GET /sessions/{id}/checkpoints` | Recorded human decision revisions |
| `POST /sessions/{id}/rewind` | Active-dialogue child session from an eligible NPC checkpoint |
| `POST /sessions/{id}/player-assist` | Read-only player reply from actor-safe context |
| `POST /sessions/{id}/fork` | New session and initial-only fresh credential delivery |
| `GET /sessions/{id}/comparison` | Same-role parent and child outcomes after the child completes |

The coaching request has no body.
It returns `complete`, `unavailable`, or `pending`.
A pending concurrent request can receive HTTP 202.
An active session receives HTTP 409 before a provider call.
Benchmark review gates remain active.
Benchmarks do not accept this training configuration or training forks.
Repeated coaching requests return the cached result.
A failed result remains cached.
A pending job older than three minutes becomes `unavailable` on the next coaching request.
The service does not automatically repeat the model call after interruption.

The fork request body is:

```json
{"source_revision": 2, "idempotency_key": "retry-decision-unique-key"}
```

The parent must be terminal.
The selected checkpoint must exist.
The child preserves the exact state, pending confirmation, and history boundary at that revision.
The child receives fresh participant and event identifiers.
The service remaps structured references.
The service does not copy later history, render jobs, parent credentials, or idempotency records.
An idempotent repeat returns the same child without redelivering its credential.
Keep the first response credential.
Older sessions without training checkpoints cannot use this retry route.

The rewind request uses the same `source_revision` and `idempotency_key` fields as the fork request.
The source revision must contain a stored NPC message and a checkpoint.
The source session stays immutable.
The returned child has the exact checkpoint state and excludes later history.
Participant identifiers, event identifiers, and credentials are fresh and internally consistent.
The limit is three rewinds for the root session and all rewind descendants.
The limit does not reset when the user rewinds again from a child.
The Web UI shows the remaining count below each eligible earlier NPC message.
It disables those actions after the third rewind.

The player assistance request contains `expected_revision` and `idempotency_key`.
It is available only during the player's turn in an active training session.
It does not update state before the returned text is submitted.
The Web UI submits the text through `POST /messages` after generation.
The normal parser, validation, and NPC response flow then apply.
The provider input contains the actor-safe observation and private preparation.
It excludes NPC private state and raw internal events.
The selected live route uses `Qwen3.8-Max` for this operation.
The `/llm-debug` window records this call with task name `player_assist`.

## Social rules and memory

The engine pins `human-training-v1`, `social-events-v1`, and `training-clarification-v1` in session state.
The baseline is rapport 45, credibility 60, tension 10, and patience 80.
Successful prior deals set initial rapport to 55 and credibility to 70.
The values are simulation parameters on a 0–100 scale.
They are not validated psychological measurements.

| Validated event | Change |
| --- | --- |
| `personal_interest` | rapport +3 |
| `direct_insult` | rapport −6; tension +8; patience −4 |
| `apology` | rapport +2; tension −5 |
| `admitted_deception` | credibility −6; tension +3 |
| `repetition` | patience −3 |

The classifier can propose at most two distinct events per message.
Each event must contain an exact excerpt from that message.
The engine clamps values to the scale and applies each committed revision once.
Positive personal-interest and apology events each have a two-event cap.
An apology can change state only above the initial tension baseline.
An admitted-deception event additionally requires an explicit first-person admission.
Provider failure, invalid JSON, missing evidence, or unknown event kinds cause no social change.
Firm bargaining does not count as an insult in the classifier instructions.
Classification remains probabilistic.

The active owner observation exposes the current values as `training.social_state.values`.
It exposes the latest applied change as `training.social_state.delta`.
It exposes the processed player revision as `training.social_state.source_revision`.
Legacy active sessions show a zero delta until the next processed player message.

Social state currently changes presentation tone only.
It cannot change utility, reservation thresholds, hard constraints, or confirmation rules.
The existing public conversation memory retains attributed statements and offer status.
The model does not write an unrestricted MEMORY document.
The optional personal fact is a dog named Гуффи in Russian or Goofy in English.
It is available for relevant questions and one early opportunity in the sociable profile.
The engine records disclosure only when the delivered reply contains the name.

## Clarification recovery

A parser clarification does not end a new training session.
An acceptance-confirmation opening or cancellation also does not consume a training termination allowance.
A failed HTTP 4xx participant transition does not consume this allowance.

After three consecutive clarifications, the Player API returns `clarification.recovery`.
The object contains the pinned version, one supported example, and a canonical exit message.
The Web UI and CLI show this recovery content.
An authenticated session reload shows the same recovery content while the clarification remains pending.
The service restores this content after a restart.
The learner can restate the proposal or send the exit message.
The same learner remains the next actor.
The offer and substantive counters do not change.

Benchmark sessions retain the configured bounded protocol-control behavior.
Historical terminal sessions remain terminal.

## Goal evaluation and coaching

Only a completed agreement can satisfy a numeric deal target.
The engine calculates each gap:

- `lte`: `max(0, actual − target)`.
- `gte`: `max(0, target − actual)`.
- `eq`: `abs(actual − target)`.

No agreement produces an unknown deal-term result.
The report still shows the authored BATNA outcome utility.
The coach receives the actor's brief, BATNA utility, reservation utility, preparation, result, and permitted transcript evidence.
It receives no counterpart private utility or limits.
A rational exit can be appropriate.
Free-text goals have qualitative assessments, not invented completion percentages.

Coaching uses a separate English task and a strict output schema.
The engine checks cited message identifiers.
A second model call checks factual grounding and language.
The service attaches exact excerpts after validation.
It stores provider, model, prompt version, source revision, coverage status, and validated output.
Model calls run outside write transactions.
Economic facts remain deterministic.
Semantic grounding is probabilistic and can fail.

The evidence package uses at most 80 recent message excerpts within a 28000-character selection budget.
Each excerpt contains at most 1600 characters.
The package includes at most 12 recent offer events.
`evidence_truncated` identifies reduced coverage.
The coach must disclose that limitation in its text.
The generation budget is 2200 output tokens per review call.
The classifier budget is 350 output tokens.
Each call has one transport attempt and a timeout no greater than 45 seconds.
The configured NPC timeout can impose a shorter limit.

Comparison reports observed utility and agreement outcomes.
It labels the child as informed practice.
It does not claim a causal or transferable skill improvement.
Legacy skill counters remain heuristic diagnostics.

## Qwen and CLI

Run the selected model through the existing launcher:

```sh
/bin/zsh -ic 'exec /bin/zsh scripts/run-qwen-api.zsh'
```

The launcher uses `deepseek-v4.1-flash` with thinking disabled for NPC wording.
It uses `deepseek-v4-flash-0731` with thinking disabled for grounding and social classification.
It uses `qwen3.8-max` with thinking disabled for the final review.
It reads `QWENCLOUD_PAYGO_API_KEY` from the process environment loaded by interactive zsh.
All three routes use the QwenCloud Pay-as-you-go endpoint.
Set `NEGOTIATION_NPC_MODEL=qwen-flash-character` or `NEGOTIATION_NPC_MODEL=qwen-plus-character` before the launcher to test a Character model.
No provider credential reaches the browser.
Template mode remains available without provider credentials.
Template mode produces no model-based social classifications or coaching.

Save the example training object to a private local JSON file.
The CLI can start it and operate completed sessions:

```sh
python -m clients.cli --base-url http://127.0.0.1:8172 play --scenario supplier_001 --scenario-version 6 --training-file /path/to/training.json
python -m clients.cli --base-url http://127.0.0.1:8172 coach SESSION_ID
python -m clients.cli --base-url http://127.0.0.1:8172 checkpoints SESSION_ID
python -m clients.cli --base-url http://127.0.0.1:8172 retry SESSION_ID --source-revision 2 --idempotency-key RETRY_KEY
python -m clients.cli --base-url http://127.0.0.1:8172 compare CHILD_SESSION_ID
```

Completed-session commands read `NEGOTIATION_PARTICIPANT_TOKEN`.
`retry` starts a plain interactive child session and keeps its fresh credential inside the process.
It does not print that credential.
External agents retain the common Player API.
Their English instruction template version is `natural-language-agent-v5`.
The supply branch uses `supply-agent-v2`.
New final coaching uses `goal-coaching-v4`.
Existing cached coaching retains its original result and version.
Do not combine benchmark results across changed prompt versions without identifying the difference.

## OWASP implementation boundary

Use the source-linked [OWASP recommendations](social-state-and-llm-dialogue.md#8-owasp-recommendations-and-project-application).
The implementation applies these controls:

| Risk | Implemented control |
| --- | --- |
| Prompt injection | Untrusted task data; narrow schemas; engine-owned transitions; separate grounding checks |
| Sensitive information disclosure | Separate private preparation and NPC projection; authenticated review; credential redaction |
| Improper output handling | Strict JSON parsing; evidence checks; plain React text rendering; no model-generated executable formulas |
| Excessive agency | No tools or state-write authority for classifiers, renderers, or reviewers |
| Misinformation | Deterministic outcomes; exact excerpts; hypothetical alternatives; explicit heuristic and coverage labels |
| Unbounded consumption | Input bounds; output budgets; finite timeouts; capped events; one cached review job |

This is not an OWASP certification or a proof against semantic prompt injection.
Public deployment still needs account admission, quotas, retention policy, and operational monitoring.
The model has no authority to resolve an out-of-grammar proposal or amend hidden truth.

## Verification boundary

Automated tests use isolated databases and deterministic provider fixtures.
They verify private projections, source references, failure caching, checkpoint reconstruction, fresh authentication, and comparison.
The browser check uses an isolated template-mode server.
It covers Russian setup, negotiation, report fallback, retry, and observed comparison.
Live Qwen quality for the full coaching task has not been rated.
No human learning-gain experiment is claimed.
