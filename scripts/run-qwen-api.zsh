#!/bin/zsh

unsetopt XTRACE VERBOSE
set -eu

project_dir=${0:A:h:h}

if [[ -z ${QWENCLOUD_TOKEN_PLAN_API_KEY:-} ]]; then
  print -u2 'QWENCLOUD_TOKEN_PLAN_API_KEY is missing. Run this launcher from an interactive zsh session that loads ~/.zshrc.'
  exit 1
fi

if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
  print -u2 'The project virtual environment is missing. Run uv sync --frozen --all-groups first.'
  exit 1
fi

export QWENCLOUD_TOKEN_PLAN_API_KEY
export NEGOTIATION_NPC_PROVIDER=qwen
export NEGOTIATION_NPC_MODEL=qwen3.8-max
export NEGOTIATION_NPC_API_KEY_ENV=QWENCLOUD_TOKEN_PLAN_API_KEY
export NEGOTIATION_NPC_BASE_URL=https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
unset NEGOTIATION_NPC_TEMPERATURE

cd "$project_dir"
exec "$project_dir/.venv/bin/python" -m uvicorn backend.app.main:app \
  --host 127.0.0.1 --port 8172 --workers 1 "$@"
