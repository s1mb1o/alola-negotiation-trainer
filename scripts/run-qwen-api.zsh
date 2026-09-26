#!/bin/zsh

unsetopt XTRACE VERBOSE
set -eu

project_dir=${0:A:h:h}

if [[ -z ${QWENCLOUD_PAYGO_API_KEY:-} ]]; then
  print -u2 'QWENCLOUD_PAYGO_API_KEY is missing. Run this launcher from an interactive zsh session that loads ~/.zshrc.'
  exit 1
fi

if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
  print -u2 'The project virtual environment is missing. Run uv sync --frozen --all-groups first.'
  exit 1
fi

export QWENCLOUD_PAYGO_API_KEY
export NEGOTIATION_NPC_PROVIDER=qwen
export NEGOTIATION_NPC_MODEL=${NEGOTIATION_NPC_MODEL:-qwen-flash-character}
export NEGOTIATION_NPC_API_KEY_ENV=QWENCLOUD_PAYGO_API_KEY
export NEGOTIATION_NPC_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
unset NEGOTIATION_NPC_TEMPERATURE

export NEGOTIATION_CONTROL_PROVIDER=qwen
export NEGOTIATION_CONTROL_MODEL=${NEGOTIATION_CONTROL_MODEL:-deepseek-v4-flash-0731}
export NEGOTIATION_CONTROL_API_KEY_ENV=QWENCLOUD_PAYGO_API_KEY
export NEGOTIATION_CONTROL_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
unset NEGOTIATION_CONTROL_TEMPERATURE
export NEGOTIATION_CONTROL_ENABLE_THINKING=false

export NEGOTIATION_REVIEW_PROVIDER=qwen
export NEGOTIATION_REVIEW_MODEL=${NEGOTIATION_REVIEW_MODEL:-qwen3.8-max}
export NEGOTIATION_REVIEW_API_KEY_ENV=QWENCLOUD_PAYGO_API_KEY
export NEGOTIATION_REVIEW_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
unset NEGOTIATION_REVIEW_TEMPERATURE
export NEGOTIATION_REVIEW_ENABLE_THINKING=false

# Local diagnostics use a separate administrator credential, never the provider key.
export NEGOTIATION_LLM_TRACE=${NEGOTIATION_LLM_TRACE:-true}
if [[ -z ${NEGOTIATION_ADMIN_TOKEN:-} && $NEGOTIATION_LLM_TRACE == true ]]; then
  mkdir -p "$project_dir/.local"
  chmod 700 "$project_dir/.local"
  export NEGOTIATION_ADMIN_TOKEN=$("$project_dir/.venv/bin/python" - "$project_dir/.local/llm-debug-admin-token" <<'PY'
import os
from pathlib import Path
import secrets
import sys

path = Path(sys.argv[1])
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    pass
else:
    with os.fdopen(fd, "w") as stream:
        stream.write(secrets.token_urlsafe(32))
path.chmod(0o600)
print(path.read_text().strip())
PY
)
fi

cd "$project_dir"
exec "$project_dir/.venv/bin/python" -m uvicorn backend.app.main:app \
  --host 127.0.0.1 --port 8172 --workers 1 "$@"
