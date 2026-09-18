# Decision Records — 2026-09-02 (review fixes)

- **Status**: implemented on 2026-09-02 from the findings of the 2026-09-02 project review. Awaiting acceptance by Alexander Shmelev. Until acceptance, the rules below are implementation facts, not accepted decisions.
- **Affected specifications**: `docs/offer-session-protocol.md`, `docs/api.md`, `README.md`, `SMOKE_TESTS.md`.

---

## DR-19. Natural-language acceptance and restated packages

**Decision.**
- The parser recognises acceptance intent from natural phrases that name the offer, the terms, or the package, in Russian and English, unless the phrase is negated.
- An acceptance phrase that states a new term value is a counteroffer, also while a confirmation is pending.
- A message that restates every term of the counterpart's complete active revision is an acceptance intent and goes through the confirmation step.
- A bare agreement word requires clarification, with or without punctuation.

**Rationale.** Four exact substrings did not cover how people write; restating the seller's numbers bound the deal without the confirmation step; a conditional acceptance during a pending confirmation committed a counteroffer at the old terms attributed to the wrong party.

## DR-20. Number words and abbreviations

**Decision.** The parser expands number words and the abbreviations `тыс.`, `тысяч`, `млн`, `thousand`, `million`, `k` to digits before term extraction. Percent words and adjectives before `недель` or `weeks` are read.

**Rationale.** LLM buyers hit a 44% clarification rate and a human message such as `110 тыс. евро` silently carried the opening price into the player's own offer.

## DR-21. Negated ending statements

**Decision.** A walk-away cue preceded by a negation inside the same sentence is ignored.

**Rationale.** `мы не уйдём из переговоров` terminated the session irreversibly.

## DR-22. Round expiry for every controller type

**Decision.** The engine evaluates `max_rounds` immediately after the action that completes the last round. A built-in NPC receives no extra action after the last round.

**Rationale.** External-versus-external sessions never expired; NPC sessions ran one action past the limit.

## DR-23. Built-in NPC binding and counteroffers

**Decision.**
- A built-in NPC binds only a package that passes every role's hard constraints.
- The NPC anchors each counteroffer on its own previous counteroffer, so its demand never rises as the player concedes.
- While an incomplete player revision is active, the NPC answers greetings and questions before it repeats the request for the missing terms, and the request names the missing terms.

**Rationale.** The NPC bound 1 300 000 against a 1 250 000 buyer cap; its price rose from 110 000 to 114 000 while the player conceded; every message received one identical template once a partial offer existed.

## DR-24. Reviews carry evidence and coaching

**Decision.** `key_moments` summarise the acting role and the package in the session language and quote the originating message. The review returns actor-specific `recommendations` derived from the deterministic skill scores and the outcome. The skill formulas are unchanged.

**Rationale.** The review listed raw event names and gave no guidance.

## DR-25. Administrative gates and statistics

**Decision.**
- A benchmark session can be created only with the administrator credential when one is configured.
- Only the recipient can reject an active offer; the proposer withdraws.
- Aggregate statistics count distinct sessions, expose `seat_count`, and hide agreement outcomes of sealed benchmark sessions.
- Administrator credentials are compared as bytes, so a non-ASCII header returns 401 instead of 500.

**Rationale.** Any client could re-seal a benchmark run; `by_model.session_count` counted seats; sealed outcomes leaked through agreement rates.
