#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [ ! -x .venv/bin/python ] || [ ! -f dist/index.html ]; then echo 'Execute bash scripts/setup.sh primeiro.' >&2; exit 1; fi
exec .venv/bin/python -m uvicorn server.app:app --host 0.0.0.0 --port "${PORT:-8000}"
