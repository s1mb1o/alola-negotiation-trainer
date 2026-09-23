# Human negotiation training

Date: 2026-09-24.
Contract: [DR-36](decisions/2026-09-24_training-loop.md).
Plan: [implementation plan](plans/06_human-training-loop.md).

## Use the Web UI

1. Select a scenario and your role.
2. Select a counterpart profile and relationship history.
3. Enter optional shared background.
4. Open the private preparation card.
5. Record your goal, unacceptable outcome, possible exchanges, and questions.
6. Optionally set a numeric target for a supported scalar term.
7. Start the negotiation.
8. End the negotiation through an agreement or an explicit exit message.
9. Select **Получить разбор** after the deterministic report appears.
10. Read the evidence excerpts and proposed alternatives.
11. Select a saved decision point and start a retry.
12. Complete the retry and compare the observed results.

The UI uses Russian by default.
The UI also supports English.
Session language is independent of UI language.
Internal model instructions use English.
Russian quotes and canonical protocol phrases retain their exact text.

The private card is available only to its owner and the final coach.
The NPC receives shared background, its profile, an authored personal detail, and a derived tone.
It does not receive the private card or raw social values.
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
| `shared_background` | At most 800 characters; no instruction or economic authority |
| `personal_detail` | Enables the authored dog fact; default `false` |
| Preparation text | Four optional strings; at most 1000 characters each |
| `targets[].term_id` | A numeric primitive in the pinned scenario |
| `targets[].operator` | `lte`, `gte`, or `eq` |
| `targets[].value` | A finite number in that term's units |

All following endpoints require the participant Bearer credential.
The participant must own the training configuration.

| Method and route | Result |
| --- | --- |
| `GET /sessions/{id}/review` | Deterministic report and cached coaching status; no provider calls |
| `POST /sessions/{id}/coaching` | One cached generation and grounding job for the completed session |
| `GET /sessions/{id}/checkpoints` | Recorded human decision revisions |
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

## Social rules and memory

The engine pins `human-training-v1` and `social-events-v1` in session state.
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

Social state currently changes presentation tone only.
It cannot change utility, reservation thresholds, hard constraints, or confirmation rules.
The existing public conversation memory retains attributed statements and offer status.
The model does not write an unrestricted MEMORY document.
The optional personal fact is a dog named Гуффи in Russian or Goofy in English.
It is available for relevant questions and one early opportunity in the sociable profile.
The engine records disclosure only when the delivered reply contains the name.

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

The launcher uses `qwen3.8-max` and the user-selected Token Plan endpoint.
It reads `QWENCLOUD_TOKEN_PLAN_API_KEY` from the process environment loaded by interactive zsh.
Dialogue, social classification, and review use that selected provider.
No provider credential reaches the browser.
Template mode remains available without provider credentials.
Template mode produces no model-based social classifications or coaching.

Save the example training object to a private local JSON file.
The CLI can start it and operate completed sessions:

```sh
python -m clients.cli --base-url http://127.0.0.1:8172 play --scenario supplier_001 --scenario-version 5 --training-file /path/to/training.json
python -m clients.cli --base-url http://127.0.0.1:8172 coach SESSION_ID
python -m clients.cli --base-url http://127.0.0.1:8172 checkpoints SESSION_ID
python -m clients.cli --base-url http://127.0.0.1:8172 retry SESSION_ID --source-revision 2 --idempotency-key RETRY_KEY
python -m clients.cli --base-url http://127.0.0.1:8172 compare CHILD_SESSION_ID
```

Completed-session commands read `NEGOTIATION_PARTICIPANT_TOKEN`.
`retry` starts a plain interactive child session and keeps its fresh credential inside the process.
It does not print that credential.
External agents retain the common Player API.
Their English instruction template version is `natural-language-agent-v4`.
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
