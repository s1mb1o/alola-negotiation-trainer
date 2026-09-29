# ALOLA — тренажёр переговоров

ALOLA даёт безопасную практику деловых переговоров в браузере.
Игрок пишет естественные реплики.
Детерминированный движок отдельно проверяет условия сделки, ограничения, порог приемлемости и подтверждение соглашения.

Материалы и доступы для жюри распространяются по отдельной прямой ссылке.
Скриншоты показывают демонстрационный прогон Nord Systems от 29.09.2026.
Результат 73,325 / 100 относится к этому прогону. Он не подтверждает измеренный рост навыка.

Три свойства отличают MVP от лекции, чат-бота и разовой ролевой игры:

1. Движок хранит сделку как проверяемое состояние и не передаёт экономическую истину LLM.
2. Игрок может вернуться к сохранённому решению и сравнить два фактических исхода на одном состоянии.
3. Люди, внешние агенты и CLI используют один Player API. Это позволяет применять сценарии и для обучения, и для сопоставимых прогонов агентов.

Локальные артефакты кандидата: [презентация](docs/release/ALOLA_LCT2026_Task9_v2.pptx), [PDF](output/pdf/ALOLA_LCT2026_Task9_v2.pdf) и [сценарий видео](docs/release/video-script.md).
Внешние URL и точный публичный тег добавляют только после прохождения release gate.

## Целевая аудитория, проблема и границы MVP

Основная аудитория — специалисты по закупкам и продажам, руководители, HR-команды и корпоративные учебные центры.
Им нужна повторяемая практика без риска для реальной сделки.
Лекции объясняют методы, но не проверяют решение в диалоге.
Групповая ролевая игра требует тренера, расписания и второго участника.
Обычный LLM-чат может звучать естественно, но не гарантирует устойчивые правила сделки.

MVP закрывает полный цикл: настройка, приватный бриф, диалог, явное предложение, безопасное подтверждение, выход без сделки, детерминированный результат и повтор решения.
Репозиторий содержит девять опубликованных идентификаторов сценариев в четырёх доменах: поставка оборудования, SaaS, перевозка и аренда офиса.
Основной демонстрационный кейс — `supplier_001` версии 6.

MVP не является юридическим конструктором договора.
Он не оценивает психологию человека.
Он не выводит точную скрытую ZOPA из переписки.
Шаблонный режим не выполняет LLM-коучинг, не меняет тон через модель и не обновляет социальные индикаторы.
Эти элементы скрыты в сборке по умолчанию.

## Архитектура и логика симуляции

```text
React Web UI / CLI / внешний агент
                │ естественный текст
                ▼
         Player API (FastAPI)
                │
     parser → validation → state transition
                │                  │
                │                  └─ SQLite: transcript + typed events
                ▼
 deterministic NPC policy → template wording
                │
                └─ optional provider wording after action selection
```

Структурированное состояние является источником истины.
Сценарий задаёт роли, публичный контекст, допустимые термины, ограничения и функции полезности.
Парсер предлагает типизированное действие.
Движок проверяет действие и только затем меняет состояние.
LLM может формулировать уже выбранную реплику, но не может назначить полезность, скрытый факт или обязательное условие.

Сервис хранит исходную переписку и структурированный журнал событий.
Каждая сессия привязана к неизменяемой версии сценария.
Контроль ревизии и идемпотентность защищают от повторной отправки.
Соглашение требует отдельного подтверждения полного предложения.
Фраза `согласен` без однозначного контекста не связывает сделку.

### Параметры конфигурации администратора

В MVP администратор выбирает подготовленный сценарий и его версию.
Игрок на стартовом экране выбирает доступные параметры сессии.
Экономические правила остаются авторскими и не редактируются в свободном тексте.

| Настройка | Фактический эффект | Не меняет |
| --- | --- | --- |
| Сценарий | Домен, роли, термины, бриф, ограничения и формулу результата | Правила уже опубликованной версии |
| Роль | Приватный бриф и функцию полезности игрока | Скрытое состояние другой стороны |
| Сложность | Объём брифа, подсказки и дополнительные отвлекающие факты | BATNA, порог приемлемости и ограничения |
| История отношений | Формулировку приветствия и начальную социальную конфигурацию | Экономику сделки |
| Общая предыстория | Разрешённый общий контекст диалога | Приватный план игрока |
| План игрока | Приватные цели для итогового сопоставления | Решения и знания NPC |
| Подсказки | До трёх детерминированных подсказок в поддерживаемых режимах | Допустимость предложения |
| Стиль реплик | Доступен только в сборке с провайдером | Политику действий NPC |

| Требование администратора | Поток в MVP | Ограничение интерфейса |
| --- | --- | --- |
| Выбрать учебный кейс | Выбор опубликованной версии сценария | Браузер не редактирует экономику сценария |
| Задать роль и уровень помощи | Выбор параметров до создания сессии | Активная сессия сохраняет исходную конфигурацию |
| Добавить новый кейс | Авторинг YAML/JSON и проверка линтером | Визуальный редактор отложен |
| Опубликовать кейс | Новая неизменяемая версия и тесты | Опубликованная версия не меняется на месте |
| Проверить результаты | Отзывы, журнал событий, CLI и API | MVP не заявляет измеренный эффект обучения |

