# DR-44. Complete outgoing LLM requests

Date: 2026-09-25.
Status: accepted and implemented.
Extends: DR-40, DR-41, and DR-42.

## Decision

The LLM trace window MUST show the complete application request sent to the provider.
Capture the request at the provider transport boundary.
Show the method, resolved URL, redacted headers, complete JSON body, timeout, and attempt number.
Capture each retry separately.
Do not reconstruct the provider body from the earlier renderer input.
Keep the existing instruction, message, response, and diagnostics sections.
Add an addressable section for each outgoing request attempt.

The recorder MUST NOT truncate retained prompts, messages, request bodies, or response text.
The complete request includes every supplied context field and retrieved example.
Do not add session information that the provider did not receive.
Application context limits still apply before provider submission.
The trace cannot show provider-internal instructions or transport headers added by the HTTP library.

Credentials MUST remain redacted before storage.
Mask authorization and other credential header values.
Do not store raw provider exception messages.
Keep trace contents in process memory only.
Keep at most 200 records and 64 MiB of serialized trace data.
Evict complete records in start order when either limit is exceeded.
An oversized record is evicted instead of being shown as a complete but shortened request.
Missing records retain the existing explicit unavailable behavior.

Request observation MUST NOT change the request or provider behavior.
Observer errors MUST NOT interrupt negotiation.
Concurrent calls MUST retain separate trace contexts.
Disabled tracing and benchmark sessions MUST create no request snapshots.
Existing local access, remote authentication, and Player API isolation rules remain unchanged.

## Rationale

The earlier trace stored truncated provider-neutral input.
That input omitted the final request URL and adapter-specific JSON fields.
Capturing the completed request avoids a second implementation of provider serialization.
Evicting whole records preserves both complete content and bounded retention.

## Verification

Compare captured requests with requests received by fixture transports.
Cover Qwen and Responses adapters, retry attempts, failures, and concurrent calls.
Check long prompts, more than 32 input messages, and full response text.
Check credential redaction and disabled tracing.
Check whole-record eviction, OpenAPI response contracts, and browser section links.
Use fixture transports without external model calls.
