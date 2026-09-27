# Smoke Tests

## Negotiation methodologies — DR-51

- Run `uv run pytest backend/tests/test_methodology.py backend/tests/test_training_loop.py backend/tests/test_conditional_exchange_policy.py backend/tests/test_grounded_goal_dialogue.py backend/tests/test_supply_dialogue.py backend/tests/test_openapi.py`.
- Check separate BATNA and reservation margins with positive, zero, and negative differences.
- End a session without agreement. Check null deal margins and no automatic failure label.
- Return duplicate dimensions, an invented reference, or an unsafe grounding verdict from a fixture provider. Check that coaching becomes unavailable and the deterministic report remains available.
- Check new render-plan version retention and historical plans without a version.
- Check canonical acceptance and exact supply package preservation.
- Check that a technique name cannot create a social event.
- Run `npm test` and `npm run build` in `frontend`.
- In a completed session, select **Получить разбор**. Check economics, Harvard process, and Voss communication labels in both UI languages.
- Check that insufficient evidence is a coverage limit rather than a failed skill.
- Inspect dark and light themes and a narrow viewport. The new sections use the existing review styles.
- Keep live model quality checks separate from fixture tests. Use synthetic cases and record each actual fallback.
- Use an exit-only transcript with an empty offer history. Check that an `observed` economics card is rejected before grounding, even if a fixture grounder would approve it.
- Check that the reviewer does not treat alternative utility as rejected-offer utility or infer an economically justified exit from an empty history.

## Bounded dialogue rewind and player-side assistance — DR-48

- Run `pytest backend/tests/test_training_loop.py backend/tests/test_openapi.py`.
- Run `npm test` and `npm run build` in `frontend/`.
- Start an active human-versus-NPC training session. Send enough messages to receive two NPC replies.
- Select **Вернуться сюда** under the first NPC reply. Check that the UI opens a new session with a fresh participant credential.
- Check that all later messages, offers, pending protocol state, and social changes disappear.
- Check that the selected checkpoint transcript, structured state, and offer state match the source point.
- Repeat the same request envelope. Check that it returns the same child and does not consume another attempt.
- Rewind from a child. Check that the root-lineage count increases.
- Use all three attempts. Check that every eligible rewind action is disabled and a fourth API request returns `rewind_limit_exhausted`.
- Select **Ответь за меня** on the player turn. Check a `player_assist` record in `/llm-debug`.
- Check that the provider input contains the actor-safe brief, private preparation, and public history.
- Check that the provider input contains no NPC private state, credential, or raw event payload.
- Check that the generated text is sent through `POST /messages` with the current revision.
- Return a final acceptance, final publication, or walk-away control from a fixture provider. Check that the service rejects it without changing the revision.
- Check Russian and English labels, keyboard focus, narrow layout, light theme, and dark theme.

## Relationship-aware opening greetings — DR-47

- Run `pytest backend/tests/test_easy_opening_dialogue.py`.
- Start several training sessions with `relationship: successful_history`.
- Open the new-session form. Check that **Успешные сделки в прошлом** is selected by default.
- Check that the Russian greeting uses varied wording and signals prior familiarity.
- Check that the greeting contains the public scenario title.
- Check that it contains no deal term or invented detail about a previous negotiation.
- Repeat a create request with the same idempotency key. Check that the greeting does not change or duplicate.
- Start a session with `relationship: first_meeting`. Check the neutral greeting.
- Restore an older session. Check that its stored relationship and greeting do not change.

## Grounded goal-directed dialogue — DR-50

- Run `pytest backend/tests/test_grounded_goal_dialogue.py`.
- Compile `supplier_001` version 6 and `freight_contract_ru` version 4.
- Start supplier version 6 with a human buyer, a built-in seller, `successful_history`, and `player_name: Александр`.
- Check that the revision-zero message contains the exact player name, `120 000 €`, and `8 недель`.
- Check that the message does not state a prepayment value because the opening position omits this term.
- Check that the message uses the authored production-load explanation and asks one relevant question.
- Check that revision, round, substantive-turn count, active offer, and `next_actor` stay unchanged.
- Repeat the create request with the same idempotency key. Check that no second opening render occurs.
- Inspect `/llm-debug`. Check that generation receives tokens and does not receive the exact title or public numeric values.
- Send a direct question about the NPC position. Check that the reply answers it before advancing `conversation_goal`.
- Stop the provider. Check that the deterministic grounded fallback contains the same exact public terms.
- Attempt to compile a strategy with a private numeric limit or a term absent from the opening artifact. Check that compilation fails.
- Check the same rules in an English session.
- Check that the human remains `next_actor` at revision 0.
- Send `Добрый день, мы не ожидали что вы так быстро сможете поставить оборудование, а вот цена конечно нас расстроила`.
- Check that the social greeting does not select the `greeting` speech act.
- Check that `price` is the concern and `delivery_weeks` is a favorable-surprise signal.
- Check that the NPC does not ask whether delivery must become faster.
- Accept a tentative question about a later delivery in exchange for price discussion.
- Check that the question does not state that the player has accepted this exchange.

## Live social indicators — DR-45

- Run `pytest backend/tests/test_training_loop.py backend/tests/test_openapi.py`.
- Run `npm test -- --run src/__tests__/SocialIndicators.test.tsx` in `frontend/`.
- Start a training session. Check four indicators at the bottom of the right column.
- Check that each 0–100 number matches its marker position.
- Check that each latest-message change has a separate `Δ` label.
- Send a message with one validated social event. Check the signed changes against the stored internal event.
- Send a neutral message. Check that all displayed changes become zero while the current values remain unchanged.
- Repeat the previous request with the same idempotency key. Check that the delta does not change.
- Restore the session. Check that the same values and last delta appear.
- Check Russian and English labels, narrow layout, light theme, dark theme, and accessible meter values.
- Authenticate as a participant that does not own the training configuration. Check that `social_state` is absent.

## Complete outgoing LLM requests — DR-44

- Run `pytest backend/tests/test_llm_trace.py backend/tests/test_openapi.py clients/tests/test_providers.py`.
- Run `node --test backend/tests/llm-debug-navigation.test.cjs`.
- Inspect a new trace. Compare the full request body with the fixture transport input.
- Check the system prompt, all messages, context fields, retrieved examples, URL, headers, and generation parameters.
- Check content beyond the earlier 16,000, 64,000, and 32,000 character limits.
- Check more than 32 messages and separate request links for retries.
- Check credential masking, whole-record eviction, and concurrent session isolation.
- Check that an observer failure does not change the request or interrupt generation.

## STE-style system instructions — DR-43

