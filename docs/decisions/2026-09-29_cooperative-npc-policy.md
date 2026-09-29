# DR-57: Cooperative NPC counterproposals

Date: 2026-09-29.
Status: Accepted. The user selected cooperative negotiation within existing limits.

## Options

1. Prefer feasible compromises. Keep authored limits. Selected.
2. Change courtesy wording only. This does not change bargaining behavior.
3. Lower economic limits in an easier scenario. This changes the exercise. Not selected.

## Contract

New training sessions with one human and one built-in NPC MUST store `npc_policy_version=cooperative-v1` in internal session state.
This rule does not depend on tone or difficulty.
Existing sessions without this version MUST keep the previous policy.
Checkpoint copies and forks MUST preserve the stored version.
Benchmark and external-agent sessions MUST keep the previous policy.
No API setting, database migration, or scenario version change is required.

For complete scalar offers, the cooperative policy MUST prefer a validated package close to the player's proposed terms.
It MUST rank candidates by the sum of absolute term differences divided by each authored schema range.
It MUST break ties by the number of changed terms, then by NPC utility, then by canonical JSON.
Candidates MUST come from the bounded authored grid, single-term variants of that grid, or a validated monetary midpoint.
The policy MUST preserve prior public monetary concessions.
Each changed nonmonetary exchange term MUST improve the NPC's utility at the selected price.
The policy MUST NOT read the counterpart's utility model or private preparation.
If no cooperative candidate is eligible, the previous validated fallback MAY run.

For composite supply price discussion, the cooperative seller MAY examine the entire authored price list immediately.
Each candidate MUST pass the existing own-role constraints and reservation check.
The seller MUST NOT increase the discussed price or invent an unauthored price.
Missing terms MUST remain missing in the delivered preliminary package.
The existing evaluation-only completion MUST NOT become an agreement or an assertion that payment terms were accepted.
The composite buyer policy remains unchanged.

Hard constraints, reservation utility, parser authority, and publication and acceptance confirmation MUST remain unchanged.
Rapport and tone MUST NOT authorize economic concessions.
The LLM MUST only render the engine-selected action.
The service MUST use the same policy version for action selection and its explanation.

## Verification

Tests MUST compare old and cooperative counterproposals.
Tests MUST cover both scalar roles, all published scenario families, both languages, and no-feasible-deal cases.
Tests MUST cover monotonic concessions, missing terms, private-model isolation, canonical explanations, restart, and checkpoint forks.
Tests MUST prove that benchmark and historical sessions keep their previous policy.
Provider availability checks do not establish final coaching quality.
Production activation requires a separate deployment.
