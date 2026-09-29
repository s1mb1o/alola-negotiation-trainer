# DR-56: Administrator context presets

Date: 2026-09-29.
Status: Accepted for the user-requested minimal implementation.

## Requirement

Task 9 requires an administrator interface for domain, topic, difficulty, counterpart tone, counterpart role, and counterpart goals.
The task permits selection of an authored scenario. It does not require a general editor.

## Options

1. Rename the Session Inspector. This does not configure a session. Reject this option.
2. Add an administrator preset form. Reuse immutable scenarios and the normal session API. Select this option.
3. Add scenario CRUD and arbitrary economic goals. This expands the scope and the validation surface. Defer this option.

## Contract

- `/app/admin` MUST provide the administrator form in Russian and English.
- `GET /api/v1/admin/training-presets` MUST require `AdministratorBearer`.
- Missing server configuration MUST return 503. Missing or invalid credentials MUST return 401.
- The optional `language` query MUST accept `ru` or `en`.
- The catalog MUST contain approved scenario families only.
- Each preset MUST identify an exact published scenario version, domain, topic, NPC role, and the authored NPC objective.
- The catalog MUST NOT include raw scenario source, private player preparation, economic limits, or credentials.
- The authored objective is privileged authoring data. It MUST NOT be added to the public scenario catalog or the player's session configuration.
- Domain and topic MUST filter the available presets.
- Role and goal selection MUST select a real scenario-role bundle. A goal MUST NOT be a decorative label or arbitrary prompt.
- The equipment topic MUST offer the scalar supply and composite supply cases. Selecting a different goal bundle MUST select the corresponding immutable scenario contract.
- A topic MAY have only one approved goal bundle per role. The UI MUST state that goals are bundled with authored scenarios. It MUST NOT imply independent editing of a goal.
- The administrator MUST select one of the four existing difficulty levels and one of the two existing wording profiles.
- Starting a training session MUST use the existing `POST /api/v1/sessions` contract and a new participant credential.
- The administrator credential MUST be sent only to the administrator catalog endpoint. It MUST NOT be sent to the Player API.
- The form MUST clear its administrator credential and private preset data before handing the browser to the player.
- No assignment database, new creation endpoint, account system, or schema migration is required.

## Authored tone

`TrainingSetup.authored_tone` is optional and defaults to `false`.
The administrator form MUST set it to `true`.
With this flag, the selected wording profile MUST have an observable template-mode effect.
The warmer profile MAY add authored, non-binding courtesy wording to greetings and informational replies.
The concise profile MUST preserve base informational replies. It MAY use a shorter authored greeting.
The flag MUST NOT change actions, numbers, offers, formal acceptance, constraints, utilities, or hidden facts.
Existing sessions without the flag MUST retain their current behavior.
The setup MUST remain stored in session state and checkpoint copies.
Provider-enabled dialogue MUST continue to receive the existing profile and tone context.

## Verification and boundaries

Tests MUST cover authentication, catalog filtering, authored goal binding, pinned versions, player-safe handoff, template tone, unchanged economics, and legacy behavior.
Browser checks MUST cover administrator setup, a created player session, two different goal bundles, and a narrow viewport.
The form MUST support system light and dark themes.
This change MUST NOT claim that all other hackathon requirements are complete.
Production proxy admission for the new GET endpoint requires the normal reviewed deployment. This task does not deploy the product.
