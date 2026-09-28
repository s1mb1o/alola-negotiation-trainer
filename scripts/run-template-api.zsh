#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
api_port="${NEGOTIATION_API_PORT:-8172}"

cd "$project_dir"
exec env \
  NEGOTIATION_NPC_PROVIDER=template \
  NEGOTIATION_CONTROL_PROVIDER=template \
  NEGOTIATION_REVIEW_PROVIDER=template \
  NEGOTIATION_LLM_TRACE=false \
  "$project_dir/.venv/bin/python" -m uvicorn backend.app.main:app \
  --host 127.0.0.1 --port "$api_port" --workers 1 "$@"
