#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

exec uv run --package backend uvicorn backend.app.main:app \
  --reload \
  --host "${HOST}" \
  --port "${PORT}" \
  "$@"
