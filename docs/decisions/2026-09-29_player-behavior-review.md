# DR-55: Separate player behavior review

Date: 2026-09-29.
Status: Accepted. The owner selected the separate review section.

## Decision and readiness

The product MUST assess player actions separately from the deal outcome.
The selected option adds a structured section to the existing coaching job.
The rejected option only strengthens the existing process and communication cards.
The selected option makes criterion coverage and missing evidence explicit.
The requirements and additive API contract below are ready for implementation.
No new endpoint, database migration, or numeric skill score is required.

## Behavior rubric

New coaching MUST use prompt version `goal-coaching-v6`.
New complete coaching MUST include `behavior` with version `player-behavior-v1`.
The section MUST contain a summary and exactly one item for each criterion:

| Identifier | Criterion |
| --- | --- |
| `rapport` | Context-appropriate contact and respectful conduct |
| `listening` | Questions, direct answers, and use of the counterpart's replies |
| `interest_discovery` | Discovery of needs, priorities, and constraints |
| `argumentation` | Reasons and supported objective criteria |
| `conditional_trading` | Reciprocal concessions and conditional exchanges |
| `clarity` | Clear proposals, summaries, and agreement checks |
| `plan_adherence` | Actions compared with the player's private preparation |

Each item MUST contain `criterion`, `assessment`, `evidence_refs`, `observation`, `strength`, `improvement`, `alternative_phrase`, and `next_practice`.
`assessment` MUST be `effective`, `needs_improvement`, `mixed`, or `insufficient_evidence`.
Observed assessments MUST cite at least one player message.
Each item MAY cite up to three messages, including NPC context.
The service MUST reject duplicate or unknown references.
The service MUST attach exact source excerpts after validation.
The service MUST mark proposed phrases as hypotheses.
`effective` MUST include a strength.
`needs_improvement` and `mixed` MUST include an improvement, alternative phrase, and practice task.
`mixed` MUST also include a strength.
`insufficient_evidence` MUST explain the evidence limit in `observation`.
Its strength, improvement, alternative phrase, and practice task MUST be null.
It MAY use an empty reference list when the record has no relevant message.
An empty private preparation MUST produce `insufficient_evidence` for `plan_adherence`.

## Interpretation and safety

A favorable deal MUST NOT establish effective behavior.
No agreement MUST NOT establish ineffective behavior.
The assessment MUST describe actions, not personality or psychological traits.
It MUST NOT reward a technique name or a personal-interest phrase alone.
It MUST NOT require small talk or penalize concise communication alone.
The reviewer MUST consider context and observed replies.
It MUST NOT infer causal effects from message order or a polite NPC response.
Plan adaptation MAY be appropriate. The review MUST NOT reward rigid adherence automatically.
Missing evidence MUST NOT become a failed skill.
The existing grounding call MUST check these rules for the complete response.
Schema or grounding failure MUST produce unavailable coaching, not invented fallback ratings.
The engine remains authoritative for deal terms and utility.

## API and UI

`POST /sessions/{id}/coaching` and `GET /sessions/{id}/review` retain their current access gates and cache rules.
`behavior` is optional in the response contract for historical cached reviews only.
Historical results MUST NOT be regenerated automatically.
The Web UI MUST show a separate `Поведение игрока` / `Player behavior` section.
The section MUST show qualitative labels, exact evidence, strengths, improvements, and practice.
Old complete reviews MUST show that the separate section is unavailable for that review version.
The UI MUST not convert ratings into a total score.
The section MUST support Russian, English, light theme, and dark theme.
The review call budget is 5000 output tokens. The timeout remains 45 seconds maximum.
The existing three methodology cards remain unchanged in structure.

### Missing-evidence practice guidance

The owner requested actionable guidance for insufficient-evidence criteria on 2026-09-29.
The UI MUST add a criterion-specific next-dialogue action and example phrase for these criteria.
This guidance MUST be authored product text, separate from the model assessment and its null advice fields.
It MUST be labelled as general practice, not as a finding about the recorded dialogue.
It MUST NOT change the assessment, invent evidence, or claim that the player omitted the suggested action.
Examples MUST use placeholders where facts are unavailable.
Plan-adherence guidance MUST keep private limits private.
No additional provider call or cache mutation is required.

### Provider-independent practice

The owner approved closing the Task 9 feedback gaps on 2026-09-29.
The selected implementation reuses authored guidance in a separate practice section.
It does not create fallback behavior ratings or change provider availability.
The alternative was to generate another model review after failure.
That alternative adds cost and does not provide provider-independent access.

When no complete behavior assessment is available, the UI MUST expose general practice guidance.
This includes unavailable, pending, not-requested, historical, and provider-disabled reviews.
The section MUST state that it is not an assessment of the recorded dialogue.
It MUST NOT label the player as having insufficient evidence without an assessment.
It MUST preserve the private-plan boundary and existing retry controls.
No API, cache, database, or scoring change is required.

### Bounded grounded correction

Version 6 MUST distinguish agreed commitments from completed execution.
It MUST attribute evidence to the correct actor.
It MUST NOT infer causal effects, completed preparation, or prevented risks from the final deal alone.
The grounding call MAY return bounded claim-level issues with its boolean verdict.
The issue list MUST contain at most eight items. Each item has a path of at most 100 characters and a reason of at most 600 characters.
Only `safe: true` with no issues permits publication.
The service MAY make one correction attempt after a structurally valid draft receives explicit grounding issues.
The corrected draft MUST pass the same schema, actor-evidence, sanitization, and grounding checks.
Malformed verdicts, unsupported references, provider errors, and an unsuccessful correction MUST remain unavailable.
The service MUST NOT publish rejected drafts or checker issues through the Player API.
The model MAY omit an inapplicable nullable advice field.
The service MUST normalize that omission to null before validation and output.
Advice required by the selected assessment MUST remain mandatory and nonempty.
The correction MUST use the original evidence package and treat the draft and issues as untrusted data.
The service MUST make at most four provider calls per job.
Each call retains the 5000-output-token limit and the maximum 45-second timeout.
Correction MUST NOT start after 70 elapsed seconds, keeping the job below the existing three-minute stale-job limit.
Historical cached reviews MUST remain unchanged.

This bounded correction addresses generation errors without accepting ungrounded claims.
Prompt-only correction was tested first and still produced rejected claims.
Unbounded retries and relaxed validation were rejected.
The separate authored practice section remains the provider-independent fallback.

## Verification

Tests MUST cover all criteria, duplicate criteria, invalid references, NPC-only claims, missing preparation, empty evidence, unsafe output, grounding rejection, and old cached results.
API tests MUST verify owner-only access and cache persistence.
UI tests MUST cover both languages, missing data, historical reviews, and text-only evidence rendering.
Fixture tests verify contracts. They do not establish live model quality or learning gains.