- Run `pytest backend/tests clients/tests benchmarks/tests`.
- Review the scalar, supply, extraction, social, coaching, and external-agent prompts.
- Check short, active sentences and consistent terms.
- Compare the rules with their previous versions. Check engine authority and untrusted-data boundaries.
- Check exact Russian protocol phrases and the requested output language.
- In a new training call, inspect **Инструкции модели** in `/llm-debug`. Check the new English wording.
- Check that historical traces retain their original request text while the trace remains available.
- Do not use fixture test results as evidence of live model quality or formal STE compliance.

## Addressable LLM messages — DR-42

- Run `node --test backend/tests/llm-debug-navigation.test.cjs` after installing the frontend dependencies.
- Select a trace. Check that the URL contains its `trace_id` and that the card is an ordinary link.
- Open an older trace by its direct URL. Reload it. Check that the newest trace does not replace it.
- Open the instruction, input message, and response section links. Check that the selected section expands.
- Use browser Back and Forward. Check the selected trace and section.
- Inspect an expired or nonexistent trace link. Check the explicit unavailable message and unchanged URL.
- Start a delayed request and select another trace before it finishes. Check that the previous response cannot replace the current selection.

## Topic returns and LLM diagnostics — DR-39 / DR-40

- Start a session with personal details disabled. Ask «Как зовут вашу собаку?». Repeat the question. Check a polite return to negotiation with different wording.
- Force a provider failure in the fixture tests. Check the same behavior and unchanged economic terms.
- Enable the authored dog fact. Check that the model still receives it. Ask a mixed personal and commercial question. Check that the commercial action remains intact.
- Run `pytest backend/tests/test_dialogue_redirect.py backend/tests/test_llm_trace.py backend/tests/test_openapi.py`.
- Open `/llm-debug` in a separate window. Check that its public shell contains no trace data or credentials.
- Open the loopback LLM page without a credential. Check that the journal loads immediately and the sign-in form stays hidden. Send a new training message. Check running and completed calls, instructions, input, response, timing, and errors.
- Check the session filter, automatic refresh, manual refresh, logout, light theme, and dark theme.
- Check that remote and foreign-origin trace requests require an administrator credential. Check that other administrator endpoints retain authentication. Check `Cache-Control: no-store` and OpenAPI schemas.
- Restart the API. Check that the trace buffer is empty and the session history is unchanged.
- Check that benchmark calls create no trace. Check that a model response with `safe: false` remains distinguishable from a provider exception.

## Brief at the start of the dialogue

- Start a training session. Check that **Ваш бриф** appears before the NPC greeting and remains in view before the first player message.
- Check the summary, objective, context, BATNA, limits, and priorities against the authenticated player's observation.
- Check that the separate **Ваш контекст** panel is absent. Check that additional scenario context remains in the opening brief.
- Check that offers, the private plan, and assistance appear beside the dialogue on wide screens and below it on narrow screens.
- Send a message. Check that the dialogue scrolls to the latest reply and does not submit the brief as a message.
- Restore a session and open a completed transcript. Check that the brief is available at the top without changing the message count.
- Check Russian and English labels. Check that the card uses the current light or dark theme.

## OpenAPI documentation — DR-37 acceptance target

Run `uv run pytest backend/tests/test_openapi.py` for the implemented automated checks.
The suite covers all 25 canonical operations. The shared backend client also validates response contracts during regression tests.

- Fetch `/openapi.json`. Validate the document against its declared OpenAPI version.
- Open `/docs`. Verify that Swagger UI loads the schema and displays the canonical `/api/v1` operations.
- Compare the schema with registered canonical operations. Verify unique operation IDs.
- Check request fields, response fields, validation limits, and applicable error schemas.
- Check declared authentication schemes and protected-operation security requirements.
- Execute a protected operation without a credential. Verify rejection by the normal API access controls.
- Execute representative requests with a permitted test credential. Validate successful and error responses against the documented schemas.
- Check actor restrictions and applicable idempotency, revision, and confirmation descriptions.
- Check synthetic examples for real credentials and hidden session state.

## Human training loop — 2026-09-24

- Run `pytest backend/tests/test_training_loop.py clients/tests/test_training.py`.
- Start a human session with shared history and a private goal.
- Verify that NPC requests and the Admin projection omit the private goal.
- Ask a personal question with a valid source-linked fixture. Repeat the same request key.
- Verify one bounded social update and one saved event.
- Complete a session. Request coaching twice and verify one cached job.
- Inject provider failure and invalid evidence. Verify that the deterministic report remains available.
- Retry a recorded decision. Verify fresh credentials, exact inherited history, and restored pending confirmation.
- Complete the child and compare the same role's observed outcome.
- Verify that benchmark and legacy sessions cannot use the training fork.
- Run `npm test` and `npm run build` in `frontend`.
- Inspect preparation, coaching failure, retry, and comparison in Russian and English.
- Check that setup has no horizontal overflow and that dark and light themes remain readable.

See the [implementation guide](docs/human-training-guide.md) for configuration, formulas, and limits.

## Selected QwenCloud Pay-as-you-go launcher

- Run `/bin/zsh -n scripts/run-qwen-api.zsh` to check shell syntax.
- Run `/bin/zsh -ic 'exec /bin/zsh scripts/run-qwen-api.zsh --help'` from the project root. Confirm that Uvicorn help appears without printing a credential or starting the service.
- After verifying the existing API process and restarting it with the launcher, check `http://127.0.0.1:8172/api/v1/health`.
- Confirm that NPC wording uses `deepseek-v4.1-flash` with thinking disabled.
- Confirm that turn control uses `deepseek-v4-flash-0731` with thinking disabled.
- Confirm that final coaching uses `qwen3.8-max` with thinking disabled.
- Confirm that all three routes use the Pay-as-you-go endpoint and `QWENCLOUD_PAYGO_API_KEY`. Do not print the key value.

## Implementation status — 2026-09-07

The lists below define the full specification acceptance target.
They do not imply that every target is implemented.

The current executable suite verifies these areas:

- bounded, versioned prepared-reply search after NPC action selection; approved reason gating and durable prompt provenance;
- seven current published scenario entries, immutable versions, and compiler rules;
- the event example schema;
- Player API actor authentication and hidden-state filtering;
- SQLite WAL persistence and restart recovery;
- same-revision concurrency and idempotency;
- complete materialized offers and immutable revisions;
- context-aware acceptance and strict confirmation;
- Unicode-safe grouped prices and proposal-clause selection;
- safe clarification for several offer packages in one message;
- explicit currency mismatch handling;
- bounded clarifications, protocol controls, hints, and rounds;
- actor-safe histories and reviews;
- benchmark run-set review sealing;
- benchmark model-score release gating and generation provenance;
- role-swapped aggregation and technical-failure attribution;
- Russian and English sessions;
- Guided, Easy, Normal, and Expert projections;
- replayable Easy built-in-NPC opening-artifact presentation at revision 0;
- partial opening positions with unresolved terms and no generated placeholder values;
- focused partial-offer dialogue, event-derived bounded memory, public offer lifecycle status, and gated authored reasons;
- numeric intent separation, relative edits against one active baseline, and short-answer term context;
- bounded exchange candidates, complete-package validation, and monotonic public monetary concessions;
- active-offer numeric quote slots, durable profiles, and engine-authored requested terms;
- separate dialogue diagnostics and offline source-attributed human scorecards;
- structured actor-safe role briefs and localized value formatting;
- CLI, Telegram adapter, OpenAI, and Qwen provider contracts;
- React session, confirmation, context, review, and statistics views.
- Russian and English UI labels, localized scenario discovery, and document metadata.
- Light, dark, and system themes with stored preferences and narrow-screen controls.
- Web UI typography tokens and minimum readable text sizes.
- administrator-authenticated safe session list and detail projections;
- Stable Web UI routes for training, progress, and Inspector views.

