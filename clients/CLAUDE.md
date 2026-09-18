# Client guide

Read [`../CLAUDE.md`](../CLAUDE.md) and [`../AGENTS.md`](../AGENTS.md) first.

- Use natural-language Player API messages for humans and external agents.
- Fetch an authenticated actor view before each model call.
- Do not add raw hidden state to prompts.
- Read provider credentials from environment variables only.
- Redact credentials from errors and artifacts.
- Keep the Telegram adapter independent from a Telegram framework.
