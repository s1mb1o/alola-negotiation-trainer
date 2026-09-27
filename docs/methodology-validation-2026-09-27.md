# Negotiation methodology validation

Date: 2026-09-27.
Contract: [DR-51](decisions/2026-09-26_negotiation-methodologies.md).
Runtime version: `harvard-batna-voss-v1`.
Current coaching prompt version: `goal-coaching-v4`.
The initial live probe used `goal-coaching-v3`.

## Scope

The implementation applies Harvard and Voss rules to permitted NPC wording.
The engine continues to select actions and calculate economics.
The review adds separate economics, process, and communication assessments.
No dialogue method can make an invalid offer binding.

## Verification cases

| Case | Required result | Evidence |
| --- | --- | --- |
| Utility 75, BATNA 40, reservation 60 | BATNA surplus 35; reservation margin 15 | `test_batna_and_reservation_are_distinct` |
| Utility 50, BATNA 40, reservation 60 | BATNA surplus 10; reservation margin -10; below reservation | Same parameterized test |
| Utility equal to BATNA or reservation | Zero only for the equal comparison | Same parameterized test |
| No agreement | Null agreement margins; no automatic success or failure | `test_no_agreement_has_no_deal_surplus` and UI test |
| Conditional exchange | Valid package; concession linked to an improved condition | `test_conditional_exchange_policy.py` |
| Crossed hard limits or unreachable reservation | No eligible counterproposal | `test_crossed_hard_limits_and_unreachable_npc_reservation_have_no_counterproposal` |
| Scalar and supply wording | Shared method instructions; engine action and values preserved | `test_methodology.py` |
| Opening | Exact authored terms inserted by the engine | `test_grounded_opening_uses_methodology_without_changing_authored_values` |
| Grounding rejection | Safe fallback; no generated concession committed | `test_scalar_methodology_passes_grounding_or_uses_safe_fallback` |
| Missing or duplicate review dimension | Unavailable coaching; no invalid cards published | `test_incomplete_or_ungrounded_methodology_review_is_not_published` |
| Invented reference or markup | Unavailable coaching | Same parameterized test |
| Fabricated surplus | Negative grounding verdict suppresses the coaching | Same parameterized test; fixture verdict only |
| Insufficient evidence | Explicit coverage limit; actual message excerpts | `test_review_has_three_dimensions_exact_evidence_and_no_skill_penalty` |
| Technique name | No supported social event | `test_method_name_is_not_a_social_event` |
| Privacy and compatibility | No active review; own economics only; old plans and cards remain readable | Methodology, training, and OpenAPI tests |

## Reproduce local checks

Use the project virtual environment.
All API checks use temporary databases.
Fixture providers make no network calls.

```sh
.venv/bin/python -m pytest backend/tests/test_methodology.py backend/tests/test_conditional_exchange_policy.py backend/tests/test_grounded_goal_dialogue.py backend/tests/test_supply*.py backend/tests/test_npc_dialogue.py backend/tests/test_training_loop.py backend/tests/test_openapi.py
```

Run these commands from `frontend`:

```sh
npm test
npm run build
```

## Live probe plan

Status: executed after explicit user consent on 2026-09-27.
Eight provider requests were used. No retries were used.
The local results below are separate from the live findings.

Live execution needs separate transmission consent under `backend/CLAUDE.md`.
Use at most eight provider requests, including grounding.
Disable retries for this bounded probe.
Use only synthetic data.
Do not send a real transcript or call the running training server.

1. Generate a Russian supplier opening with a known prior relationship and engine-owned price and delivery placeholders.
2. Answer a player who explains that a project deadline matters. Check tentative acknowledgment and one relevant question.
3. Discuss a supply package. Check that generated prose preserves the exact immutable package.
4. Review a short synthetic transcript that ends without agreement. Check all three dimensions, exact references, and null agreement margins.

The executed methodology probe used `qwen-flash-character` for dialogue, `deepseek-v4-flash-0731` for control, and `qwen3.8-max` for review.
DR-52 changed the later default dialogue route to `deepseek-v4.1-flash`.
Record the actual model and fallback status for each case.
A provider error is not a successful generation.
An accepted fixture response does not establish live model quality.

## Live findings and correction

[Captured results](reports/2026-09-27-methodology-live.json) contain only synthetic inputs and model responses.

| Probe | Actual result |
| --- | --- |
| Opening | DeepSeek generated a valid Russian opening. The engine inserted the exact name, price, and delivery time. The text stated the prior relationship and asked one question. It closely followed the authored template. |
| Interests | Character changed `speech_act` and added text outside JSON. Format validation rejected it. The service delivered the fallback. |
| Supply package | Character invented a six-week delivery period. DeepSeek returned `safe:false`. The service delivered the fallback and preserved the exact engine package. |
| Coaching | Qwen returned three dimensions and exact references. It also claimed that an exit was economically justified without offer evidence. The original grounding pass incorrectly accepted this claim. |

The coaching defect was corrected after the first seven requests.
The service now requires `insufficient_evidence` for economics when there is no agreement and no offer evidence.
This deterministic check rejects the captured bad response before grounding.
Prompt version `goal-coaching-v4` explains that alternative utility is not rejected-offer utility.
The grounding instructions reject an unsupported economic justification in the summary or any card.
The eighth live request checked the captured bad review with these instructions.
Qwen returned `safe:false`.
The regression suite for methodology, training, and OpenAPI then passed 51 tests.

No fresh review was generated after the correction because the eight-request limit was reached.
The Character model did not pass both dialogue probes.
The live results therefore do not establish reliable dialogue quality.

## Server restart

The API was restarted on port 8172 with the existing QwenCloud launcher.
The persistent database was retained.
The API health check returned `status: ok`.
The Web UI on port 8171 returned HTTP 200.
The served OpenAPI document included `MethodologyReview` and 24 paths.

## Recorded local results

- The backend regression command above passed 347 tests before the final OpenAPI schema test was added.
- The final methodology suite, new OpenAPI schema test, and completed-agreement integration test passed 23 tests. This includes repeated checks from the regression run.
- The frontend suite passed 105 tests in 22 files.
- The frontend production build passed.
- Ruff passed for all changed Python modules and tests.
- `git diff --check` passed.
- API tests used temporary databases. The initial local checks did not restart the running server. The later user-authorized restart is recorded above.

## Limits

Local checks establish contract behavior and integration.
They do not establish that an LLM reliably recognizes a negotiation technique.
Grounding remains a model judgment for semantic claims.
The deterministic checks cover structure, references, engine values, and release boundaries.
Even a successful live probe does not establish a learning gain.
Learning effectiveness needs a separate evaluation with human learners.
