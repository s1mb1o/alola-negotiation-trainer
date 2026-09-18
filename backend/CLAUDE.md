# Backend guide

Read [`../CLAUDE.md`](../CLAUDE.md) and [`../AGENTS.md`](../AGENTS.md) first.

- Keep domain transitions independent from HTTP.
- Use SQLite transactions and optimistic `expected_revision` checks for mutations.
- Serialize mutations per session.
- Store public and internal event payloads separately.
- Return only actor-safe observations, histories, hints, and reviews.
- Add a backend integration test for each API contract change.
- Use an isolated temporary database in tests.

## Built-in NPC validation

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
