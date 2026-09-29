# DR-51. Harvard, BATNA/ZOPA, and Voss

Date: 2026-09-26.
Status: implemented. Local verification completed on 2026-09-27.
Verification: [cases and limits](../methodology-validation-2026-09-27.md).

## Decision

Use one versioned methodology contract for NPC wording and training review.
Harvard supplies interests, options, objective criteria, and relationship discipline.
BATNA and reservation utility supply distinct economic reference values.
ZOPA describes mutually acceptable packages, not only a price interval.
Voss supplies optional listening and question techniques.

Options considered:

- Documentation only preserves runtime behavior but cannot improve dialogue.
- An unrestricted LLM negotiator can alter economics and violates engine authority.
- Shared wording instructions and evidence-bound review preserve engine authority and support verification.

Use the third option.
Readiness is established by the existing public dialogue contract, economic evaluator, and owner-only review policy.

## NPC behavior

The NPC MUST answer a direct question before asking another question.
It SHOULD investigate the interest behind a position.
It MAY request objective evidence without inventing market facts.
It MAY explain an exchange only when the engine has selected that exchange.
It MAY reflect a short phrase, summarize, or tentatively name a stated concern.
It SHOULD use one relevant `what` or `how` question when a question helps.
It MUST NOT diagnose emotions or repeat a technique mechanically.
Warmth, technique names, and special phrases MUST NOT earn automatic social points or concessions.

The methodology MUST NOT change action selection, utility, constraints, confirmation, or fact visibility.
Canonical financial replies MUST remain deterministic.
Scalar, composite-supply, and grounded-opening wording MUST share these rules.
New durable render plans MUST retain the methodology version.
Historical plans without a version MUST remain readable.

## Review and API

The completed owner-only `training` review MUST include `methodology`.
The field MUST contain the methodology version and an economic assessment.
The engine MUST compute agreement surplus over the learner's BATNA and margin over reservation utility.
Without agreement, both agreement margins MUST be null.
No agreement MUST NOT automatically mean failure or success.
The assessment MUST NOT infer an exact ZOPA from a transcript or expose NPC private limits.

Presentation clarification accepted on 2026-09-29:
Economic comparison labels MUST use plain language. Explain positive, zero, and negative values in scenario points.
The authored minimum MUST remain distinct from the private preparation target and the best option without a deal.
The difference MUST NOT be presented as money, a percentage, or remaining concession capacity.
Keep the formulas and API identifiers unchanged.

New methodology coaching MUST provide exactly one card for each dimension:

- `economics`: BATNA, reservation utility, and the observed outcome.
- `process`: interests, supported criteria, options, and conditional exchanges.
- `communication`: listening, direct answers, respectful firmness, and appropriate use of Voss techniques.

Each card MUST declare `observed` or `insufficient_evidence`.
Each card MUST cite actual message references.
Insufficient evidence MUST NOT be treated as a failed skill.
Without agreement and without offer evidence, the economics card MUST use `insufficient_evidence`.
The service MUST reject an `observed` economics assessment in that case.
The reviewer MUST NOT treat alternative utility as the utility of a rejected offer.
An empty offer history MUST NOT establish that no acceptable deal existed.
The grounding pass MUST reject an asserted economic justification for an exit without this evidence in any part of the review.
The grounding call MUST check claims against the cited evidence and engine economics.
The UI MUST label all three dimensions in Russian and English.
Existing cached coaching MUST remain readable.
No new endpoint or benchmark assistance is required.

## Verification

Check positive, equal, and negative BATNA margins and distinct reservation values.
Check no-agreement behavior and no-ZOPA policy rejection.
Check privacy, historical plans, provider fallback, and social-score invariance.
Check all three review dimensions and reject missing or duplicate dimensions.
Use isolated sessions for model tests.
Record actual provider failures and fallback replies separately from successful generation.
Do not claim proven learning gains from software or model checks.

## Sources

- [Harvard: principled negotiation](https://www.pon.harvard.edu/tag/principled-negotiation/).
- [Harvard: seven elements](https://www.pon.harvard.edu/wp-content/uploads/images/posts/Binder-COMPLETE-MC-Nov-20161.pdf).
- [Harvard: BATNA, reservation price, and ZOPA](https://www.pon.harvard.edu/daily/dealmaking-daily/resolving-the-first-offer-dilemma-in-business-negotiations/).
- [Black Swan Group: tactical empathy and listening](https://www.blackswanltd.com/newsletter/5-ways-tactical-empathy-can-assist-you-in-getting-what-you-want).

These sources describe methods. They do not establish the learning effectiveness of this trainer.
