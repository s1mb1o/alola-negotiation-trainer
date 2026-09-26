# DR-39. Polite return from an unrelated question

Date: 2026-09-24.
Status: accepted.

## Decision

For a recognized unrelated question without an approved personal fact, the NPC MUST acknowledge the question politely and return to the negotiation.
The reply MUST NOT invent a personal fact or deny an unknown fact.
The reply SHOULD restate the previous negotiation question or resume the current public topic.
The reply MUST NOT repeat historical prices or imply a new agreement.
The deterministic fallback MUST support this behavior without a model call.
The service MUST store the selected fallback in the existing durable render plan.
The engine MUST provide several fallback variants. It MUST prefer a variant absent from the recent NPC history.
When all variants were used, the engine MUST prefer the least recently used variant.
Binding actions and mixed messages with negotiation content MUST retain their existing action handling.
The output validators and disclosure gates remain mandatory.

## Implementation scope

Use bounded local recognition for common personal, weather, sports, and politics questions.
Do not treat this recognizer as a general relevance classifier.
Use authored term identifiers and public conversation topics for fallback continuation.
The LLM MAY paraphrase the previous substantive NPC question without changing facts.
All internal instructions remain English. Participant text follows the session language.
The public API schema does not change.

## Rationale

Prompt instructions alone cannot repair a provider outage.
A generic negotiation fallback can ignore the actual question.
A context-aware fallback provides a polite response while preserving the engine's authority.

## Verification

Check disabled and enabled personal facts, provider failure, active topics, mixed messages, both languages, and old render plans.
Check scalar sessions and non-binding supply replies.

Implemented six variants in `backend/app/dialogue_redirect.py`.
The engine selects from recent delivered NPC history before storing the render plan.
The provider-failure tests cover the reported Russian industrial-computer case and an English scalar case.
The supply check preserves public package terms. The scalar check preserves active offers.
The full Python regression suite passed 1,074 tests with DR-40 on 2026-09-24.