These target areas remain unimplemented:

- exact-revision forks;
- MESO offer sets;
- typed runtime composite terms;
- knowledge compilation, evidence extraction, and belief updates;
- fuzzy LLM policy ranking;
- server-side speech adapters.

The earlier DR-27 checks on 2026-09-06 passed 373 Python tests and 66 frontend tests in 16 files.
The frontend production build and `git diff --check` passed.
Browser restoration and catalog/state reads passed without submitting a dialogue turn.
The OpenAI continuity smoke attempt produced 11 `provider_failure` fallbacks.
It does not verify live generated replies or conversational quality.
The network retry remains blocked by automatic safety review until fresh explicit transmission consent is available.
See `docs/reports/2026-09-06-conversation-continuity.md` for the earlier DR-27 evidence and limits.
The DR-28 sections below define the new acceptance checks.
Run them with fake providers or template mode unless a live transmission is separately authorized.

The final DR-28 local run passed 655 Python tests and 70 frontend tests.
The frontend build and `git diff --check` passed.
No external model call was made for DR-28 verification.
See the [DR-28 verification report](docs/reports/2026-09-06-grounded-negotiation-dialogue.md).

The DR-28 validation-harness run on 2026-09-07 passed 761 Python tests.
The offline matrix passed 48 sessions and 232 scripted messages with four workers.
It checked supplier version 5 in Russian and office version 4 in English at all four difficulty levels.
It used offline fixtures and made zero external model calls.
The frontend was not changed or retested in this increment.
See the [validation-suite report](docs/reports/2026-09-07-dr28-dialogue-validation.md).

### Executable DR-28 smoke matrix

```sh
.venv/bin/python -m backend.live_dialogue_smoke
.venv/bin/python -m backend.live_dialogue_smoke --mode offline --workers 4 --output benchmark-results/dr28-offline-new.json
```

The default command prints a plan and constructs no provider or session.
Offline mode uses the real renderer and Player API with a local fixture provider.
An existing output file must remain unchanged. Use a new path for each run.
The [validation guide](docs/dr28-dialogue-validation.md) defines live execution prerequisites and the full command set.

- Verify unchanged offers and no acceptance request after numeric questions and false agreement claims.
- Verify short numeric answers use the requested term and preserve unresolved terms.
- Verify relative edits use the correct offer ID and increment its revision.
- Verify explicit zero remains a real proposal value.
- Verify ambiguous or missing baselines request clarification and permit later recovery.
- Require actual delivered numeric quote use in quote-request steps. Check exact text, attribution, and active source revision.
- Reject unused, replaced, or invalid quote output as coverage evidence.
- Distinguish expected clarification or canonical replies from unobserved conversational generation.
- Verify one atomic provider-call limit across concurrent cases and grounding invocations.
- Verify public export allowlists, credential redaction, source identifiers, and evaluator compatibility.
- Keep all human ratings unset until a reviewer supplies source-linked labels.
- Run legacy `contextual` and `continuity` scripts offline to preserve earlier checks.

## Specification acceptance tests

Composite-supply checks implement [DR-30](docs/decisions/2026-09-08_reference-supply-implementation.md).
Run `.venv/bin/python -m pytest backend/tests/test_supply*.py` for typed economics, source-bound parsing, confirmation, replay, optional semantic extraction, and renderer regressions.
The [offline report](docs/reports/2026-09-08-supply-offline-dialogue.md) contains four completed reference trajectories.
No live-model naturalness or model ranking is claimed.

### Versioned schemas

- Validate `examples/scenario_supplier_001.yaml` against `schemas/scenario-v1.schema.json`.
- Verify that structural schema validation passes for the declared draft state.
- Attempt to publish the draft.
- Verify that the publication linter rejects every item in `missing_required_definitions`.
- Validate and compile `examples/scenario_supplier_001_v2.yaml` as `supplier_001` version 2.
- Validate and compile `examples/scenario_supplier_001_v3.yaml` as `supplier_001` version 3.
- Validate and compile `examples/scenario_supplier_001_v4.yaml` as `supplier_001` version 4.
- Validate and compile `examples/scenario_supplier_001_v5.yaml` as `supplier_001` version 5.
- Verify that the catalog exposes version 5 and does not expose draft version 1.
- Verify that the explicit-version endpoint retains immutable versions 2, 3, and 4.
- Verify that versions 2 through 5 require `price`, `prepayment_fraction`, and `delivery_weeks`.
- Verify that the current Russian and English office-lease versions are 4 and the current freight and SaaS versions are 3.
- Compare each DR-28 scenario with its preceding version. Verify unchanged opening terms, economic truth, utility rules, reservation thresholds, and hard constraints.
- Verify that richer context, grounded reasons, conversation style, and bounded exchange grids exist only in the new versions.
- Verify that exactly one role defines exactly one of `opening_offer` and `opening_position`.
- Reject an `opening_offer` that omits a required term.
- Compile an `opening_position` that omits a required term.
- Reject an empty `opening_position`.
- Verify that the compiler does not add the omitted term.
- Verify that an explicit zero remains a real term value.
- Verify that a published scenario requires controlled composition-rule and evaluation-rule catalogs.
- Validate `schemas/event-example.json` against `schemas/negotiation-event-v1.schema.json`.

### Client parity

- Start the same human-versus-built-in-NPC session from the Web UI and CLI.
- Verify that both clients receive equivalent actor-safe observations.
- Verify that the Web UI and CLI use the same Player API.
- Run one human participant and one external-agent participant through the same natural-language message flow.
- Verify that neither participant can submit a typed public action.

### Windowed CLI

