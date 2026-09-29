# DR-58: Contextual package replies and visible agreement

Date: 2026-09-29.
Status: Accepted for the user's requested corrective behavior and supplied regression example.

## Decision

Correct the existing deterministic parser, reply planning, and completion UI.
Do not add a second AI relevance service or change economic eligibility.
The alternative additional model pass adds latency and does not correct missing structured context.

Follow-up: [DR-59](2026-09-29_npc-relevance-check.md) records the user's later choice of an additional relevance check.
DR-59 supersedes the choice to omit that check. The parser and interface rules below remain in force.

## Input and reply contract

- A short numeric reply MUST use the latest delivered engine-selected question before an older topic focus.
- The renderer MUST ask for the planned term. It MUST NOT invent a different numeric question.
- After a partial offer, the engine MUST select one missing required term for its follow-up question.
- Multiple explicit terms in one proposed package MUST be extracted together. Sentence boundaries MUST NOT discard a term.
- Separate supported relative edits MAY be combined when each clause identifies one distinct term and uses the same active public baseline.
- Questions, quotations, negation, incompatible alternatives, missing units, and unsupported terms MUST retain their safety checks.
- A clarification MUST describe the actual problem. Only ambiguous agreement may ask about whole-offer acceptance.
- A counterproposal MUST identify the terms it changes and the proposed terms it retains. It MUST describe one complete validated package.
- These statements describe the selected package. They MUST NOT claim that each retained term is independently acceptable.
- A rejection MUST identify supported term objections when available. Otherwise it MUST explain that the package needs revision without inventing a reason or hidden limit.
- Courtesy changes MUST NOT change canonical numbers, actions, or confirmation requirements.
- Existing stored messages and render plans MUST remain unchanged.

## Completion UI

- `agreement_reached` MUST retain the final conversation before showing analysis.
- The UI MUST display a Russian or English agreement dialog. The dialog MUST not itself accept a deal or make an API mutation.
- The dialog MUST distinguish counterpart acceptance from player confirmation when the API supplies that action. Otherwise it MUST use a neutral agreement title.
- The dialog MUST offer viewing the agreement and opening the analysis.
- Closing the dialog MUST leave the completed dialogue visible. A visible action MUST still open analysis.
- Analysis MUST appear only after the user requests it. Background loading of the existing engine review MAY continue.
- Non-agreement outcomes MUST NOT show a false acceptance dialog.
- Repeated state refreshes MUST NOT reopen a dismissed dialog. A different session MUST have separate presentation state.
- The dialog MUST support keyboard operation, focus containment, and system light and dark themes.

## Verification

Reproduce the annual-rent question followed by `2 600 000`.
Test Russian and English multi-term packages and mixed absolute and relative clauses.
Retain parser safety regressions and formal confirmation tests.
Test the final reply, both dialog actions, dismissal, reload, session switching, and non-agreement outcomes.
Keep live provider quality claims separate from deterministic test results.
