#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
TCC_CACHE_ROOT="${TCC_CACHE_DIR:-$PWD/.cache}"
mkdir -p "$TCC_CACHE_ROOT/npm" "$TCC_CACHE_ROOT/uv" "$TCC_CACHE_ROOT/pip"
if command -v uv >/dev/null 2>&1; then
  if [ ! -x .venv/bin/python ]; then uv venv --cache-dir "$TCC_CACHE_ROOT/uv" --python python3 .venv; fi
  uv pip install --cache-dir "$TCC_CACHE_ROOT/uv" --python .venv/bin/python -r server/requirements-jobspy.txt
else
  if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
  .venv/bin/python -m pip install --cache-dir "$TCC_CACHE_ROOT/pip" -r server/requirements-jobspy.txt
fi
npm ci --cache "$TCC_CACHE_ROOT/npm" --no-audit --no-fund
npm run build
