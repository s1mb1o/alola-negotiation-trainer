# DR-28 dialogue validation

Date: 2026-09-07.
Implementation: [`backend.live_dialogue_smoke`](../backend/live_dialogue_smoke.py).
Authority: [DR-28](decisions/2026-09-06_grounded-negotiation-dialogue.md).
## Purpose and limits

The harness checks the built-in NPC training path.
A script submits natural-language messages through the Player API.
The deterministic engine selects the NPC action.
The production dialogue renderer formats or generates the response.

These checks are not a role-swapped agent benchmark.
They use `run_mode=training` and disable hints.
They exercise `guided`, `easy`, `normal`, and `expert` difficulty.
They do not rank models by price reduction, utility, or human dialogue quality.
The agent-versus-agent matrix remains a separate task.

Each trial uses a new temporary SQLite database and a new session.
The harness does not connect to the running Web UI service.
It does not modify production sessions or application defaults.
It deletes each temporary database after the trial.
Exported session identifiers are source references.
They are not replay links for the running Web UI.
Use the exported transcript and public events to review these trials.

## Current cases

The default suite is `grounded`.
Its version is `dr28-smoke-v1`.
It pins these executable scenarios:

| Language | Scenario | Version | Cases |
| --- | --- | --- | --- |
| Russian | `supplier_001` | 5 | `public_numbers`, `partial_package`, `clarification_recovery` |
| English | `office_lease_en` | 4 | `public_numbers`, `partial_package`, `clarification_recovery` |

`public_numbers` checks numerical questions, attributed quotations, and a false claim that prepayment was waived.
Questions and quotations must not create an offer or an agreement.

`partial_package` checks a focused short answer, a relative price change, a numerical question after that change, and an explicit zero prepayment.
The relative change must use the active public offer revision.
Missing required terms must remain absent.
An explicit zero must remain a real value.
The English case first rejects its complete opening offer.
This step creates the conditions for a new partial package.

`clarification_recovery` checks an ambiguous short answer and a relative change without an active baseline.
Both inputs must request clarification.
A later focused short answer must create the expected partial offer.

The default selection contains both provider targets, both languages, all four difficulties, and all three cases.
It creates 48 trial specifications.
Selecting `normal` alone creates 12 trial specifications.
These counts describe the configured coverage, not completed test results.

## Plan without provider calls

Run commands from the project root.
The default command only prints a plan:

```sh
.venv/bin/python -m backend.live_dialogue_smoke
```

Plan mode does not construct a provider or create a session.
It does not require API keys.
The plan lists scenario versions, scripts, targets, configuration identities, and destination URLs.
It also estimates a conservative provider-call bound without retries.
The bound is not a monetary cost estimate.

The default target identifiers are `gpt-5.6-luna` and `qwen3.8-max`.
These are configured identifiers, not claims that a provider currently accepts them.
Use `--openai-model` and `--qwen-model` to select exact model identifiers.
The harness does not replace these identifiers or change application defaults.

## Offline execution

Use a new output path for every run:

```sh
.venv/bin/python -m backend.live_dialogue_smoke \
  --mode offline \
  --suite grounded \
  --providers openai qwen \
  --languages ru en \
  --difficulties guided easy normal expert \
  --workers 4 \
  --output benchmark-results/dr28-offline-new-run.json
```

Offline mode uses the deterministic `OfflineProvider` fixture.
Its actual identity is `offline-fixture` / `dr28-render-contract-v1`.
The fixture passes through the production renderer, service, API, and persistence code.
It can supply exact quote tokens and deterministic grounding results.
It makes no network calls.
It does not test the quality of OpenAI or Qwen responses.

The artifact retains the selected live target separately as `target_provider` and `target_model`.
The evaluator groups the NPC under the actual fixture identity.
Do not present an offline target label as a measured model result.

## Live execution after separate consent

Live mode sends synthetic player messages and approved public renderer context to the selected provider.
It can incur API charges.
Obtain permission for the destinations, models, transmitted context, and spending limit before execution.
This documentation does not authorize live execution.

Live mode requires `--mode live` and `--max-provider-calls` from 1 to 1000.
The call limit is shared across every trial and worker.
It includes both response-generation calls and grounding-validation calls.
The provider configuration uses `max_attempts=1`.
The harness does not retry a failed invocation.
A failed invocation still consumes a call allowance.
The limit is not a dollar budget or a guarantee about provider billing.

The live provider requires `OPENAI_API_KEY` or `QWEN_API_KEY` in the process environment.
Do not put keys in command arguments or result files.
OpenAI uses the configured OpenAI API provider.
Qwen uses the token-plan compatible endpoint shown in the plan.

