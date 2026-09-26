# DR-45. Live social indicators for the player

Date: 2026-09-26.
Status: accepted by the user's request to show the existing social axes in the training workspace.

## Decision

The active training workspace MUST show `rapport`, `credibility`, `tension`, and `patience` in the lower part of the supporting column.
Each indicator MUST show the current value as a marker and a number on a 0–100 scale.
The number MUST match the marker position.
Each indicator MUST show the signed change from the player's latest committed message with a separate delta label.
The displayed change MUST use the engine-applied delta after clamping and event caps.
A message with no applied change MUST replace the prior delta with zero.
An idempotent repeat MUST preserve the original delta.

The Player API MUST expose this projection only to the owner of the training configuration.
The projection MUST contain current values, the latest aggregate delta, and its source revision.
It MUST NOT contain classifier evidence, hidden event history, NPC private state, or another participant's data.
The Admin API MUST continue to omit the private training projection.

The indicators are simulation parameters.
They are not psychological measurements.
They MUST NOT change utility, constraints, action selection, or confirmation rules.
The UI MUST provide Russian and English labels.
The UI MUST expose each current value through an accessible meter.

## Implementation

The engine stores `last_social_change` with all four axes after each newly processed player revision.
The owner observation exposes it as `training.social_state`.
Legacy active sessions use their current values and a zero delta until the next processed player message.
The Web UI renders the projection after the assistance card.

## Verification

API tests check owner-only visibility, aggregation, zero reset, clamping, and idempotency.
OpenAPI tests check the typed projection.
Frontend tests check both languages, meter values, signed deltas, and the missing-projection state.
