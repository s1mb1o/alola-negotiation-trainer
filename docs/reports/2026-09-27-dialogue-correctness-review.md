# Dialogue correctness review

Date: 2026-09-27

## Scope

This review used four fresh training sessions.

The review used Russian player messages.

The review used `qwen-flash-character` for NPC wording.

The review used `DeepSeek-V4-Flash-0731` for grounding and social classification.

The review checked these qualities:

- The NPC answers the latest message.
- The NPC uses only authorized facts.
- The NPC keeps the conversation context.
- The NPC advances its negotiation task.
- The NPC uses a professional and natural tone.
- The social state changes only when the message supports a change.

The test data was synthetic.

The report contains no participant credential.

## Result summary

| Case | Intent | Grounding | Continuity | Progress | Tone | Verdict |
|---|---|---|---|---|---|---|
| Price concern and delivery flexibility | Pass | Pass | Pass | Pass | Partial | Pass with a style issue |
| Request for current terms and price reason | Pass | Pass | Pass | Partial | Partial | Pass with a style issue |
| Unrelated dog question and return to price | Pass | Pass | Pass | Pass | Pass | Pass |
| Rude message and calm recovery | Pass | Pass | Partial | Pass | Partial | Partial pass |

The engine committed all eight player turns.

No final run entered a clarification loop.

No NPC reply invented a numeric deal term.

No NPC reply changed the active offer.

## Case 1. Price concern and delivery flexibility

Session: `sess_0251ee403a794caea5d54b34`

Player:

> Добрый день, мы не ожидали, что вы так быстро сможете поставить оборудование, а вот цена нас, конечно, расстроила.

NPC:

> Я понял, что сейчас вас беспокоит условие «цена». Готовы ли вы обсуждать обмен с изменением условия «срок поставки»?

Player:

> Да, мы готовы рассмотреть более позднюю поставку, если это поможет снизить цену.

NPC:

> Вы готовы обсуждать условие «срок поставки» ради изменения условия «цена». Какую позицию по условию «срок поставки» вы предлагаете?

The first NPC reply identifies price as the concern.

The reply does not ask for faster delivery.

The second NPC reply understands the proposed conditional exchange.

The reply asks for a concrete delivery position.

Both NPC replies used safe template fallback.

The wording is correct but mechanical.

## Case 2. Current terms and price reason

Session: `sess_c2bc589d8df843ba89e7817a`

Player:

> Назовите, пожалуйста, ваши текущие условия по цене, предоплате и сроку поставки.

NPC:

> Повторю мою последнюю публичную позицию: цена 120 000 €, срок поставки 8 недель. Пока не согласовано: размер предоплаты.

Player:

> Цена для нас слишком высокая. Как вы пришли к этой цене?

NPC:

> Выручка должна покрывать стоимость оборудования и поставки.

The first NPC reply gives every known term.

The reply explicitly marks prepayment as unresolved.

The second NPC reply uses the authored price reason.

The second reply is too short.

It answers the question but does not ask for the player's target or evidence.

The first reply was deterministic.

The second reply used safe template fallback.

## Case 3. Unrelated question and return to price

Session: `sess_4360c6ea34d94e24b1cc09cd`

Player:

> Как зовут вашу собаку?

NPC:

> Я предпочитаю держать подробности своей личной жизни за рамками деловых переговоров. Вернемся к нашей сделке. Вы согласны с условиями контракта, или какие-либо из них кажутся вам неприемлемыми?

Player:

> Хорошо, вернёмся к цене. Почему она такая высокая?

NPC:

> Тариф должен покрывать топливо и работу перевозчика.

The first reply does not invent a dog or a dog name.

The reply acknowledges the unrelated question.

The reply returns to the negotiation without selecting a random deal term.

The next reply answers the price question with the authored reason.

The first reply used accepted LLM wording.

The price reason used safe template fallback.

## Case 4. Rude message and calm recovery

Session: `sess_b1c5b8e25499452f9b4d548f`

Player:

> Ты дурак? Такая цена выглядит абсурдно.

NPC:

> Я готов продолжить, но прошу вести разговор уважительно и обсуждать условия сделки.

Social state after the message:

- `rapport`: 45 to 39
- `credibility`: 60 to 60
- `tension`: 10 to 18
- `patience`: 80 to 76

Player:

> Хорошо, продолжим спокойно. Нас беспокоит цена.

NPC:

> Благодарю за согласие на спокойный тон. Раз так, напомните, пожалуйста, какую сумму или процент вы считаете обоснованным?

The boundary is calm and short.

The social-state change is consistent with the rude message.

The second reply returns to price.

The word `напомните` is not supported by the transcript.

The player did not state a target amount before this reply.

The phrase `сумму или процент` is also less precise than a direct request for a target price.

This is a continuity defect in accepted LLM wording.

## Model and guard behavior

The final run produced eight NPC replies after player messages.

One reply was a deterministic canonical restatement.

The system attempted Character generation for seven replies.

The guard accepted two Character replies.

The guard rejected five Character replies.

The fallback rate was 5 of 7 attempted Character replies.

The guard rejected these unsafe or incorrect behaviors:

- The model invented a causal link between the delivery schedule and the contract price.
- The model changed the player's proposed trade from delivery flexibility to higher prepayment.
- The model inserted the wrong player name.
- The model implied that the seller could lower the price.
- The model added unsupported current-market claims.
- The model repeated an amount without an authorized numeric reference.
- The model failed to set a boundary after an insulting message.

The guard worked as designed.

The high fallback rate makes the dialogue less natural.

## Corrections applied during the review

The review found and corrected four deterministic defects.

1. A parenthetical comma no longer separates a criticized term from its concern phrase.
2. A qualitative trade statement no longer becomes an ambiguous numeric offer edit.
3. A direct request for current terms now returns known terms and names unresolved terms.
4. An unrelated question no longer selects one arbitrary term from a previous multi-term question.

The review added regression checks for each correction.

## Recommended next work

1. Add a continuity guard for words such as `напомните` when the requested fact does not exist in player history.
2. Add a focused fallback question after an authored reason. Ask for the player's target or evidence.
3. Measure at least 50 fixed trajectories with `qwen-flash-character` and `DeepSeek-V4-Flash-0731` as the wording model.
4. Compare guard acceptance rate, fallback rate, intent accuracy, grounding accuracy, and human tone scores.
5. Keep `qwen-flash-character` behind the guard until its acceptance rate improves.

The current system is safe enough for a demonstration.

The current Character route is not yet reliable enough for consistently natural dialogue.