## Инструкция по сборке, запуску и демонстрации

Нужны Python 3.11+, `uv`, Node.js 22+ и актуальный Chrome.
Ключ внешнего API не нужен.

В первом терминале выполните:

```sh
git clone https://github.com/s1mb1o/alola-negotiation-trainer negotiation-trainer
cd negotiation-trainer
uv sync --frozen --all-groups
zsh scripts/run-template-api.zsh
```

В Windows PowerShell замените последнюю команду на:

```powershell
$env:NEGOTIATION_NPC_PROVIDER="template"
$env:NEGOTIATION_LLM_TRACE="false"
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8172 --workers 1
```

Во втором терминале выполните:

```sh
cd negotiation-trainer/frontend
npm ci
npm run dev
```

Откройте <http://127.0.0.1:8171/app/training> в Chrome.
Vite передаёт `/api` на `http://127.0.0.1:8172`.
Если порты заняты, используйте `NEGOTIATION_API_PORT`, `VITE_API_PROXY_TARGET` и `VITE_DEV_PORT` как показано ниже в разделе [Run locally](#run-locally).

### Как проверить за 5 минут

1. Выберите основной кейс `supplier_001`, роль покупателя, деловой уровень и русский язык.
2. Оставьте шаблонный режим без ключа.
3. Отправьте приветствие. Система создаст точку возврата перед решением игрока.
4. Отправьте: `Предлагаю цену 112 000 EUR, аванс 100% и поставку за 8 недель.`
5. Завершите эту ветку или вернитесь к точке перед предложением.
6. В новой ветке спросите: `Какие ваши приоритеты?`
7. Затем отправьте: `Предлагаю цену 105 000 EUR, аванс 100% и поставку за 2 недели.`
8. Сравните результат игрока: 26 в первой ветке и 70 во второй. Разница равна +44.
9. Отдельно нажмите `Завершить переговоры` и подтвердите выход. Сессия должна получить статус `walked_away` и сформировать разбор.

Демонстрация показывает, что порядок действий и полный пакет меняют исход.
Она не раскрывает скрытые пределы другой стороны.

### Как формулировка влияет на состояние

| Формулировка | Интерпретация | Эффект |
| --- | --- | --- |
| `Предлагаю цену 105 000 EUR, аванс 100% и поставку за 2 недели.` | Полное явное предложение | Создаёт новую редакцию предложения после проверки |
| `Аванс 50% для нас много.` | Возражение, а не предложение | Не принимает и не изменяет предложение |
| `Конкурент предлагал 108 000 EUR.` | Сообщение о третьей стороне | Не переносит чужое число в предложение игрока |
| `Какие ваши приоритеты?` | Вопрос об интересах | Не изменяет условия сделки |
| `Согласен.` | Недостаточно контекста | Запрашивает уточнение |
| `Принимаю все условия предложения.` | Намерение принять полный пакет | Открывает отдельное подтверждение |
| `Подтверждаю принятие полного предложения без дополнительных условий.` | Точное подтверждение | Заключает обязательное соглашение |
| `Прекращаю переговоры.` | Явный выход | Завершает сессию без соглашения |

### Завершения сессии

| Завершение | Условие | Что видит игрок |
| --- | --- | --- |
| Соглашение | Отдельно подтверждено одно полное предложение | Условия, полезность и предупреждение о пороге |
| Выход | Игрок явно завершил переговоры | Разбор без соглашения и доступные доказательства |
| Истечение времени | Сработало настоящее ограничение сессии | Причина завершения без выдуманной сделки |
| Техническая остановка | Движок не может безопасно продолжить | Нейтральное сообщение и диагностический код |

Запрос уточнения в учебном режиме не является завершением.
Он сохраняет условия сделки и предлагает безопасный пример следующей реплики.

## Методы, библиотеки и внешние сервисы

Экономический результат использует авторские кусочно-линейные функции полезности, жёсткие ограничения и `reservation_utility`.
BATNA является входом в порог приемлемости, но может отличаться от него.
Линтер сценария проверяет ожидаемое наличие ZOPA.
Точный скрытый диапазон не показывается игроку.

Гарвардский подход отражён через интересы, варианты, объективные критерии, BATNA и взаимовыгодные обмены.
При наличии валидированного модельного разбора Voss-карточка отделяет наблюдаемую коммуникацию от экономического результата.
SPIN не используется как отдельная автоматическая оценка навыка.
Вопросы ситуации, проблемы и последствий можно практиковать в диалоге, но MVP не присваивает им выдуманный балл.

| Компонент | Назначение | Версия или фиксация | Условия доступа |
| --- | --- | --- | --- |
| [Python](https://www.python.org/) | Движок, CLI и тесты | 3.11+ | Открытый runtime |
| [FastAPI](https://fastapi.tiangolo.com/) и [Pydantic](https://docs.pydantic.dev/) | HTTP API и типизированные контракты | 0.141.1 и 2.13.4 в `uv.lock` | Открытые библиотеки |
| [SQLite](https://sqlite.org/) | Локальные сессии, события и отзывы | Модуль Python | Входит в Python |
| [React](https://react.dev/), TypeScript и [Vite](https://vite.dev/) | Веб-интерфейс и сборка | 19.2.8, 5.7.3 и 6.4.3 в `package-lock.json` | Открытые библиотеки |
| Pytest, Vitest и Ruff | Регрессии и статический контроль | 8.4.2, 2.1.9 и CI-пин 0.15.5 | Открытые инструменты |
| OpenAI Responses API | Опциональные агенты и формулировки | Серверный адаптер | Нужен отдельный ключ |
| QwenCloud Chat Completions API | Опциональные формулировки и коучинг | Серверный адаптер | Нужен отдельный ключ |
| Шаблонный renderer | Основной отказоустойчивый режим | Версионируемые шаблоны | Ключ не нужен; внешних запросов нет |

## Внедрение и вовлечение

Первый канал внедрения - корпоративные учебные центры для продаж и закупок.
Второй канал - интеграция через Player API и CLI в существующую LMS или программу обучения.
Повтор строится вокруг возврата к одной точке решения и сравнения двух исходов.
MVP не содержит подтверждённой оценки рынка, конверсии или эффекта обучения.
Пилот с 1-2 незнакомыми пользователями проверяет только понятность пути и доступность запуска.

## Краткое описание концепции для сдачи §7.1

ALOLA — веб-тренажёр переговоров для закупок, продаж, руководителей и корпоративного обучения.
Он закрывает разрыв между теорией и безопасной повторяемой практикой.
Игрок ведёт естественный диалог, а детерминированный движок проверяет условия, ограничения, полезность и явное подтверждение сделки.
Сценарии задают разные роли и экономику.
Возврат к точке решения позволяет сравнить две тактики на одинаковом состоянии.
Шаблонный режим работает без внешнего ключа.
Опциональная LLM отвечает только за формулировку уже разрешённых действий и за отдельный итоговый разбор.

## План до финала для сдачи §7.1

До финальной фиксации команда выполняет только релизные работы.
Команда блокирует семантически опасные формулировки парсера, проверяет ключевой путь на `supplier_001` версии 6 и фиксирует один SHA кандидата.
Команда готовит публичный очищенный репозиторий с историей, шаблонный стенд без ключей, презентацию по шаблону и видеодемонстрацию 3–5 минут.
После фиксации разрешены только перезапуск стенда и проверка доступности.
Новые продуктовые функции переносятся после хакатона.

## Ключевые решения и компромиссы

- Движок решает, что произошло. LLM решает только, как это сказать.
- Мы выбрали модульный монолит и SQLite для воспроизводимого MVP на одном хосте.
- Мы используем неизменяемые версии сценариев вместо редактирования активной экономики.
- Мы разделяем экономический результат и качество формулировок.
- Мы требуем два шага для принятия предложения человеком или агентом.
- Мы сохраняем шаблонный режим как основной отказоустойчивый путь без платного API.
- Мы показываем эвристики как диагностику, а не как валидированную оценку компетенции.

## План развития после хакатона

Следующий этап добавит проверенный редактор сценариев, серверную БД для нескольких хостов, валидированный live-LLM профиль и исследование SPIN-рубрики.
Экономическая сложность и социальная политика потребуют отдельных версионированных решений.
Они не входят в текущий MVP.

## English technical reference

Negotiation Trainer is an API-first training and simulation service.

The service publishes [OpenAPI JSON](http://127.0.0.1:8172/openapi.json), [Swagger UI](http://127.0.0.1:8172/docs), and [ReDoc](http://127.0.0.1:8172/redoc).
See the [OpenAPI guide](docs/openapi-guide.md) for authentication, examples, and contract checks.

Repository: [GitHub](https://github.com/s1mb1o/alola-negotiation-trainer).

The repository contains a runnable FastAPI service, a React Web UI, a CLI, external-agent clients, a Telegram integration adapter, and a role-swapped benchmark runner.

Russian is the primary demo language.
The executable scenarios and clients also support English.

## Implemented MVP

The [human training loop](docs/human-training-guide.md) adds private preparation, shared player background, two NPC profiles, bounded social state, and goal-based LLM coaching.
Completed sessions can restart from a recorded decision checkpoint with fresh credentials.
Active training sessions can rewind to an earlier NPC checkpoint three times per root lineage.
The **Ответь за меня** action uses `Qwen3.8-Max` to create one actor-safe player reply and submits it through the normal Player API.
The final report compares observed parent and child results.
[DR-36](docs/decisions/2026-09-24_training-loop.md) defines the delivered scope.
The selected live route uses `deepseek-v4.1-flash` for NPC wording, `deepseek-v4-flash-0731` for turn control, and `qwen3.8-max` for final coaching.
The launcher disables thinking for all three bounded tasks.
Full coaching quality remains unvalidated on live Qwen dialogues.

- FastAPI exposes the role-neutral Player API.
- SQLite stores immutable scenario versions, sessions, participant credentials, offers, messages, events, reviews, and benchmark metadata.
- SQLite uses WAL mode.
- The engine validates deal terms, hard constraints, offer revisions, turn ownership, and terminal transitions.
- The built-in NPC uses a deterministic action policy and an optional provider-backed dialogue renderer.
- In human-versus-built-in-NPC training, the NPC greets the player without stating offer terms. The human makes the first live negotiation move.
- A scenario can use a complete `opening_offer` or a partial `opening_position` with unresolved required terms.
- The service never inserts a placeholder value for an omitted opening-position term.
- An explicit zero remains a real term value.
- Human and external-agent acceptance uses a separate full-offer confirmation step. Natural acceptance phrases and a restatement of the counterpart's complete package reach that step; a bare `согласен` asks for clarification.
- The parser reads number words and thousand or million abbreviations (`сто десять тысяч`, `110 тыс.`, `1,2 млн`, `thirty percent`, `six weeks`) and ignores a negated walk-away phrase.
- Numeric questions and reported quotations do not become offers. Explicit proposal clauses remain distinct from questions in the same message.
- Bounded relative changes use one active public offer revision. Short numeric replies use an unambiguous topic or an engine-authored requested term.
- The built-in NPC follows an explicit topic and can discuss a partial price proposal before requesting the remaining terms.
- Bounded conversation memory retains source references, postponed topics, participant statements, and public offer events across restart.
- Authored reasons explain the NPC position when the player asks about the matching term.
- New scenario versions define richer grounded motives, stable conversational styles, and bounded exchange candidates.
- The engine can exchange a monetary concession for another authored term after validating the complete package.
- The built-in NPC never binds a package that violates any role's hard constraint and never reverses its previous public monetary concession.
- The renderer can quote active public numbers through exact attributed engine slots. It cannot create a price or an agreement through prose.
- Difficulty changes conversational guidance and challenge. It does not change economic truth or reservation thresholds.
- Each review lists key moments with the acting role, the package, and the quoted message, plus actor-specific recommendations.
- The service records both a raw transcript and a structured event history.
- The Web UI supports Russian and English, four difficulty levels, light, dark, and system themes, and responsive layouts.
- The Web UI stores the UI language and theme in browser-local preferences.
- The UI language also selects the matching localized scenario catalog.
- The Web UI uses browser Web Speech APIs for optional STT and TTS when the browser supports them.
- The Web UI includes a read-only Admin Session Inspector with filters, transcripts, public events, offer revisions, dialogue diagnostics, and gated public reviews.
- The separate [LLM diagnostics window](docs/llm-debug-guide.md) at `http://127.0.0.1:8172/llm-debug` shows new training-session provider calls. Local access opens without sign-in. Remote access requires an administrator credential. Redacted traces remain only in bounded process memory.
- An offline evaluator exports source-attributed human scorecards and compares dialogue diagnostics separately from economic outcomes.
- The CLI supports interactive play, one-agent play, self-play, history export, reviews, and statistics.
- Provider adapters support the OpenAI Responses API and Qwen Cloud Chat Completions API.
- The benchmark runner creates fresh trials, swaps model roles, records safe telemetry, retries transient provider errors before attributing a failure, records the provider-reported model id and per-seat seeds, and separates technical failures from negotiation outcomes.
- Benchmark reviews remain sealed until the declared run set is terminal.
- The Telegram adapter maps a chat to the same participant-scoped Player API. It does not require a specific Telegram framework.
- Nine current scenario IDs cover freight, office lease, SaaS, and industrial-computer supply negotiations. The integration-and-reserve scenario supports Russian and English.

The current versions are supplier version 6, office-lease version 4 in both languages, freight version 4 in Russian and version 3 in English, and SaaS version 3 in both languages.
These versions add grounded motives, conversation styles, and candidate grids for validated exchanges.
They preserve the earlier economic truth, utility rules, hard constraints, and opening terms.
Earlier published versions remain available for explicit-version sessions and replay.

The service never uses an LLM as the source of truth for deal validity, utility, hidden facts, or hard constraints.

See the Russian [NPC dialogue guide](docs/npc-dialogue-guide.md) for examples, scenario versions, authoring rules, and verification steps.
Prepared NPC reply variants live in [reply_examples_v1.json](backend/data/reply_examples_v1.json). The engine filters them by case, role, language, and action before the renderer sees them.

## Run locally

See [COMMANDS.md](COMMANDS.md) for complete start, stop, restart, and status commands for this Mac's API on port 8172 and UI on port 8171.
The portable defaults use API port 8172 and UI port 8171.

Use Python 3.11 or later and Node.js 22 or later.

For the no-key template mode, start the API from the repository root.

```sh
uv sync --frozen --all-groups
zsh scripts/run-template-api.zsh
```

Start the Web UI in another terminal.

```sh
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:8171/app/training` in Chrome.

The development UI proxies `/api` to `http://127.0.0.1:8172` by default.
No provider credential is required.
The template build hides provider-only controls by default.

To use other local ports, set matching values before startup.

```sh
NEGOTIATION_API_PORT=8272 zsh scripts/run-template-api.zsh
cd frontend
VITE_API_PROXY_TARGET=http://127.0.0.1:8272 VITE_DEV_PORT=8271 npm run dev
```

Do not stop an unrelated service to free a port.

The selected paid route uses QwenCloud Pay-as-you-go.
The local launcher reads `QWENCLOUD_PAYGO_API_KEY` from the interactive zsh environment.
This command loads `~/.zshrc`.

```sh
/bin/zsh -ic 'exec /bin/zsh scripts/run-qwen-api.zsh'
```

Set an administrator token before service startup to enable the Session Inspector.

```sh
export NEGOTIATION_ADMIN_TOKEN='replace-with-a-local-secret'
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8172
```

Open `http://127.0.0.1:8171/app/inspector`.
Enter the same token in the access form.
The browser keeps this credential in `sessionStorage` only.
The Inspector never returns raw session state, private event payloads, credentials, or sealed benchmark reviews.

Use `.env.example` as a configuration reference.
Export each selected variable into the service process environment.
The application does not load `.env.example` automatically.
Do not put provider keys in the repository.

The default `NEGOTIATION_NPC_PROVIDER=template` mode needs no provider credential.

## CLI

A new `play` or `agent` session uses the credential issued at creation. `NEGOTIATION_PARTICIPANT_TOKEN` is only a fallback for the `history`, `review`, and `export` commands.

List Russian scenarios.

```sh
uv run python -m clients scenarios --language ru
```

Start an interactive session.

```sh
uv run python -m clients play \
  --scenario freight_contract_ru \
  --language ru \
  --role buyer \
  --other-role seller \
  --difficulty guided
```

In an interactive terminal, `play` opens a windowed interface. It shows the conversation,
the current public offer, your role brief, and available coaching. Use `Tab` to switch the
right panel. Use `Page Up` and `Page Down` to scroll the conversation. Use `F5` and `F6`
to scroll the right panel. Use `F2` to inspect the current offer. A separate confirmation
window appears when you must publish or accept an exact offer revision. Confirm with
`Enter` or `Y`. Cancel the pending confirmation with `C`. Press `Esc` to return to the
conversation without sending a confirmation.
The conversation starts with the pinned scenario title and your actor-safe role brief.
Use `--debug` to show a lower-right pane with the current session revision, turn state,
pending operation, and public NPC action metadata. Press `F3` or enter `/debug` to toggle
the pane. Use `F7` and `F8` to scroll it. The pane does not show private NPC state.

Type a message and press `Enter` to send it. Use `Ctrl+N` to add a line to the draft.
Type `/hint` to request a hint, `/help` to view controls, or `/quit` to exit. The terminal
must be at least 72 columns by 16 rows. Use `--plain` for the original line-oriented JSON
interface. `play` also uses that interface when input or output is redirected.
The 256-color theme uses fixed black for the background. It distinguishes borders, speakers,
headings, and errors. Eight-color terminals use their configured ANSI black. On light
monochrome terminals, reverse video gives the interface a dark background.

Run one external OpenAI agent against the built-in NPC.

```sh
uv run python -m clients agent \
  --scenario freight_contract_ru \
  --language ru \
  --provider openai \
  --model gpt-5.6-luna
```

## Provider configuration

External-agent clients and the optional built-in NPC renderer read credentials at runtime.

Set `OPENAI_API_KEY` or `QWEN_API_KEY` with the deployment secret manager or a hidden shell prompt.
Do not paste a credential into a command or tracked file.

The Qwen adapter selects the QwenCloud Token Plan endpoint for `sk-sp-` keys.
Set `QWEN_BASE_URL` when the key belongs to Coding Plan or a custom workspace.

The built-in NPC Qwen renderer keeps the Token Plan endpoint as its backward-compatible implicit default.
It does not read the ambient `QWEN_BASE_URL` value.
Set `NEGOTIATION_NPC_BASE_URL` and `NEGOTIATION_NPC_API_KEY_ENV` together when the NPC must use another Qwen endpoint.
The selected launcher explicitly uses the Pay-as-you-go endpoint for all model routes.

External-agent clients do not send provider keys to the backend or browser.
The optional backend renderer reads its selected key from the service process environment.
No provider adapter writes a key to the database, transcript, event log, API response, review, log, or benchmark artifact.

### Built-in NPC dialogue

The engine selects and validates every built-in NPC action before dialogue rendering.

The default template renderer uses deterministic actor-safe messages.

The optional OpenAI or Qwen renderer receives only an allowlisted dialogue request.
It writes contextual replies for non-binding speech acts.
It receives up to 12 public dialogue turns from both participants, with at most 1,000 characters per turn.
It also receives the public scenario title, NPC role identifier, and labels for missing terms.
It receives bounded conversation memory with a version and public source references.
It also receives an allowlisted dialogue profile, stable role style, optional engine-authored requested term, and active-offer numeric references.
The service rebuilds that memory from the current session's durable messages and public events.
Memory can retain an earlier topic, postponed topics, attributed player statements, question-response references, public offer revisions, and an actual binding agreement.
A reply can mark a question `responded`; chronology alone cannot establish that it was answered.
Player assertions remain untrusted statements.
Only authoritative events establish public offers and binding agreements.
An explicit topic switch changes the current focus.
Postponing or resuming a topic does not agree its value or change an existing offer term.

Each role can author up to six `dialogue_reasons` with a topic and a reference to its own objective or context.
The compiler validates the reason structure and nonnumeric text.
The scenario author checks that the source supports the explanation.
The engine selects at most two matching reasons after a topic question or a contextual follow-up.
The renderer receives selected reason identifiers and texts, plus previously delivered public reason history.
It does not receive the private source text or unselected private reasons.
Only delivered disclosures enter disclosed-reason history.
The delivered message must contain the exact authored reason text to record its disclosure.
Later turns can use disclosed-reason history without repeating the authored text verbatim.
Reasons do not change utility, deal constraints, or acceptance thresholds.

The parser distinguishes numeric questions, quotations, proposals, corrections, relative edits, and short answers within a bounded grammar.
A relative edit needs one active public baseline with the scenario currency.
The parser clarifies an ambiguous reference rather than selecting a historical price.
Generated NPC questions do not select the numeric term expected from the player.
The engine records that term as `requested_term_id` in a delivered public event.

New scenarios can author `exchange_policy.candidate_values` for existing required terms.
The compiler validates each candidate and limits the complete grid to 512 packages.
The policy selects only complete packages that pass all hard constraints and the NPC reservation utility.
It does not optimize against the counterpart's private utility.
An incomplete opening position remains incomplete until the participant proposes its missing terms.

The renderer can insert an engine-authored numeric reference token such as `[[quote_a]]`.
The engine replaces the token with an exact attributed quotation from the active public offer.
Unknown or repeated tokens, stale references, and raw generated numbers fail validation.
The quote does not create a new offer, commitment, or agreement.

`pragmatic`, `analytical`, and `relationship_focused` styles are independent from difficulty.
Guided and Easy dialogue supports small steps.
Normal and Expert dialogue asks for grounds and reciprocal changes.
Neither style nor difficulty changes hidden facts or economic thresholds.

Opening-offer and opening-position presentations, binding acceptance, rejection, and complete counteroffer messages always use deterministic templates.
The renderer never receives private role briefs, hidden facts, utility values, or constraints.
The service redacts participant tokens, credential-shaped fragments, and known configured credentials before parsing, truncation, persistence, and provider submission.
Generated prose never changes structured negotiation state.
Deterministic output checks run before a separate grounding check for novel text.
An exact engine-authored option does not need the grounding check.
The grounding check can reject wording but cannot change the NPC action.
This semantic check is probabilistic, not a formal guarantee.

The service persists each provider-eligible NPC intent and durable render job before provider I/O.
It atomically claims the render job before the provider attempt.
It delivers one validated reply or deterministic fallback with compare-and-swap checks.
Startup recovery delivers the precomputed fallback for an unfinished render job.
Historical render plans remain readable without memory, reasons, numeric references, and profile fields.
A create-time binding NPC action uses its canonical deterministic message in the create transaction and does not call a provider.
The human training greeting uses a deterministic template and does not call a provider.
`successful_history` selects one of six relationship-aware templates in the session language.
The templates signal familiarity without inventing details about previous negotiations.
An Easy create-time `opening_offer` or `opening_position` presentation for an external-agent next actor also bypasses the provider.

Set `OPENAI_API_KEY` securely in the service process environment before you use this exact OpenAI run command:

```sh
NEGOTIATION_NPC_PROVIDER=openai \
NEGOTIATION_NPC_MODEL=gpt-5.6-luna \
NEGOTIATION_NPC_API_KEY_ENV=OPENAI_API_KEY \
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8170
```

Use this command for the selected Qwen configuration after zsh exports `QWENCLOUD_PAYGO_API_KEY`:

```sh
NEGOTIATION_NPC_PROVIDER=qwen \
NEGOTIATION_NPC_MODEL=deepseek-v4.1-flash \
NEGOTIATION_NPC_API_KEY_ENV=QWENCLOUD_PAYGO_API_KEY \
NEGOTIATION_NPC_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1 \
NEGOTIATION_NPC_ENABLE_THINKING=false \
NEGOTIATION_NPC_TIMEOUT_SECONDS=30 \
NEGOTIATION_CONTROL_PROVIDER=qwen \
NEGOTIATION_CONTROL_MODEL=deepseek-v4-flash-0731 \
NEGOTIATION_CONTROL_API_KEY_ENV=QWENCLOUD_PAYGO_API_KEY \
NEGOTIATION_CONTROL_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1 \
NEGOTIATION_CONTROL_ENABLE_THINKING=false \
NEGOTIATION_REVIEW_PROVIDER=qwen \
NEGOTIATION_REVIEW_MODEL=qwen3.8-max \
NEGOTIATION_REVIEW_API_KEY_ENV=QWENCLOUD_PAYGO_API_KEY \
NEGOTIATION_REVIEW_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1 \
NEGOTIATION_REVIEW_ENABLE_THINKING=false \
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8172
```

The built-in NPC supports these environment variables:

- `NEGOTIATION_NPC_PROVIDER`: `template`, `openai`, or `qwen`; default `template`;
- `NEGOTIATION_NPC_MODEL`: optional model override; OpenAI defaults to `gpt-5.6-luna`, and Qwen defaults to `qwen3.8-max`;
- `NEGOTIATION_NPC_API_KEY_ENV`: optional credential environment-variable name; the name must use uppercase letters, digits, and underscores;
- `NEGOTIATION_NPC_BASE_URL`: optional HTTPS endpoint override; Qwen NPC rendering defaults to the Token Plan endpoint, and a custom endpoint requires an explicit `NEGOTIATION_NPC_API_KEY_ENV`;
- `NEGOTIATION_NPC_MAX_OUTPUT_TOKENS`: default `300`; permitted range `32` through `2000`;
- `NEGOTIATION_NPC_TEMPERATURE`: optional; leave it empty for `gpt-5.6-luna`; a configured value must be from `0` through `2` and must be supported by the selected model;
- `NEGOTIATION_NPC_ENABLE_THINKING`: optional `true` or `false`; the selected DeepSeek route sets it to `false`;
- `NEGOTIATION_NPC_TIMEOUT_SECONDS`: default `20`; permitted range `0.1` through `120`.

The `NEGOTIATION_CONTROL_*` variables select grounding, social classification, and semantic extraction.
The `NEGOTIATION_REVIEW_*` variables select final coaching.
Each group supports `PROVIDER`, `MODEL`, `API_KEY_ENV`, `BASE_URL`, `TEMPERATURE`, `ENABLE_THINKING`, and `TIMEOUT_SECONDS`.
An empty control group reuses the dialogue provider.
An empty review group reuses the control provider.
`ENABLE_THINKING` accepts `true`, `false`, or an empty value.
Use `NEGOTIATION_NPC_MODEL=qwen-flash-character` or `NEGOTIATION_NPC_MODEL=qwen-plus-character` to evaluate a Character model without a code change.

One eligible non-binding NPC turn makes at most one claimed render attempt.
That attempt can include a generation call and a separate grounding-check call.
Provider timeout, failure, empty output, invalid JSON, or an output-contract failure uses the precomputed deterministic reply.
The fallback does not change the engine-approved action or terms.

## Role-swapped benchmark

The following command creates one Russian and one English role-swapped pair.

```sh
uv run python -m benchmarks \
  --scenario freight_contract_ru:1:ru \
  --scenario freight_contract_en:1:en \
  --model openai:gpt-5.6-luna \
  --model qwen:qwen3.8-max \
  --repetitions 1 \
  --max-messages 8 \
  --max-output-tokens 180
```

Set the same `NEGOTIATION_ADMIN_TOKEN` for the backend and runner. The runner sends it on benchmark session creation, which the backend requires when the token is configured, and uses it to close failed trials.

Provider calls retry rate limits, 5xx responses, timeouts, and connection errors with backoff. Use `--provider-max-attempts` and `--provider-retry-backoff` to change the defaults; the run configuration records both. The agent prompt version is `natural-language-agent-v5`. It uses English instructions for Russian and English sessions. Identify prompt-version differences when comparing artifacts. Training social classification and coaching use one transport attempt per model call.

The runner passes a seed only when the provider supports that parameter.
A seed does not guarantee identical provider output.

## Built-in NPC validation

The DR-28 smoke suite uses supplier version 6 in Russian and office version 4 in English.
It checks public state, numeric quotes, source revisions, partial terms, and clarification recovery.
The default matrix includes three cases per language and all four difficulty levels.
These are training-path checks, not an agent-versus-agent benchmark.

```sh
.venv/bin/python -m backend.live_dialogue_smoke
.venv/bin/python -m backend.live_dialogue_smoke --mode offline --workers 4 --output benchmark-results/dr28-offline-new.json
```

The first command only prints a plan.
The second command uses an offline fixture through the real renderer and Player API.
Neither command makes external model calls.
Use a new output path for each run. The runner does not overwrite artifacts.
The artifact contains public source-linked sessions for the evaluator below.

Live mode requires explicit selection and a positive provider-call limit.
The limit includes generation and grounding calls. It is not a monetary budget.
See the [validation guide](docs/dr28-dialogue-validation.md) for model selection, consent, and result interpretation.

## Offline dialogue evaluation

The Inspector overview separates technical dialogue diagnostics from economic results.
It shows exact repeats, repeated questions, fallback rate, categorized failures, and measured latency.
Missing telemetry appears as unavailable, not zero.
Repetition flags are heuristics. They do not prove that an answer is relevant or correct.

The offline CLI accepts a public Admin session detail or an object with a `sessions` array.
It makes no provider requests.

```sh
uv run python -m benchmarks.dialogue_quality export-scorecard public-sessions.json
uv run python -m benchmarks.dialogue_quality analyze public-sessions.json
uv run python -m benchmarks.dialogue_quality analyze public-sessions.json --scorecard human-ratings.json
```

Save the first command's JSON output as `human-ratings.json`.
Enter ratings and source references without editing the exported context.
The analyzer checks source digests and rating ranges.
It keeps unrated dimensions `null` and reports rating coverage.
The API does not store human ratings in this increment.

The [dialogue evaluation rubric](docs/dialogue-evaluation-rubric.md) defines the four human dimensions and the full procedure.
The connected Russian and English fixture corpus includes deliberate failures and is not evidence of live model quality.

```sh
uv run python -m benchmarks.dialogue_quality analyze benchmarks/fixtures/dialogue_quality_cases.json
```

## Verification

```sh
uv run pytest
uv run ruff check backend clients benchmarks

cd frontend
npm audit
npm test
npm run build
```

The CI workflow runs the Python suite, Ruff, the npm audit, frontend tests, and the production build.

See the DR-28 validation-suite report for the latest offline matrix and test evidence.
See the DR-28 implementation report for runtime changes and earlier verification.
See the conversation-continuity report for the earlier DR-27 evidence.
DR-28 acceptance checks are listed in [SMOKE_TESTS.md](SMOKE_TESTS.md).

See the initial implementation report for the original MVP validation.

See the OpenAI agent benchmark report for the authorized Luna and Terra self-play results.

See the full LLM matrix report for the 11-model Russian and English comparison.

## Current boundaries

The next delivery order is accepted in [DR-29](docs/decisions/2026-09-08_reference-before-generalization.md): complete one reference supply scenario, then generalize its deal model for another domain.
The bounded reference scenario is implemented under [DR-30](docs/decisions/2026-09-08_reference-supply-implementation.md).
See the [implementation guide](docs/reference-supply-guide.md).
The [reference supply specification](docs/reference-supply-spec.md) keeps live language validation pending before generalization.

- The built-in NPC uses a deterministic MVP policy. An optional provider can write contextual non-binding replies after the engine selects the action and disclosures.
- The parser supports bounded proposal clauses, questions, quotations, corrections, and one explicit relative `на` or `by` change against the active offer. It does not implement unrestricted arithmetic or date interpretation.
- The current scalar supplier scenario is immutable version 6. Its public opening position states only the price and leaves prepayment and whole-order delivery unresolved.
- Supplier version 2 retains its complete opening offer. Version 3 retains its partial opening position. Both remain available for replay.
- Conditional exchanges use only authored candidates. The renderer can quote existing public numbers only through validated reference slots.
- Human conversation ratings require an offline source-attributed scorecard. Technical checks do not provide an automatic humanity score.
- The supplier scenario executes price, prepayment, and whole-order delivery terms. It does not bind split delivery, FOC, reserve, or contingent RMA structures.
- The parser requests clarification when one message contains several offer packages.
- The authored knowledge model, evidence-to-belief updates, participant hypotheses, and runtime composite-term DSL remain specification-level capabilities. They are not active runtime features.
- The service implements exact-revision training forks from recorded checkpoints. MESO offer sets remain outside the current UI.
- Browser STT and TTS depend on Web Speech support. The canonical stored input remains text.
- SQLite supports one host with a shared local database file.
- Multiple local service processes use atomic render claims and compare-and-swap delivery against the same database.
- A deployment across hosts requires a server database and distributed locking.
- A repeated create-session idempotency request returns the same session without participant credentials. Credentials are delivered only in the initial response.
- When `NEGOTIATION_ADMIN_TOKEN` is configured, creating a `run_mode: benchmark` session requires the same administrator Bearer credential. Training sessions need no credential.
- `max_rounds` expiry is evaluated right after the action that completes the last round for every controller type.

The target authored-world and runtime-emergent-state model is specified in [docs/knowledge-and-emergent-state.md](docs/knowledge-and-emergent-state.md).

## Specifications

- [Architecture](docs/architecture.md)
- [Player API](docs/api.md)
- [Offer and session protocol](docs/offer-session-protocol.md)
- [Grounded dialogue decision](docs/decisions/2026-09-06_grounded-negotiation-dialogue.md)
- [Dialogue evaluation rubric](docs/dialogue-evaluation-rubric.md)
- [Negotiation model](docs/negotiation-model.md)
- [Knowledge and emergent state](docs/knowledge-and-emergent-state.md)
- [Scenario schema](schemas/scenario-v1.schema.json)
- [Event schema](schemas/negotiation-event-v1.schema.json)
- [Accepted decisions](docs/decisions/2026-08-27_post-review-decisions.md)

## Design proposals

- [Social state, conversation memory, and LLM protection](docs/social-state-and-llm-dialogue.md): broader persona, STATUS, MEMORY, and OWASP design. DR-36 defines the implemented subset.

## Hackathon research

- Task 9 verified insights and source map: official requirements, Telegram clarifications, deadlines, resources, and open questions.
- Task 9 Telegram monitoring ledger: message-level evidence and coverage state.
