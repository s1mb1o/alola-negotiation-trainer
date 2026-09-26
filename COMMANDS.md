# Service commands

Last checked: 2026-09-23.
These commands are for local development on macOS with zsh.
Use two terminal tabs: one for the API and one for the Web UI.

## Addresses

| Component | Address |
| --- | --- |
| Training UI | [Training](http://127.0.0.1:8171/training) |
| Session Inspector | [Inspector](http://127.0.0.1:8171/inspector) |
| API health | [Health](http://127.0.0.1:8172/api/v1/health) |
| API documentation | [Swagger UI](http://127.0.0.1:8172/docs) |
| API schema | [OpenAPI JSON](http://127.0.0.1:8172/openapi.json) |
| API reference | [ReDoc](http://127.0.0.1:8172/redoc) |

Run `uv run pytest backend/tests/test_openapi.py` to validate the API documentation and response contracts.
See the [OpenAPI guide](docs/openapi-guide.md) for the authentication workflow.

Use API port `8172` for this Mac's previously tested configuration.
Port `8170` is also assigned to another project. Do not stop that project.
The repository's default Vite proxy still points to `8170`.
The UI command below explicitly selects `8172`.

## Prepare dependencies

Use Python 3.11 or later, Node.js 22 or later, and `uv`.
Run these commands after cloning or when dependency lockfiles change:

```zsh
cd /Volumes/T7_2TB/Projects-T7_2TB/2026_LCT_Hackatons/9-Negotiation_trainer
uv sync --frozen --all-groups
npm --prefix frontend ci
```

## Start the API

Open the first terminal tab and enter the project directory:

```zsh
cd /Volumes/T7_2TB/Projects-T7_2TB/2026_LCT_Hackatons/9-Negotiation_trainer
```

Run exactly one of the following API commands.
Keep the terminal open while the service runs.
The commands use the installed virtual environment. They do not need activation.

### Selected model: QwenCloud Pay-as-you-go

The NPC wording model is `qwen-flash-character`.
The turn-control model is `DeepSeek-V4-Flash-0731` with thinking disabled.
The final-review model is `Qwen3.8-Max` with thinking disabled.
The launcher reads `QWENCLOUD_PAYGO_API_KEY` from its process environment.
The interactive zsh command below loads the user's `~/.zshrc` first.
The key stays in memory. The launcher does not copy it to a file or print it.

```zsh
/bin/zsh -ic 'exec /bin/zsh scripts/run-qwen-api.zsh'
```

The launcher selects the exact endpoint:
`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`.
It starts this project's API on `127.0.0.1:8172` with one worker.
Stop an existing verified project API process before using the launcher.
Provider-backed tasks use the configured Pay-as-you-go account when generation is requested.
Set `NEGOTIATION_NPC_MODEL=qwen-plus-character` before the launcher to evaluate the larger Character model.

### Alternative: natural dialogue with OpenAI

Use a zsh session that already exports `OPENAI_API_KEY`.
Do not paste the key into the command or repository.
Provider-backed dialogue can incur API charges when a game requests a generated reply.

```zsh
NEGOTIATION_NPC_PROVIDER=openai \
NEGOTIATION_NPC_MODEL=gpt-5.6-luna \
NEGOTIATION_NPC_API_KEY_ENV=OPENAI_API_KEY \
NEGOTIATION_NPC_BASE_URL= \
NEGOTIATION_NPC_TEMPERATURE= \
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8172 --workers 1
```

### Equivalent explicit Qwen command

Use a zsh session that already exports `QWENCLOUD_PAYGO_API_KEY` from `~/.zshrc`.
This configuration selects the same routes as the launcher.
It does not use the external-agent client's `QWEN_BASE_URL` setting.

```zsh
NEGOTIATION_NPC_PROVIDER=qwen \
NEGOTIATION_NPC_MODEL=qwen-flash-character \
NEGOTIATION_NPC_API_KEY_ENV=QWENCLOUD_PAYGO_API_KEY \
NEGOTIATION_NPC_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1 \
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
NEGOTIATION_NPC_TEMPERATURE= \
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8172 --workers 1
```

These model identifiers are existing project settings, not a guarantee of current account access.
Missing credentials or failed generation can produce a template fallback.
See [provider configuration](README.md#provider-configuration) for custom endpoints.

### Offline template mode

Use this mode when you do not want built-in NPC provider requests.
It does not provide LLM-generated dialogue.
It does not stop a separately launched external-agent client from making its own requests.

```zsh
NEGOTIATION_NPC_PROVIDER=template \
NEGOTIATION_NPC_MODEL= \
NEGOTIATION_NPC_API_KEY_ENV= \
NEGOTIATION_NPC_BASE_URL= \
NEGOTIATION_NPC_TEMPERATURE= \
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8172 --workers 1
```

## Start the Web UI

Run these commands in the second terminal tab:

```zsh
cd /Volumes/T7_2TB/Projects-T7_2TB/2026_LCT_Hackatons/9-Negotiation_trainer/frontend
VITE_API_BASE=http://127.0.0.1:8172/api/v1 npm run dev -- --port 8171 --strictPort
```

Open [Training](http://127.0.0.1:8171/training).
Keep `/api/v1` in `VITE_API_BASE`. Do not add a trailing slash.
The explicit API base bypasses the default proxy to port `8170`.
Restart Vite after changing `VITE_API_BASE`.
Keep provider keys and the administrator token out of all `VITE_*` variables.

## Check status

Use another terminal tab:

```zsh
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8172/api/v1/health
curl --fail --head --max-time 5 http://127.0.0.1:8171/training
lsof -nP -iTCP:8172 -sTCP:LISTEN
lsof -nP -iTCP:8171 -sTCP:LISTEN
```

The API health response should contain `"status":"ok"`.
The UI request should return HTTP 200.
A failed connection means that no reachable service answered at that address.
An empty `lsof` result means that it found no visible listener on that port.
These checks do not submit a game message or call an LLM.

## Stop

Press `Ctrl+C` in the API terminal.
Wait for the shutdown message and shell prompt.
Press `Ctrl+C` in the Web UI terminal.
Stopping only the UI leaves the API running.

If the original terminal is unavailable, find the exact process first:

```zsh
lsof -nP -iTCP:8172 -sTCP:LISTEN
lsof -nP -iTCP:8171 -sTCP:LISTEN
```

Replace `PID` below with one numeric PID from that output.
Check its command and working directory before stopping it:

```zsh
ps -p PID -o pid,ppid,command
lsof -a -p PID -d cwd
```

The API command must belong to this project's `backend.app.main:app` process.
The UI command must belong to this project's Vite process.
The working directory must be this project or its `frontend` directory.
Do not continue if the process belongs to another project.
After verification, send a graceful termination signal to that PID:

```zsh
kill -TERM PID
```

Repeat separately for the other verified process if necessary.
Run the listener checks again to confirm shutdown.
Do not use broad commands such as `pkill node` or `pkill uvicorn`.
Do not use `kill -9` for a normal shutdown.

## Restart

1. Stop the affected process with the procedure above.
2. Confirm that its port no longer has a listener.
3. Repeat its start command in the correct directory.
4. Run the health checks and refresh the browser.

Restart the API after changing NPC provider settings or backend code.
Restart the UI after changing its environment or Vite configuration.
Do not start a second API process against the same SQLite file to perform a restart.

## Configuration and saved sessions

The API reads configuration from its process environment.
It does not automatically load a repository `.env` file or `.env.example`.
Open a new zsh terminal if your exported shell settings have changed.

The default database is `backend/data/negotiation.db` inside this project.
`NEGOTIATION_DB_PATH` overrides that path.
Use the same database path after a restart to retain session history.
Do not delete the database, its `-wal` file, or its `-shm` file as a restart step.
Existing sessions retain their pinned scenario versions.

Session Inspector requires `NEGOTIATION_ADMIN_TOKEN` in the API process environment.
The local LLM trace window opens without a credential under DR-41. Remote trace access still requires the administrator credential.
The local Qwen launcher preserves an existing value. If none exists, it generates a local credential at `.local/llm-debug-admin-token` with mode `0600`.
Enter the same token in the Inspector access form.
Keep its value out of this document and command history.

Open <http://127.0.0.1:8172/llm-debug> in a separate window to inspect new LLM calls during training.
The local page loads the trace list automatically.
For Session Inspector or remote trace access, copy the generated administrator credential without printing it:

```zsh
pbcopy < .local/llm-debug-admin-token
```

Paste it into the applicable administrator access form.
The launcher enables `NEGOTIATION_LLM_TRACE=true` by default. Set it to `false` to disable capture.
The trace buffer is private process memory. It clears on restart and excludes benchmark calls.
See the [LLM diagnostics guide](docs/llm-debug-guide.md).

CLI clients default to the older API port.
Point them to this API in their own terminal:

```zsh
export NEGOTIATION_API_URL=http://127.0.0.1:8172
```

Start the windowed CLI in that terminal:

```zsh
uv run python -m clients play --scenario freight_contract_ru --language ru --role buyer --other-role seller --difficulty guided
```

The CLI opens three terminal windows for the conversation, context panel, and message input.
The conversation starts with the pinned public scenario title and your role brief.
Use `Tab` to switch the context panel between the offer, role brief, and coaching.
Add `--debug` to start with a lower-right debug pane.
Press `F3` or enter `/debug` to show or hide the pane during a session.
Use `F7` and `F8` to scroll its variables.
The pane shows session state and public NPC event metadata from the authenticated Player API.
It does not show private NPC state or credentials.
Use `F2` to inspect an offer or a pending exact-revision confirmation.
Use `Page Up` and `Page Down` for conversation history.
Type `/hint` to request a hint, `/help` for controls, or `/quit` to exit.
Use `--plain` to retain the line-oriented JSON interface.
The windowed interface requires an interactive terminal at least 72 columns by 16 rows.
It uses fixed black in 256-color terminals. Eight-color terminals use their ANSI black.
It uses reverse video when the terminal reports no color support.

See [`.env.example`](.env.example) for configuration names.
See [the validation guide](docs/dr28-dialogue-validation.md) for offline and separately authorized live tests.
