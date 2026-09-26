# DR-41. Local LLM diagnostics without sign-in

Date: 2026-09-24.
Status: accepted. Supersedes the local access and capture prerequisites in DR-40.

## Decision

The local `/llm-debug` page MUST open the trace viewer without a credential or sign-in step.
Both trace endpoints MUST allow unauthenticated requests from a loopback client to a loopback host.
If an `Origin` header is present, it MUST match the request origin for this exemption.
Other trace requests MUST retain administrator authentication.
This exemption MUST NOT apply to other administrator or Player API operations.
Capture MUST require `NEGOTIATION_LLM_TRACE=true`. It MUST NOT require an administrator credential.
The page MUST attempt to load traces immediately. It MAY show the administrator form when remote access requires authentication.
The OpenAPI operations MUST describe the conditional authentication rule.
Redaction, memory bounds, benchmark exclusion, and `no-store` remain mandatory.

## Rationale and consequences

The user requested direct access to the local development window.
Automatic local access removes credential setup from this workflow.
Any local client can inspect the trace buffer through a loopback URL.
The same-origin check prevents a foreign browser origin from using this exemption.
The local Qwen launcher continues to bind to `127.0.0.1`.
The existing administrator credential remains available for the Session Inspector and remote authenticated access.

## Verification

Passed 28 focused trace and OpenAPI checks.
Verified loopback access without credentials, matching and foreign origins, remote authentication, and unchanged administrator gates.
Restarted the local API and verified HTTP 200 without a credential.
Reloaded the existing browser page. The connected trace viewer appeared without the sign-in form.
