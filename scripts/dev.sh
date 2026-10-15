#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [ ! -x .venv/bin/python ]; then echo 'Execute bash scripts/setup.sh primeiro.' >&2; exit 1; fi
setsid .venv/bin/python -m uvicorn server.app:app --host 0.0.0.0 --port "${TCC_API_PORT:-8000}" --reload &
TCC_API_PID=$!
setsid npm run dev -- --port "${TCC_WEB_PORT:-5173}" &
TCC_WEB_PID=$!
cleanup() {
  kill -TERM -- "-$TCC_API_PID" "-$TCC_WEB_PID" 2>/dev/null || true
  wait "$TCC_API_PID" "$TCC_WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
wait -n "$TCC_API_PID" "$TCC_WEB_PID"
