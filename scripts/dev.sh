#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [ ! -x .venv/bin/python ] || ! .venv/bin/python scripts/check-runtime.py >/dev/null 2>&1 || [ ! -d node_modules ]; then bash scripts/setup.sh; fi
echo "Frontend na porta ${TCC_WEB_PORT:-5173}. No Codespaces, abra essa porta na aba Ports/Portas."
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
