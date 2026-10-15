#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [ ! -x .venv/bin/python ] || [ ! -d node_modules ]; then
  echo 'Primeiro uso: preparando as dependências da plataforma…'
  bash scripts/setup.sh
elif [ ! -f dist/index.html ] || [ -n "$(find src public index.html package.json package-lock.json vite.config.ts tsconfig.json -type f -newer dist/index.html -print -quit)" ]; then
  echo 'Preparando a interface…'
  npm run build
fi
echo "Plataforma na porta ${PORT:-8000}. No Codespaces, abra essa porta na aba Ports/Portas."
exec .venv/bin/python -m uvicorn server.app:app --host 0.0.0.0 --port "${PORT:-8000}"