- Start `play` in an interactive terminal that is at least 72 columns by 16 rows.
- Verify that the conversation, offer panel, and message input appear without a credential.
- Verify that the conversation starts with the pinned public scenario title, your objective, and your context.
- Verify that the built-in NPC greets the human with the case title and no terms or negotiation advice.
- Start as buyer and seller. Verify that the human is `next_actor` at revision 0 in both sessions.
- Switch the right panel with `Tab`. Scroll the conversation with `Page Up` and `Page Down`.
- Start `play --debug`. Verify that a lower-right pane shows revision, round, next actor, pending state, and public NPC action metadata.
- Toggle the debug pane with `F3` or `/debug`. Scroll it with `F7` and `F8`. Verify that credentials and private NPC state never appear.
- Send a Russian message. Verify that the conversation and session revision update.
- Request a hint with `/hint` in a session with hints enabled. Verify that the coaching panel updates.
- Reach an offer confirmation. Verify that the window shows the exact offer revision and full terms.
- Change the offer before confirmation. Verify that the CLI refuses to confirm the stale revision.
- Run `play --plain`. Verify that the line-oriented JSON interface still works.
- In a 256-color terminal with ANSI color 0 mapped to gray, verify that both empty cells and ordinary text use fixed black color 16.
- Verify distinct speaker, border, and heading colors.
- With a light monochrome terminal, verify reverse video gives the interface a dark background.

### Easy opening dialogue

- Create `supplier_001` version 3 as an Easy training session with a human buyer and a built-in NPC opening seller.
- Verify that the transcript starts with one seller `opening_position` message.
- Verify that the message states only the authored price of 120 000 EUR.
- Verify that the message does not state a prepayment share or delivery time.
- Verify that the message does not describe the position as a complete package.
- Verify that the active revision contains only `price: 120000`.
- Verify that `unresolved_required_terms` contains `prepayment_fraction` and `delivery_weeks`.
- Verify that `offer.created` contains the same unresolved-term list.
- Verify that `npc.opening_utterance.delivered` contains `speech_act: opening_position` and `opening_kind: opening_position`.
- Attempt to accept the partial revision.
- Verify that the service returns HTTP `422` with `offer_not_bindable`.
- Verify that the service does not create a pending acceptance confirmation or agreement.
- Verify that `revision = 0`, `round = 1`, and `substantive_turn_count = 0`.
- Verify that the buyer remains `next_actor`.
- Verify that the active offer remains unchanged.
- Verify that the opener creates no evidence, belief update, detected signal, or probable interest.
- Verify that one `npc.opening_utterance.delivered` event exists.
- Repeat creation with the same idempotency key.
- Verify that the message and event are not duplicated.
- Configure a dialogue provider spy.
- Verify that Easy session creation makes no provider call.
- Create an Easy scenario that has a complete `opening_offer`.
- Verify that its message uses `opening_offer` and contains the exact complete public package.
- Create an Easy scenario with an explicit zero opening term.
- Verify that the active revision and presentation retain the zero value.
- Verify that Guided, Normal, and Expert creation does not add the Easy opener.
- Verify that the service does not synthesize an opener for a human or external-agent proposer.

### Web UI routes

- Open `/training` directly.
- Verify that the training view is active.
- Open `/progress` directly.
- Verify that the progress view is active.
- Open `/inspector` directly.
- Verify that the Inspector view is active.
- Navigate between all three views.
- Verify that browser Back and Forward restore the corresponding view.
- Open `/` and an unknown path.
- Verify that the Web UI replaces each path with `/training`.

### Admin Session Inspector

- Start the service with `NEGOTIATION_ADMIN_TOKEN` configured.
- Request `GET /admin/sessions` without a credential.
- Verify that the service returns `administrator_unauthorized`.
- Repeat the request with a participant credential.
- Verify that the service returns `administrator_unauthorized`.
- Request the endpoint with the configured administrator credential.
- Filter by status, scenario, language, and run mode.
- Verify pagination and the reported total.
- Open an active session detail.
- Verify that participants, transcript messages, public events, and offer revisions are present.
- Verify that credentials, credential hashes, raw session state, scenario source, private event payloads, and private review data are absent.
- Verify that the active session has `review_state: not_ready` and `review: null`.
- Verify that `dialogue_quality` is available independently from the economic review.
- Verify that missing latency and fallback observations display as unavailable in both UI languages.
- Verify that exact repeats and repeated questions show source references and a heuristic warning.
- Verify that the API human dimensions remain unrated.
- Complete one trial in an incomplete benchmark run set.
- Verify that the session has `review_state: sealed` and `review: null`.
- Complete the declared run set.
- Verify that the Inspector exposes only `reviews.public_json`.
- Open `/inspector` in Russian and English.
- Verify list filters, session selection, tabs, and pagination.
- Verify light and dark themes at 1440 by 900 pixels and 390 by 844 pixels.
- Disconnect administrator access.
- Verify that the token is removed from `sessionStorage` and is absent from `localStorage`.

### Web UI readability at 100% zoom

- Set browser zoom to 100%.
- Use a desktop viewport of at least 1440 by 900 pixels.
- Open the setup, active negotiation, confirmation, review, and statistics views.
- Verify that body text is at least 16 pixels.
- Verify that captions and metadata are at least 12 pixels.
- Verify that Russian and English text has no clipping or overlap.
- Verify the same views in the light and dark themes.
- Repeat the check with a 390-pixel-wide viewport.
- Verify that all controls remain visible and usable.

### Structured role brief

- Start one Russian session and one English session.
- Verify that `role_brief` contains `summary`, `objectives`, `context`, `batna`, `constraints`, and `priorities`.
- Verify that `role_brief` does not contain `reservation_utility`, BATNA utility, interest weights, or role data for the counterpart.
- Verify that the Web UI shows a separate localized section for each non-empty field.
- Verify that a price constraint uses the scenario currency and the UI locale.
- Verify that priority identifiers use localized labels and retain their authored order.
- Verify that the Web UI still renders a legacy string `role_brief`.
- Verify that the formatted card is readable in light and dark themes.
- Load the legacy office-lease role-brief string.
- Verify that the Web UI does not show JSON, snake-case identifiers, or supply-delivery labels.

### Office-lease vocabulary

- List the Russian and English office-lease scenarios.
- Verify that the catalog returns version 4 and that the explicit version endpoint still returns versions 1 through 3.
- Verify that version 2 uses annual rent, prepayment, and office-readiness terms.
- Submit one complete Russian package with an annual rent, a prepayment percentage, and an office-readiness period.
- Submit the equivalent English package.
- Verify that both packages compile into the three expected terms.
- Start a human-landlord session in each language.
- Verify that the NPC mentions office readiness or move-in and does not mention product delivery.
- Verify that the role brief and offer panel show localized labels, currency, percentages, and week units.

### Context-aware agreement

