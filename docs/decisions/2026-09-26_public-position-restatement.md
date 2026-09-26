# DR-49. Public NPC position restatement

Date: 2026-09-26.
Status: accepted and implemented.

## Context

A player can ask the NPC to state its terms.
The request can follow a rejected player counteroffer.
The current active offer can be empty at that point.
The NPC still has an earlier public position in the event history.

The reported session used these requests:

- `А какой у вас?`
- `все`
- `назови ограничения`
- `просто скажи мне их`
- `ТЫ МНЕ СКАЖИИ!!!`

The service returned generic questions instead of the public NPC terms.

## Decision

The engine MUST detect a direct request for the NPC public deal position.
The engine SHOULD resolve a short follow-up against bounded recent dialogue.
The short follow-up MUST contain a supported request form.
The recent dialogue MUST contain a deal-position topic.
A request that names one authored term MUST use the existing term-question and public-quote route.

The engine MUST select the latest public position that the NPC authored.
An active NPC offer has first priority.
The latest NPC counteroffer has second priority.
The authored NPC opening position has third priority.

The reply MUST use `public_position_restatement`.
The reply MUST use the exact engine-approved public terms.
The reply MUST be deterministic.
The reply MUST NOT call a model provider.
The reply MUST NOT create, reactivate, revise, accept, or reject an offer.
The reply MUST NOT disclose a hard constraint, utility value, reservation utility, BATNA, or private role fact.
The reply MUST describe an inactive position as historical.

A generic question about a document or an external source MUST NOT trigger this route.
A player statement about the player's own terms MUST NOT trigger this route.
A personal question that contains `your` or `ваш` MUST NOT trigger this route without a deal-position topic.

## Verification

An integration test reproduces the reported rejected counteroffer.
It checks direct, short, pronoun-based, and emphatic follow-up requests.
Each reply contains the exact public price, prepayment, and delivery terms.
The test also checks that a generic document question remains a general question.
