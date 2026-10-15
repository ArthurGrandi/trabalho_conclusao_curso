#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
TCC_CACHE_ROOT="${TCC_CACHE_DIR:-$PWD/.cache}"
mkdir -p "$TCC_CACHE_ROOT/npm" "$TCC_CACHE_ROOT/uv" "$TCC_CACHE_ROOT/pip"
if command -v uv >/dev/null 2>&1; then
  TCC_UV="$(command -v uv)"
else
  # Bootstrap the interpreter manager in isolation, without changing system pip.
  TCC_BOOTSTRAP="$TCC_CACHE_ROOT/uv-bootstrap"
  if [ ! -x "$TCC_BOOTSTRAP/bin/uv" ]; then
    echo 'Preparando o gerenciador de Python em um ambiente local…'
    python3 -m venv "$TCC_BOOTSTRAP"
    "$TCC_BOOTSTRAP/bin/python" -m pip install --cache-dir "$TCC_CACHE_ROOT/pip" --only-binary=:all: 'uv>=0.9,<1'
  fi
  TCC_UV="$TCC_BOOTSTRAP/bin/uv"
fi
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$TCC_CACHE_ROOT/python}"
if ! "$TCC_UV" python find --cache-dir "$TCC_CACHE_ROOT/uv" --no-python-downloads 3.12 >/dev/null 2>&1; then
  echo 'Baixando Python 3.12 pronto para uso; o Python do sistema será preservado…'
  "$TCC_UV" python install --cache-dir "$TCC_CACHE_ROOT/uv" --no-bin 3.12
fi
if [ -e .venv ] || [ -L .venv ]; then
  if ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' >/dev/null 2>&1; then
    TCC_BACKUP="$TCC_CACHE_ROOT/venv-backups/venv-$(date +%Y%m%d-%H%M%S)-$$"
    mkdir -p "$(dirname "$TCC_BACKUP")"
    mv .venv "$TCC_BACKUP"
    echo "Ambiente anterior preservado em $TCC_BACKUP"
  fi
fi
if [ ! -x .venv/bin/python ]; then
  "$TCC_UV" venv --cache-dir "$TCC_CACHE_ROOT/uv" --python 3.12 .venv
fi
echo 'Instalando dependências com Python 3.12 e pacotes binários de pandas/numpy…'
"$TCC_UV" pip install --cache-dir "$TCC_CACHE_ROOT/uv" --python .venv/bin/python --only-binary pandas,numpy -r server/requirements-jobspy.txt
.venv/bin/python scripts/check-runtime.py
npm ci --cache "$TCC_CACHE_ROOT/npm" --no-audit --no-fund
npm run build