- Submit `Согласен на 50% предоплаты` while a complete offer is active.
- Verify that the engine does not classify the message as complete acceptance.
- Submit `Согласен, если доставка будет раньше`.
- Verify that the engine creates a counteroffer.
- Submit `Согласен` when one complete active offer exists.
- Verify that the bare phrase still requires clarification and cannot bind an agreement.
- Submit `Согласен` when the context can refer to one condition or the complete offer.
- Verify that the response is `clarification_required`.
- Submit an unambiguous complete-offer acceptance intent.
- Verify that the response is `confirmation_required` and shows the complete materialized offer.
- Confirm in natural language.
- Verify that the exact active revision becomes immutable and the session enters `agreement_reached`.

### Offer revisions and MESO

- Submit a delta against an active offer.
- Verify that the engine stores a new immutable complete offer revision.
- Verify that unchanged terms carry from the base revision.
- Unset an authored optional term in natural language.
- Verify that the materialized revision removes the term.
- Attempt to unset a required term.
- Verify that validation fails.
- Counter an active offer.
- Verify that the referenced revision becomes `superseded`.
- Attempt to accept the superseded revision.
- Verify HTTP `409`, `offer_not_active`, and the post-recording session revision.
- Create an explicit MESO offer set.
- Accept one alternative.
- Verify that every sibling alternative expires.
- Withdraw an active offer as its proposer.
- Verify that the withdrawn revision cannot be accepted.
- Attempt to withdraw an accepted offer.
- Verify that the engine rejects the transition.

### Clarification and retries

- Submit semantically ambiguous text.
- Verify that the server records the message and ambiguity but does not change the deal or consume a round.
- Verify that `next_actor` remains the same participant.
- Submit a clarification response that resolves to a substantive action.
- Verify that only the resolved action consumes a turn.
- Force one parser execution failure.
- Verify that the parser runs one retry.
- Force the parser retry to fail.
- Verify that the server records `parser_failure`, preserves deal state, and returns `clarification_required` with reason `parser_unavailable`.
- Force one configured NPC dialogue-provider attempt to fail.
- Verify that the server immediately uses the precomputed actor-safe deterministic template without duplicating the committed action.
- Submit a message that rejects one price and proposes another price.
- Verify that the engine commits the explicit proposal price.
- Use U+202F as the price digit-grouping character.
- Verify that the engine commits the complete numeric value.
- Submit two alternative packages in one message.
- Verify that the engine returns `multiple_offer_candidates` without changing the active offer.

### Revision and idempotency

- Repeat session creation with the same `idempotency_key`.
- Verify that the server returns the original session instead of creating another session.
- Submit a mutating request with a stale `expected_revision`.
- Verify HTTP `409` with `revision_conflict` and no new event.
- Repeat a successful request with the same `idempotency_key`.
- Verify that the server returns the stored response without another event.
- Repeat a stored `offer_not_active` request with the same `idempotency_key`.
- Verify that the server returns the same stored domain-error response without another event.

### Turn and terminal state machine

- Complete one default two-party round.
- Verify that both participants committed a substantive action before the round increments.
- Verify that a valid `pass` consumes a turn only when scenario policy permits it.
- Verify that the built-in NPC runs automatically only when the session is active and it is `next_actor`.
- Verify that agent-versus-agent mode commits at most one participant action per request.
- Reach scenario `max_rounds` without another terminal transition.
- Verify that the session enters `expired` after the complete round.
- Submit an unambiguous walk-away message.
- Verify that the session enters `walked_away` without a second confirmation.
- Call `/close` as a participant.
- Verify that authorization fails.
- Call `/close` as an administrator.
- Verify that the session enters `aborted` with an administrative reason.
- Force a recoverable processing failure after an authoritative action commit.
- Verify that the session remains active and resumes from the last committed revision.
- Exhaust the configured retry budget.
- Verify that the session enters `technical_failure` without duplicating an action.
- Generate a review from each terminal state.
- Verify that every terminal state has a review and terminal reason.

### Exact-revision fork

- Fork from `source_revision = N`.
- Supply the current parent `expected_revision` and a new `idempotency_key`.
- Verify that child initial revision is `N` and its first local event uses `N + 1`.
- Verify that offer IDs, offer lifecycle state, `next_actor`, pending protocol state, and delivered participant information match parent state after revision `N`.
- Override model policy as an authorized training orchestrator.
- Verify that the child records the override and the parent remains unchanged.

### Russian-first language support

- Start `supplier_001` version 3 with language `ru`.
- Verify that the session, prompts, transcript, and rendered messages record the language.
- Verify that structured term and event identifiers do not contain localized labels.

### Executable supplier scenario

- Verify that the version 3 opening position contains only 120 000 EUR.
- Verify that prepayment and delivery are unresolved.
- Verify that no API, transcript, event, replay, or Inspector projection invents values for these terms.
- Submit 111 000 EUR, 50% prepayment, and three weeks as one complete package.
- Verify that both roles pass their hard constraints and reservation thresholds for this package.
- Verify that each participant receives only its own brief and Expert distractor.
- Verify that the NPC uses industrial-computer supply wording.
- Submit a package that also contains a split schedule or contingent reserve.
- Verify that the engine returns `unscored_proposal` clarification and does not change the active offer.
- Start immutable version 2 through the explicit-version API.
- Verify that its complete opening offer remains 120 000 EUR, zero prepayment, and eight weeks.

### Reservation boundary

- Evaluate a valid deal with utility equal to `reservation_utility`.
- Verify that the built-in policy treats the deal as acceptable.
- Evaluate a deal below `reservation_utility`.
- Verify that the built-in policy rejects the deal.
- Confirm the same below-reservation deal as a human participant and as an external-agent participant when every hard constraint passes.
- Verify that the engine permits the confirmation and that the review identifies the economic failure.
- Attempt to confirm a deal that violates a hard constraint as each controller type.
- Verify that the engine blocks binding for every controller type.

### Intentional no-ZOPA scenario

- Load a scenario that declares an intentional no-ZOPA training objective.
- Verify that the linter reports an empty ZOPA without rejecting the scenario.
- Verify that a rational walk-away can receive a successful outcome score.

### Unauthored term

- Submit a composite split-delivery schedule built from authored primitives and capabilities.
- Verify that the engine validates the typed tree and uses authored evaluation rules.
- Submit a proposal outside the compiled term grammar.
- Verify that no LLM or engine component assigns utility to the proposal.
- Verify that the proposal cannot become part of a binding agreement.
- Verify that the NPC may clarify, discuss, or decline it without changing deal utility.

### Knowledge and belief state

- Compile a high-level authored external-offer entity.
- Verify that the compiler creates stable atomic knowledge-item definitions.
- Extract evidence from a participant message.
- Verify that the extractor cannot write belief confidence or ground truth directly.
- Apply the validated evidence through the versioned belief-update policy.
- Verify that the event records confidence before and after with evidence event IDs.
- Verify that UI labels are derived from confidence and do not write state.
- Create an ungrounded participant hypothesis.
- Verify that the engine creates a stable `hypothesis_id` and deterministic initial confidence from evidence.
- Verify that it remains belief state and cannot change reality, constraints, utility, or deal validity.
- Replay the session.
- Verify that replay recreates hypotheses and reapplies stored evidence and belief transitions without an LLM.

