# Project guide

Read `AGENTS.md` before you change code or specifications.

## Runtime structure

- `backend/` contains the FastAPI service and SQLite persistence.
- `frontend/` contains the React and Vite Web UI.
- `clients/` contains the CLI, provider clients, and Telegram adapter.
- `benchmarks/` contains role-swapped model evaluation.
- `examples/` contains versioned scenario definitions.
- `schemas/` contains the normative JSON Schemas.
- `docs/` contains product, architecture, protocol, and decision records.

Each implementation directory contains a local `CLAUDE.md` file.

## Dialogue documentation

- [Human training guide](docs/human-training-guide.md) and [DR-36](docs/decisions/2026-09-24_training-loop.md): implemented private preparation, shared background, social state, cached LLM coaching, checkpoint retry, and observed comparison. See the guide for verification limits.
- [Training precedents and hackathon priorities](docs/research/lct2026-task9-training-precedents-2026-09-23.md): source-linked research and proposed preparation, coaching, retry, comparison, and pilot design. No implementation is authorized by this research.
- [DR-34](docs/decisions/2026-09-23_prompt-language.md): English instructions for all application-owned LLM tasks. Runtime tasks were audited. External-agent prompt version is `natural-language-agent-v4`.
- [DR-35](docs/decisions/2026-09-23_player-background.md): configurable player background known to the NPC, including successful prior deals. The bounded implementation is in DR-36.
- [DR-33](docs/decisions/2026-09-23_goal-based-llm-review.md): final LLM analysis of goal progress and evidence-linked recommendations. The bounded implementation is in DR-36.
- [Task 9 compliance assessment](docs/research/lct2026-task9-compliance-2026-09-23.md): requirement coverage, current evidence, and proposed preparation priorities for MEMORY and STATUS. This assessment does not authorize implementation.
- [DR-31](docs/decisions/2026-09-23_human-first-negotiation.md): stored case-specific NPC greeting and human first live turn in human-versus-built-in-NPC training.
- [DR-32](docs/decisions/2026-09-23_retrieved-reply-examples.md): deterministic search over prepared reply variants for NPC wording.
- [Social state and LLM protection design](docs/social-state-and-llm-dialogue.md): broader MEMORY, STATUS, persona, and OWASP design. The implemented subset is defined by DR-36.
- [Reference implementation guide](docs/reference-supply-guide.md): bounded RU/EN composite negotiation, source-bound confirmation, optional semantic normalization, and verification limits.
- [Actual offline reference dialogue](docs/reports/2026-09-08-supply-offline-dialogue.md): four isolated API trajectories, not a live model ranking.

- [DR-29](docs/decisions/2026-09-08_reference-before-generalization.md): accepted order of one complete supply reference, then generalization.
- [Resolved supply contract](docs/reference-supply-contract.md): accepted package, preliminary negotiation, confirmation, synthetic economics, and reserve rules under DR-30.
- [Two-stage delivery plan](docs/plans/05_reference-supply-and-generalization.md): implementation order and readiness gates.
- [NPC dialogue guide](docs/npc-dialogue-guide.md): user examples, scenario authoring, and verification commands.
- [DR-27](docs/decisions/2026-09-06_conversation-continuity.md): accepted continuity and disclosure requirements.
- [DR-28](docs/decisions/2026-09-06_grounded-negotiation-dialogue.md): contextual parsing, bounded exchange selection, exact public numeric references, dialogue profiles, and evaluation boundaries.
- [Dialogue evaluation rubric](docs/dialogue-evaluation-rubric.md): offline diagnostics and source-linked human ratings.
- [Verification report](docs/reports/2026-09-06-conversation-continuity.md): completed checks and live-test limits.

## Commands

The selected LLM is `qwen3.8-max` through the QwenCloud Token Plan endpoint.
Use `QWENCLOUD_TOKEN_PLAN_API_KEY` from the user's `~/.zshrc` environment.
Run `/bin/zsh -ic 'exec /bin/zsh scripts/run-qwen-api.zsh'` from the project root.
The launcher pins the model, endpoint, and credential variable without storing the credential.

See [COMMANDS.md](COMMANDS.md) for the local start, stop, restart, and status procedures.
This Mac uses API port 8172 and UI port 8171. Do not stop the unrelated project on port 8170.

Use Python 3.11 or later.

```sh
uv sync --all-groups
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8172
uv run pytest backend/tests clients/tests benchmarks/tests
```

Use Node.js 22 or later for the Web UI.

```sh
cd frontend
npm install
VITE_API_BASE=http://127.0.0.1:8172/api/v1 npm run dev -- --port 8171
npm test
npm run build
```

## Security rules

- Keep `OPENAI_API_KEY`, `QWEN_API_KEY`, and `QWENCLOUD_TOKEN_PLAN_API_KEY` in the process environment.
- Do not send provider credentials to the browser or service API.
- Do not write provider credentials to logs, histories, reports, or benchmark artifacts.
- Derive every public observation from the authenticated participant.
- Do not expose raw scenario source or internal event payloads through the Player API.

## Common mistakes

- Write all application-owned LLM instructions and task templates in English. Keep Russian messages, exact quotes, and authored examples as separated task data. Request Russian participant-facing output for the MVP. Apply the rule to all model tasks and retry paths under DR-34.
- Do not infer private player information from shared background. Under DR-35, the NPC receives only explicitly known facts. Prior successful deals do not establish a current agreement or a new economic constraint.
- Do not turn the revision-0 NPC greeting into an offer, a hint, or a substantive turn. Keep the human as `next_actor` in human-versus-built-in-NPC training.
- Do not use the create-session response for the next agent prompt after another participant acts. Fetch the authenticated participant view first.
- Do not identify a participant by role text when `next_actor` contains an opaque participant ID. Resolve the ID through the session participant map.
- Do not add an executable scenario that only passes JSON Schema validation. Run the publication compiler too.
- Do not fill an incomplete public opening with zero, `null`, an empty string, or another placeholder. Use `opening_position` and omit each unstated term. An explicit zero is a real term value.
- Do not use NPC-only context or exact template membership as the natural-dialogue contract. Follow DR-26. Keep canonical financial messages deterministic, redact public context before truncation, and validate novel non-binding wording before delivery.
- Follow DR-27 for topic continuity. Derive bounded conversation memory from current-session public messages and events. Keep source references. A player claim or a chronological reply does not prove agreement or a resolved question.
- Follow DR-28 for contextual numeric edits. Authenticate and check revision before constructing public parse context. A numeric question or attributed quotation is not a proposal. Bind relative edits to one active public offer revision.
- Use exact attributed quote slots for non-binding numeric references. Preserve the immutable formatter version and stored display text. Do not allow raw LLM numbers to update terms.
- Keep dialogue diagnostics separate from economic utility. Do not label repeat counts or fallback rates as a human-quality score.
- Keep missing required terms `UNSPECIFIED` during focused discussion. Require a complete validated package before binding acceptance.
- Add `dialogue_reasons` only in a new immutable scenario version. Pass engine-selected reason identifiers and texts or previously delivered public reason history to the renderer. Record disclosure only after delivery. Keep the referenced private source out of the request.
- Do not treat generated NPC prose as a structured action. Never parse that prose back into negotiation state.
- Do not use benchmark sessions with hints or a difficulty other than `normal`.
- Do not use a shared participant credential across sessions.
