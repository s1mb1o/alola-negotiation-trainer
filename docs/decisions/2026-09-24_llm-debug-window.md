# DR-40. Separate LLM diagnostics window

Date: 2026-09-24.
Status: accepted.
Local access and capture prerequisites are superseded by [DR-41](2026-09-24_local-llm-debug-access.md).
Content bounds and header capture rules are superseded by [DR-44](2026-09-25_complete-llm-requests.md).

## Decision

The service MUST provide a separate diagnostics page at `/llm-debug`.
LLM trace data MUST require the administrator Bearer credential.
Participant credentials MUST NOT grant access.
The Player API MUST NOT include LLM traces.
The recorder MUST redact known credentials before truncation or storage.
The recorder MUST NOT capture HTTP authorization headers or raw provider exception messages.
The recorder MUST use bounded process memory. It MUST NOT write trace contents to disk.
The recorder MUST exclude benchmark calls.
Capture MUST require `NEGOTIATION_LLM_TRACE=true` and a configured administrator credential.
Trace API responses MUST use `Cache-Control: no-store`.
The API MUST document trace operations in OpenAPI.

## Scope

Capture application-level provider calls associated with an existing training session HTTP request.
Include dialogue generation, grounding, social classification, coaching, and optional supply extraction.
Show instructions, message input, response text, model, duration, token usage when available, and safe failure metadata.
Show running calls before the provider responds.
Keep at most 200 records per process. Redact and bound each record.
Do not reconstruct earlier provider traffic from a transcript or a render plan.
Do not count successful provider completion as successful dialogue validation.
Canonical template replies make no provider call and create no trace.
The diagnostics view does not change engine decisions or session history.

The local Qwen launcher enables capture by default.
If the administrator credential is missing, the launcher creates a random local credential in `.local/llm-debug-admin-token` with mode `0600`.
The directory is excluded from Git. The credential is never embedded in the page or URL.
The page keeps the supplied credential in memory until logout or reload.

## Limits

Records disappear on restart and are local to one worker.
One record covers one application provider call. Provider transport retries remain inside that record.
Administrator diagnostics can expose private prompts and NPC facts. They are not an actor-safe training view.
The local implementation is intended for the documented single-worker development launcher.

## Verification

Implemented in `backend/app/llm_trace.py`, the administrator API, and `backend/app/static/llm-debug.*`.
The full Python regression suite passed 1,074 tests on 2026-09-24.
Tests cover administrator access, credential redaction, bounds, running records, provider failures, session binding, benchmark exclusion, and OpenAPI contracts.
Browser verification used an isolated offline fixture. It covered login, call selection, displayed input and output, literal markup, filtering, automatic refresh, logout, and dark theme.
The local API returned successful health, page, schema, and authenticated trace responses after restart.
No live model request was used for this verification.