The following command is illustrative.
It was not executed as part of this documentation task.
Execute it only after consent and review of the plan:

```sh
.venv/bin/python -m backend.live_dialogue_smoke \
  --mode live \
  --suite grounded \
  --providers openai qwen \
  --openai-model gpt-5.6-luna \
  --qwen-model qwen3.8-max \
  --languages ru en \
  --difficulties normal \
  --max-provider-calls 116 \
  --workers 1 \
  --output benchmark-results/dr28-live-normal-new-run.json
```

For this selection, 116 is the conservative bound for generation and grounding calls without retries.
It is not an expected number of successful replies.
The count can be lower when a step requires clarification or a canonical response.
Provider failures and exhausted call allowances remain explicit results.

## Options and output safety

`--providers` selects `openai`, `qwen`, or both.
`--languages` selects `ru`, `en`, or both.
`--difficulties` selects one or more supported profiles.
`--workers` accepts 1 to 4 and defaults to 1.
`--mode` accepts `plan`, `offline`, or `live` and defaults to `plan`.
`--suite` accepts `grounded`, `contextual`, or `continuity`.
`--output` is required for offline and live execution.
An optional `--max-provider-calls` also bounds offline fixture invocations.
The fixed trial configuration uses 600 output tokens and a 30-second provider timeout.

The harness creates the output file exclusively before execution.
An existing path causes an error before any trial starts.
There is no overwrite flag.
Choose a new path if a previous run left an empty or incomplete output file.

Exit code 0 means the plan was printed or all selected checks passed.
Exit code 1 means at least one executed trial failed.
Exit code 2 indicates an argument, configuration, or output error.
Failure reports omit raw provider errors and response bodies.

## Interpret the artifact

The artifact contains `trials` and a `sessions` array.
Each session contains allowlisted public messages, events, offers, and participant provenance.
Source identifiers connect the transcript to public state transitions.
The export excludes credentials, private briefs, reviews, raw state, internal event payloads, and provider request dumps.
The export redacts configured custom credentials and credential-shaped strings before text truncation.
It rejects oversized histories instead of silently truncating the source sequence.

Each trial separates structural checks from generation status.
An expected clarification or canonical financial reply uses `expected_generation_bypass=true`.
Its `generation_succeeded` value is `null`, not a failed generation result.
An attempted generation that delivers a fallback remains a failed generation check.

Numeric-reference checks distinguish eligible references from references actually used.
A used reference must match exact display text and the active public offer source.
Its role, term value, offer identifier, and offer revision must match.
A requested quote that the model never uses fails coverage.
Eligible but unused quote slots do not establish correct attribution.

Technical success does not establish natural dialogue quality.
Diagnostics show repeats, fallback categories, and latency separately.
Missing measurements remain unknown.
Human ratings remain `null` until a reviewer labels the transcript.

`provider_calls` counts provider invocations, including failed invocations.
In offline mode, `network_calls` and `network_call_upper_bound` are zero.
In live mode, `network_calls` is `null` because the harness does not measure completed HTTP requests.
The live `network_call_upper_bound` equals `provider_calls` because retries are disabled.
An invocation can fail before an HTTP request starts.

See the verification report for the completed offline run and its limits.

## Review the exported dialogue

The existing offline evaluator reads the `sessions` envelope directly:

```sh
.venv/bin/python -m benchmarks.dialogue_quality export-scorecard \
  benchmark-results/dr28-offline-new-run.json

.venv/bin/python -m benchmarks.dialogue_quality analyze \
  benchmark-results/dr28-offline-new-run.json
```

These commands print JSON and do not call a provider.
Save the scorecard JSON in a new local file before entering ratings.
Rate relevance, continuity, attribution, and unsupported claims.
Enter a reviewer identifier and public source references for each rated reply.
Do not change the source context or digest.
Analyze completed ratings with `--scorecard`:

```sh
.venv/bin/python -m benchmarks.dialogue_quality analyze \
  benchmark-results/dr28-offline-new-run.json \
  --scorecard human-ratings.json
```

See the [dialogue evaluation rubric](dialogue-evaluation-rubric.md) for rating anchors and validation rules.
A rating of fixture replies is not evidence about a live model.

## Legacy suites

The older scripts remain available through explicit suite selection.
Their pinned scenarios do not advance with the latest catalog:

| Suite | Russian scenario | English scenario |
| --- | --- | --- |
| `contextual` | `supplier_001`, version 3 | `office_lease_en`, version 2 |
| `continuity` | `supplier_001`, version 4 | `office_lease_en`, version 3 |

Both suites use the same plan, offline, and explicit live controls.
Difficulty selection applies to these suites too.
Do not treat a legacy run as coverage of the `grounded` cases.