### NPC action authority

- Supply a fuzzy ranker result that prefers an illegal action.
- Verify that the engine rejects the ranking and selects only a legal action.
- Verify that the dialogue generator receives no raw hidden facts or secret identifiers.

### Built-in NPC dialogue rendering

- Run the service without `NEGOTIATION_NPC_PROVIDER`.
- Verify that the built-in NPC uses deterministic templates.
- Configure `NEGOTIATION_NPC_PROVIDER=template`.
- Verify that behavior is equivalent to the default.
- Configure OpenAI with an empty `NEGOTIATION_NPC_MODEL` and `NEGOTIATION_NPC_TEMPERATURE`.
- Verify that the renderer uses `gpt-5.6-luna` and omits `temperature` from the provider request.
- Configure Qwen with an empty `NEGOTIATION_NPC_MODEL` and `NEGOTIATION_NPC_BASE_URL`.
- Set ambient `QWEN_BASE_URL` to a different endpoint.
- Verify that the built-in NPC renderer uses `qwen3.8-max` and the QwenCloud Token Plan endpoint.
- Verify that the built-in NPC renderer ignores ambient `QWEN_BASE_URL`.
- Configure a fake OpenAI or Qwen dialogue provider.
- Verify that the engine selects and persists the NPC action before provider rendering.
- Verify that the provider call occurs outside every SQLite write transaction.
- Verify that the renderer receives a dedicated allowlisted `NpcDialogueRequest`.
- Verify that the request does not contain a raw observation, raw scenario source, role brief, session state, private event payload, review, constraint, BATNA value, utility value, reservation value, knowledge truth, distractor truth note, participant credential, or provider credential.
- Verify that renderer context contains at most 12 public messages from both participants and 1,000 characters per message.
- Verify that the latest participant message enters the renderer request as untrusted context.
- Verify that the request includes only the public scenario title, NPC role identifier, labels for missing terms, focused term identifiers, bounded public memory, and selected or previously delivered reasons in addition to the approved rendering fields.
- Verify the DR-28 profile identifiers, requested-term metadata, and active-only numeric references against the checks below.
- Put participant-token, Bearer-token, OpenAI-key, and Qwen-key canaries in participant text.
- Put known administrator and custom provider-key canaries in participant text.
- Verify that credential values become `[REDACTED_CREDENTIAL]` before parsing, truncation, persistence, and provider submission.
- Insert a legacy public message that contains a credential canary.
- Verify that context construction redacts the stored message before truncation and provider submission.
- Put `prepayment_fraction` next to a credential canary.
- Verify that the credential is redacted and `prepayment_fraction` remains unchanged.
- Verify that the request contains at most six approved reply options and 4,000 option characters in total.
- Verify that each approved reply option contains at most 1,200 characters.
- Verify that approved reply options are engine-authored and do not interpolate or quote raw transcript text.
- Put distinct hidden canaries in each forbidden source.
- Verify that no canary enters the provider request, transcript, event payload, response, or log.
- Put instruction-like text in the public transcript.
- Verify that the text remains untrusted conversation data and cannot change the approved speech act or terms.
- Return one approved reply option without changes.
- Verify that the service accepts the option for the approved non-binding speech act.
- Verify that an exact engine-authored option does not require a grounding check.
- Return a short contextual paraphrase that is not an approved reply option.
- Approve that reply through the separate grounding check.
- Verify that the service delivers the novel reply without changing structured state.
- Reject a novel reply through the grounding check.
- Return an invalid grounding response or fail the grounding provider call.
- Verify that each failed check delivers the precomputed fallback.
- Return unsupported commercial claims without digits, such as `Доставка бесплатно` or `We waive prepayment`.
- Return a new numeric term, a credential, or a claim that an agreement exists.
- Verify that unsafe output is not delivered, persisted, or parsed into state.
- Return a different speech act from the fake provider.
- Return an unexpected field, speaker, tool call, URL, or markup block.
- Return empty and over-length output.
- Verify that the deterministic validator rejects each output and delivers the precomputed fallback.
- Trigger acceptance, rejection, and complete counteroffer speech acts.
- Verify that each speech act bypasses the provider.
- Verify that each binding message uses the canonical deterministic template and canonical engine-approved terms.
- Force provider timeout, transport failure, invalid JSON, and output-contract failure.
- Raise a built-in socket `TimeoutError` from the HTTP client.
- Verify that the adapter returns the safe `ProviderError("Provider request timed out")` without the raw socket detail.
- Verify that each failure produces one deterministic fallback and leaves the session usable.
- Verify that no API response contains a raw provider output, prompt, provider error body, or credential.
- Crash after durable NPC intent persistence and before provider delivery.
- Retry the render identity.
- Verify that the service does not duplicate the NPC action or public message.
- Start two service instances against one SQLite database.
- Submit the same pending render job through both instances.
- Verify that the atomic claim permits only one render attempt, including its generation and grounding-check calls.
- Verify that the losing request returns HTTP `409` with `npc_render_pending`.
- Restart the service without retrying the original HTTP request.
- Verify that startup recovery delivers the precomputed fallback exactly once.
- Verify that a pending render blocks a new participant message, hint, and administrative close.
- Create a session in which the built-in NPC starts with a binding action.
- Verify that creation uses one canonical deterministic message in the create transaction.
- Verify that creation does not create a render job or call a provider.
- Start two sessions with a barrier fake renderer.
- Verify that both provider calls run concurrently.
- Verify that each request contains only its own session, actor, dialogue, and canary data.
- Run greetings, follow-up questions, and priority questions in Russian and English.
- Verify that the NPC answers the immediate question and does not request a complete package after every message.
- Tell the NPC that it previously promised an unauthored concession.
- Verify that this participant assertion does not become an approved fact or a binding term.
- Verify that unspecified opening terms remain unspecified throughout ordinary conversation.
- Review sample generated replies manually because the semantic check is probabilistic.

### Conversation continuity and authored reasons

These targets cover DR-27.
The automated continuity checks passed within the 373-test Python suite.
Live generated-dialogue and manual language-quality assessment remain unverified in this increment.

