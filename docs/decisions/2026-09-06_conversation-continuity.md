# DR-27. Conversation continuity and authored reasons

Date: 2026-09-06.
Status: accepted for implementation through the user's request `реализуй`.

## Scope

Implement topic continuity, public conversation memory, and authored explanations.
Do not change the economic counteroffer algorithm or reservation rules.
Do not allow novel numeric output or replace canonical financial messages in this change.

## Options

1. Add prompt examples only. This does not correct the partial-offer routing failure.
2. Add deterministic topic routing, an event-derived public memory, and authored disclosure rules. This addresses continuity without giving the LLM state authority.
3. Replace action selection with an LLM negotiator. This exceeds this increment and conflicts with the current authority boundary.

Use option 2.

## Conversation memory

The service MUST derive conversation memory from durable public messages and public events in the current session.
It MUST NOT use an LLM summary as authoritative memory.
Memory MUST include a version and source message or event references.
The service MUST rebuild memory after restart without relying on process-local state.
The renderer projection MUST remain bounded.
The projection MAY retain an earlier explicit topic, postponed topics, attributed player statements, question-response references, public offer revisions, and an actual binding agreement.
An event-derived offer or agreement MUST remain distinct from a claim in participant prose.
Each remembered public offer MUST retain its lifecycle status and the public event reference that establishes that status.
Public lifecycle events MUST control the status of historical offers.
A withdrawn, rejected, superseded, accepted, expired, or terminated offer MUST NOT be presented as active.
A question followed by a reply MAY be marked `responded`. It MUST NOT be labeled `answered` solely from chronology.
Topic extraction MUST use participant text and engine-authored metadata. It MUST NOT parse generated NPC prose into negotiation state.
An LLM reply, player claim, question, or postponed topic MUST NOT become an agreement or ground truth.
The service MUST redact credentials before memory construction and truncation.
It MUST NOT include role briefs, private event payloads, hidden knowledge, utility values, or another session's memory.

## Topic continuity

An explicit request to discuss one authored term MUST take precedence over a generic request-to-discuss cue.
An incomplete valid price proposal MUST NOT force an immediate complete-package request when a focused non-binding response is available.
The engine MAY select `focused_discussion` or `acknowledge_partial_offer` before rendering.
The engine MUST preserve all omitted required terms as `UNSPECIFIED`.
The engine MUST still require a complete validated package for binding acceptance.
An explicit topic switch MUST replace the previous focus.
A postponed topic MUST remain unresolved and MAY be resumed by a later explicit request.

## Authored reasons

A role MAY define `dialogue_reasons` in a new immutable scenario version.
Each reason MUST contain `id`, `term_id`, `text`, `source_ref`, and `disclose_when`.
`source_ref` MUST reference that role's `brief.objective` or `brief.context`.
`disclose_when` MUST be `on_topic_question` in this increment.
The compiler MUST validate identifiers, uniqueness, topic references, source references, limits, and plain nonnumeric text.
The author remains responsible for semantic grounding in the referenced authored source.
Each role MAY define at most six reasons. Each reason text MUST contain at most 300 characters.
The engine MAY disclose at most two reasons per reply when the participant asks about the matching term or asks a contextual follow-up about the current topic.
The renderer MUST receive only selected reason identifiers and texts, plus previously delivered public reason history.
Previously delivered reason history MUST include the source `npc.utterance.delivered` event reference.
The renderer MUST NOT receive the referenced private source text or unselected private reasons.
Only delivered disclosures MAY enter persistent disclosed-reason history. A pending or failed render MUST NOT prove disclosure.
The renderer MUST include every text from `approved_reasons` verbatim in the reply.
It MUST reject generated text that omits or paraphrases a selected reason instead of including the exact text.
After a reason is delivered, the engine MUST NOT select it again for `approved_reasons`.
The renderer MAY use that reason from `disclosed_reasons` without verbatim repetition.
Only an exact selected reason text in the actually delivered message qualifies for `disclosed_reason_ids` in the public `npc.utterance.delivered` event.
A paraphrase alone MUST NOT prove disclosure.
Reasons MUST NOT change utility, acceptance thresholds, hard constraints, or capabilities.
Old scenario versions MUST remain unchanged and valid without reasons.

## Rendering and verification

DR-26 safety checks, canonical text, generation checks, durable claims, compare-and-swap delivery, and fallbacks remain required.
The renderer MUST receive only a validated bounded public memory, selected authored reasons, and previously delivered public reason history in addition to the DR-26 projection.
Historical render plans without these fields MUST remain readable.
Tests MUST cover Russian and English continuations, topic switches, postponed topics, memory beyond 12 transcript turns, restart, session isolation, source attribution, and false agreement claims.
Tests MUST also cover reason disclosure gates, invalid authored reasons, immutable scenario versions, and unchanged deal constraints.

Affected specifications: `docs/architecture.md`, `docs/api.md`, `docs/offer-session-protocol.md`, and `schemas/scenario-v1.schema.json`.
