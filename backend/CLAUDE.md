# Backend guide

Read [`../CLAUDE.md`](../CLAUDE.md) and [`../AGENTS.md`](../AGENTS.md) first.

- Keep domain transitions independent from HTTP.
- Use SQLite transactions and optimistic `expected_revision` checks for mutations.
- Serialize mutations per session.
- Store public and internal event payloads separately.
- Return only actor-safe observations, histories, hints, and reviews.
- Add a backend integration test for each API contract change.
- Use an isolated temporary database in tests.
- Keep OpenAPI response contracts in `app/api_contracts.py` synchronized with routes and requests.
- Use explicit operation IDs and Bearer security dependencies. Preserve actor access checks.
- Run `pytest backend/tests/test_openapi.py`. The shared test client also validates actual JSON responses.
- See the [OpenAPI guide](../docs/openapi-guide.md) for schema generation, examples, and validation.
- `/llm-debug` uses the trace API under DR-40, DR-41, and DR-44. Loopback clients with a loopback host and matching Origin can read without a credential. Other requests require an administrator credential. Capture complete outgoing requests and retry attempts. Redact credentials before storage. Evict whole records at 200 calls or 64 MiB. Keep records in process memory. Exclude benchmark calls. Never add traces to player responses or session history.
- DR-46 separates dialogue, control, and review model profiles. Keep the engine authoritative. Route NPC prose to the dialogue provider. Route grounding, relevance, and social classification to the control provider. Route final coaching to the review provider.
- DR-59 adds `npc-relevance-v1` to new human training render plans when enabled. Keep checker input actor-safe. Permit one repair from allowlisted issue codes. Preserve the action and exact package. Repeat deterministic validation, grounding, and relevance. Keep provider I/O outside write transactions. Do not add calls to historical unversioned plans, canonical financial replies, template mode, or benchmarks.
- DR-50 permits provider-backed revision-zero wording only for a scenario version with `dialogue_strategy`. Run provider I/O before the create-session write transaction. Require exact engine-owned placeholders for the title, optional player name, and selected opening terms. Never pass the private role brief or private economics to the opening renderer.
- DR-50 also requires mixed greeting and business messages to keep the business intent. Treat concern and favorable-surprise term signals as bounded wording evidence. Never convert them into an agreement, a term value, or accepted flexibility.

## Built-in NPC validation

- DR-51 uses `app/methodology.py` for shared Harvard, BATNA/ZOPA, and Voss wording rules. Preserve the version in new render plans. Keep engine actions and canonical financial replies authoritative. New coaching requires one evidence-linked card per dimension. Read old plans and cached cards without regeneration. See [verification cases](../docs/methodology-validation-2026-09-27.md).

- Supply Stage A uses `supply-package-v1` and `supply-economics-v1`.
- Keep preliminary proposals separate from formal offers. Do not auto-accept a complete preliminary package.
- Preserve the exact actor-bound publication snapshot and its digest across reads and restarts.
- Supply `propose` permits LLM prose around a stored immutable package block. Publication and acceptance wording remains canonical.
- Optional supply normalization runs outside a write transaction. Recheck the revision before commit.
- Do not normalize explicit negation, past proposals, unsupported conditions, or protocol controls into amendments.
- Run `pytest backend/tests/test_supply*.py` after a supply change. Keep historical scalar tests passing.

- Run `python -m backend.live_dialogue_smoke` to print a plan without provider calls.
- Use `--mode offline --output <new-path>` for fixture validation through the real renderer and API.
- Live execution requires separate transmission consent, `--mode live`, and `--max-provider-calls`.
- The shared call limit includes generation and grounding. It is not a monetary budget.
- Keep actual fixture provenance separate from target provider/model labels.
- Validate numeric quotes against delivered text and active public offer revisions.
- Do not count an unexpected missing renderer call as a successful bypass.
- Export only public allowlisted data. Never export the raw Admin detail.
- See [the validation guide](../docs/dr28-dialogue-validation.md) for commands and limitations.