- In `supplier_001` version 4, send `Давайте обсудим только цену`, then `Предлагаю 105 000 евро`.
- Verify that the engine selects a focused non-binding reply and does not immediately require a complete package.
- Verify that prepayment and delivery remain `UNSPECIFIED` and the partial offer cannot bind.
- Repeat the topic continuation in an English scenario.
- Use a request with both a generic discussion cue and a specific term. Verify that the specific term determines the focus.
- Postpone prepayment, discuss price, then explicitly resume prepayment.
- Verify that the postponed term remains unresolved and the explicit switch changes the focus.
- Add more than 12 public transcript turns after an explicit topic or postponed-topic request.
- Verify that bounded memory retains the relevant topic with its original source reference.
- Restart the service. Verify that rebuilding from durable messages and public events produces the same memory.
- Add a private event, a hidden canary, and a message in another session. Verify that none enters the memory projection.
- Add credential canaries to a legacy public message. Verify redaction before memory construction and truncation.
- Assert that the NPC previously accepted a term. Verify that memory records an attributed player statement and no agreement.
- Ask a question and send an unrelated reply. Verify that chronology can mark it `responded`, but not `answered`.
- Verify that public offer revisions and an actual agreement cite authoritative public events.
- Counter, reject, withdraw, accept, expire, and terminate public offers. Verify that memory retains each resulting lifecycle status and its source event reference.
- Verify that memory and renderer input never identify an inactive historical offer as active.
- Verify the memory version, source references, and bounds: 8,000 serialized characters, one current topic, 12 postponed topics, six statements, four questions, four offers, and 400 characters per statement or question.
- Load a historical render plan without memory or reason fields. Verify compatible empty defaults and normal recovery.
- Ask about an authored term in Russian and English. Verify that the engine selects at most two matching reasons.
- Ask a contextual follow-up about the current topic. Verify that the same disclosure gate applies.
- Send a greeting or ask about another term. Verify that unrelated reasons are absent from the renderer request.
- Verify that the request contains selected reasons and previously delivered public reason history without private source text or unselected private reasons.
- Reject reasons with duplicate or invalid identifiers, unknown terms, invalid source references, unsupported disclosure gates, numeric text, excessive text length, or more than six reasons per role.
- Fail rendering before delivery. Verify that a pending or failed render does not record disclosure.
- Deliver a reply with an exact selected reason text. Verify that `npc.utterance.delivered` records its identifier once.
- Generate a paraphrase without the exact selected reason text. Verify that validation rejects the candidate before delivery. Verify that the delivered fallback contains the exact selected text and records only that actual disclosure.
- Test disclosure bookkeeping separately with a nonmatching delivered string. Verify that it cannot record the selected reason identifier. Do not treat this bookkeeping test as a permitted renderer path.
- After a reason was delivered, ask whether the corresponding term was waived. Verify that the reason remains in disclosed history without mandatory verbatim repetition or a new waiver.
- Verify that reasons do not change utility, reservation rules, hard constraints, or capabilities.
- Evaluate connected sample dialogues for relevance, continuity, repeated questions, and unsupported claims. Record this assessment separately from output-validation and fallback counts.

### Grounded numeric interpretation (DR-28)

Use template mode or an injected fake provider for these checks.
Repeat each supported case in Russian and English.

- Ask `Почему цена 120000 EUR?` and `Why is the price 120000 EUR?`.
- Verify that no offer revision changes because of the quoted number.
- Report the counterpart's price and include a separate explicit proposal clause.
- Verify that only the proposed clause supplies new terms.
- Send a negated or historical price without a new proposal. Verify that it does not become an offer.
- Propose `Снизить цену на 10000 EUR` against a unique active price of 120000 EUR.
- Verify a price of 110000 EUR and the active baseline ID and revision.
- Repeat with a percentage reduction. Verify the result against the active baseline.
- Remove the baseline or refer to a previous offer. Verify clarification without term changes.
- Use multiple numeric referents, unsupported arithmetic, mismatched currency, and ambiguous units. Verify clarification.
- Establish a price topic and send `105 тысяч` or `105 thousand`.
- Verify a price proposal only when the term is unambiguous.
- Send a short number without a topic. Verify `numeric_answer_requires_term`.
- Supply conflicting focus and requested-term context. Verify clarification.
- Persist an engine-authored `requested_term_id` through a delivered NPC event.
- Restart the service and send the short reply. Verify the same term resolution.
- Change only generated NPC wording. Verify that it cannot select another numeric term.
- Send stale-revision and wrong-participant requests. Verify rejection before parser context construction.
- Verify that a question or quotation matching the full active package does not bypass acceptance confirmation.

### Validated conditional exchange and profiles (DR-28)

- Compile all seven new scenario versions and compare earlier-version file hashes.
- Verify that the earlier economic truth, utility rules, hard constraints, and opening terms remain unchanged.
- Reject grids with unknown or optional terms, duplicate values, booleans, invalid values, or more than 512 packages.
- Submit a complete package that permits an authored price-for-prepayment or price-for-timing exchange.
- Verify that the selected package passes every role's hard constraints and the NPC reservation utility.
- Verify that the nonmonetary change provides the required NPC utility benefit.
- Change only counterpart private utility in an isolated test fixture. Verify that selection does not optimize it.
- Submit successive counters. Verify that a previous public monetary concession is not reversed.
- Submit an incomplete price proposal. Verify that missing terms remain unresolved and no grid completes them silently.
- Use a scenario without an exchange grid. Verify validated fallback behavior.
- Verify that the public exchange explanation contains only the selected public terms and no private utility.
- Compare Guided, Easy, Normal, and Expert request profiles under the same pinned scenario.
- Verify that guidance and requests for grounds differ without changing hidden truth or acceptance thresholds.
- Verify the three allowlisted conversation styles. Reject unknown styles.
- Confirm that benchmarks still require Normal difficulty and disabled assistance.
- Preserve the Easy-only canonical create-time opening behavior.

### Active numeric references and recovery (DR-28)

- Build a request with at most 12 active-offer slots named `quote_a` through `quote_l`.
- Verify the offer ID, revision, proposer role, term, finite value, currency, exact display text, and formatter version.
- Return `[[quote_a]]` in a fake provider reply. Verify exact localized attribution and numeric formatting after substitution.
- Verify that raw generated numbers still fail validation even when the same value exists in the transcript.
- Reject unknown, repeated, altered, inactive, and unbound slot references.
- Reject a slot that does not match the request currency or the active offer revision.
- Verify that accepted, superseded, rejected, withdrawn, expired, and closed offers cannot supply slots.
- Verify that an omitted opening term has no slot.
- Use decimal amounts and percentages. Verify that the formatter preserves the exact value.
- Verify the 400-character display bound and the 1,200-character reply bound before and after substitution.
- Append an unauthorized promise, waiver, or agreement assertion to a valid quote. Verify rejection.
- Reject a novel resolved reply through the grounding check. Verify deterministic fallback.
- Verify durable storage of numeric references, profiles, and requested-term metadata before provider I/O.
- Restart or race two workers. Verify one delivery for the original render ID and revision.
- Load a legacy render plan without DR-28 fields. Verify Normal/pragmatic/empty defaults and normal recovery.

