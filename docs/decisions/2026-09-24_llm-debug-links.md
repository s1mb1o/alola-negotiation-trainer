# DR-42. Addressable LLM calls and messages

Date: 2026-09-24.
Status: accepted.

## Decision

Each trace MUST have a direct page address: `/llm-debug#<trace_id>`.
Instructions, each input message, and the response MUST have section addresses under that trace fragment.
The page MUST restore selection on direct navigation, reload, and browser history navigation.
Polling MUST preserve the selected trace. It MUST NOT substitute another trace when the selected record is unavailable.
The page MUST show an explicit unavailable-record message after eviction or process restart.
The fragment MUST contain only an opaque trace identifier and an optional section identifier.
The fragment MUST NOT contain message content or credentials.
Existing access rules and trace retention remain unchanged.

## Implementation

Use the existing random `trace_id` as the slug.
Use `instructions`, `message-0`, `message-1`, `response`, and `parameters` as section identifiers.
Use ordinary anchors so the user can copy a link or open it in another tab.
Use fragment navigation to update the current deployment without restarting the API or clearing existing traces.
A link remains usable while its record is retained in the process buffer.
This change does not add trace persistence or change the REST API.

## Verification

Six DOM navigation tests passed.
Checks cover direct addresses, history, section links, eviction, invalid fragments, and delayed replies after navigation.
Browser verification used the existing three trace records. It covered selection, a response section, reload, Back, and Forward.
The update required no API restart and made no model calls.
