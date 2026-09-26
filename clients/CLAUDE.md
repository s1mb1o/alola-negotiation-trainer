# Client guide

Read [`../CLAUDE.md`](../CLAUDE.md) and [`../AGENTS.md`](../AGENTS.md) first.

- Use natural-language Player API messages for humans and external agents.
- Fetch an authenticated actor view before each model call.
- Do not add raw hidden state to prompts.
- Read provider credentials from environment variables only.
- Redact credentials from errors and artifacts.
- Keep `provider_request_observer` optional and scoped to the current context. Supply defensive copies of requests. Observer failures must not change or interrupt provider calls.
- Keep the `play --debug` pane on authenticated Player API projections and public events. Do not display raw hidden session state or credentials.
- Keep the Telegram adapter independent from a Telegram framework.