### Offline dialogue evaluation (DR-28)

Follow the [dialogue evaluation rubric](docs/dialogue-evaluation-rubric.md).
Use public redacted exports only.
The CLI does not call a model provider.

```sh
.venv/bin/python -m benchmarks.dialogue_quality export-scorecard public-sessions.json
.venv/bin/python -m benchmarks.dialogue_quality analyze public-sessions.json
.venv/bin/python -m benchmarks.dialogue_quality analyze public-sessions.json --scorecard human-ratings.json
.venv/bin/python -m benchmarks.dialogue_quality analyze benchmarks/fixtures/dialogue_quality_cases.json
```

- Save the scorecard output and rate selected replies with a reviewer ID and evidence source IDs.
- Verify that all four dimensions start as `null`.
- Enter one rating and leave other dimensions unrated. Verify sample counts and partial coverage.
- Reject a rating outside 0–4, a boolean rating, a duplicate source, an unknown source, and an unknown rubric version.
- Modify exported context without re-exporting. Verify that the source check fails.
- Compare distinct providers, languages, roles, prompt versions, and scenario versions. Verify that groups do not merge incompatible metadata.
- Verify that missing configuration metadata does not establish benchmark comparability.
- Detect the deliberate repeated questions in the synthetic Russian and English corpus.
- Verify that the report labels repetitions as heuristics and does not invent a humanity score.
- Verify missing latency and fallback measurements remain unavailable.
- Verify canonical non-generation replies do not enter generation denominators.
- Put unknown provider errors, credentials, and private payload canaries in excluded fields. Verify they are absent from the output.
- Open Inspector diagnostics in Russian and English, light and dark themes.
- Verify that historical responses without `dialogue_quality` display an unavailable state.
- Verify that API diagnostics do not release a sealed benchmark review.

### Hidden-state release

- Request observations, history, metrics, and review during an active session.
- Verify that every response uses an actor-safe projection.
- Complete a training session with a selective reveal policy.
- Verify that the review releases only configured items and records the reason.
- Run a benchmark set.
- Verify that hidden review data remains sealed until the run set is finished.

### Benchmark integrity

- Create repeated benchmark trials with a fixed run configuration.
- Verify that each independent trial uses a fresh session.
- Verify that each tested agent plays both roles.
- Verify that hints and training assistance are disabled.
- Verify that a forked session is rejected as an independent benchmark trial.

### Future speech adapters

- Convert speech to text through STT before parsing.
- Verify that the canonical stored input is text plus structured events.
- Convert an actor-safe public message to audio through TTS.
- Verify that TTS does not receive raw hidden state.

### Review fixes 2026-09-02

- Submit `Принимаю ваше предложение целиком.` while the counterpart's complete offer is active.
- Verify that the response is `confirmation_required`.
- Submit a message that restates every term of the counterpart's complete active offer.
- Verify that the response is `confirmation_required` and that no new offer revision is created.
- Submit `Принимаю предложение, если цена 1 250 000 рублей.` while a confirmation is pending.
- Verify that the engine commits a counteroffer at 1 250 000 attributed to the sender.
- Submit `Согласен.` and `Договорились.` as complete messages.
- Verify that both return `clarification_required`.
- Submit `Готовы дать 110 тыс. евро, предоплата 30 %, срок 6 нед.` and `Предлагаю сто десять тысяч евро, предоплата тридцать процентов, поставка шесть недель.`.
- Verify that both produce the package price 110000, prepayment 0.3, and six weeks.
- Submit `Мы не уйдём из переговоров и не скажем, что сделки не будет.` followed by a package.
- Verify that the session stays active and the package becomes a counteroffer.
- Submit a price-only offer in `supplier_001` version 3, then ask `Какие условия для вас важнее всего?`.
- Verify that the NPC acknowledges the partial offer and then answers the priority question without repeatedly requiring a complete package.
- Submit a complete package above the buyer's hard price cap to a built-in NPC seller.
- Verify that the session does not reach `agreement_reached`.
- Submit three rising buyer packages to a built-in NPC seller.
- Verify that each NPC counter price is not higher than the previous NPC counter.
- Run an external-versus-external session past `max_rounds`.
- Verify that the session enters `expired` on the action that completes the last round and that a built-in NPC receives no action after it.
- Submit `Отклоняю предложение.` as the proposer of the active offer.
- Verify that the response is HTTP `409` with `offer_not_owned`.
- Create a `run_mode: benchmark` session without the administrator credential while `NEGOTIATION_ADMIN_TOKEN` is configured.
- Verify that the response is HTTP `401`.
- Send a non-ASCII administrator Bearer credential.
- Verify that the response is HTTP `401`, not `500`.
- Read `/stats` while one benchmark trial of a two-trial run is terminal.
- Verify that its agreement outcome is hidden and that `by_model[].session_count` counts sessions, not seats.
- Open the review of a completed session.
- Verify that each key moment names the acting role and the package, quotes the originating message, and that `recommendations` is present.

### Web UI fixes 2026-09-02

- Stop the backend, send a message from the Web UI, then restart the backend.
- Verify that the composer offers Discard as well as Retry, and that Discard keeps the draft and unlocks the composer.
- Reload the page during an active session.
- Verify that the same session, offer card, and pending confirmation or clarification reappear without a new session.
- Click "New session" during an active session.
- Verify that a confirmation dialog appears first.
- Reach the binding confirmation card.
- Verify that prices show the scenario currency, that the revision label is localized, and that an explicit zero prepayment shows `0%`.
- Request a hint while a message is being sent.
- Verify that the hint button is disabled until the send completes.
- Open Progress.
- Verify that no fixed "100%" badge is shown and that service-wide totals and this-browser history are labelled separately.
- Switch the UI to Russian and open the inspector and the negotiation workspace.
- Verify that no English labels remain ("Session Inspector", "Review", "Benchmark", "Participant Seller", "MESO" alone).
- Complete a session and open the review.
- Verify that each key moment shows a quoted message and that a recommendations list is present.

## Retrieved few-shot replies

- Run `.venv/bin/python -m backend.reply_rag_smoke`. Check that it prints four cases and makes no provider call.
- Run the same module with `--mode offline --max-provider-calls 16 --output <new-path>`. Check both arms for every case.
- Enable the NPC personal detail in a SaaS training session. Ask `Как зовут вашу собаку?`. Check the reply against the authored fact.
- Disable the personal detail in a new session. The retrieved examples MUST NOT supply the dog fact.
- Ask about advance payment and launch. Retrieved explanations MUST require the current engine-approved reason texts.
- Reopen a stored render plan from library version 1. Its selected examples MUST remain unchanged.
- For an authorized live comparison, use `--mode live` with the same bound. Review delivered replies separately from fallback and latency.
