# DeepSeek V4.1 Flash dialogue check

Date: 2026-09-27.

## Purpose

This check compares the new default NPC wording route with the earlier `qwen-flash-character` check.
It uses four synthetic Russian training sessions.
It does not use private user data.

## Configuration

- NPC wording: `deepseek-v4.1-flash`.
- NPC thinking: disabled.
- NPC timeout: 30 seconds.
- Grounding and social classification: `deepseek-v4-flash-0731` with thinking disabled.
- Final coaching: not requested.
- Endpoint: QwenCloud Pay-as-you-go in Singapore.

The engine selected each action before generation.
The existing grounding check validated generated wording.
The existing deterministic fallback remained active.

## Cases

| Case | Required behavior | Result |
| --- | --- | --- |
| Price and delivery trade | Interpret later delivery as possible flexibility and discuss a price exchange | Passed |
| Current supplier terms | State authored public terms and explain the approved price reason | Passed |
| Unrelated personal question | Answer politely and return to the negotiation topic | Passed |
| Abuse and recovery | Set a boundary and resume a calm price discussion | Passed |

One public-position reply used the deterministic canonical action.
The other seven eligible replies called the NPC wording model.
All seven generated replies passed validation.
No generated reply used the fallback.

The earlier `qwen-flash-character` check accepted two of seven generated replies.
It used five safe fallbacks.
The two checks used the same four dialogue trajectories and the same safety architecture.

## Latency

The seven recorded NPC generation calls had these latencies:

- Minimum: 5.18 seconds.
- Median: 17.66 seconds.
- Mean: 17.26 seconds.
- Maximum: 24.99 seconds.

The complete four-session batch took 197.74 seconds.
This duration includes openings, grounding, social classification, API work, and all dialogue turns.

## Assessment

`deepseek-v4.1-flash` is a better current default for this small check.
It improved wording-guard acceptance from 2 of 7 to 7 of 7.
It answered the player before it advanced the NPC goal.
It did not invent a numeric deal term in the reviewed replies.

The latency is high for an interactive dialogue.
The current 30-second timeout contains every measured NPC generation call, but the margin is small.
The sample is too small for a general model ranking.
The project still needs a fixed evaluation set with at least 50 trajectories before a final model decision.
