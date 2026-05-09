#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

# Load secrets from .env so the backend can reach Oxylabs
if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/.env"
  set +a
fi

# Backend connects to the Dockerised DB on localhost
export DATABASE_URL="postgresql://pricesense:pricesense@localhost:5432/pricesense"

# ── Database ──────────────────────────────────────────────────────────────────
echo "→ Starting database..."
docker compose up -d db

echo "→ Waiting for database to be ready..."
until docker compose exec db pg_isready -U pricesense -d pricesense &>/dev/null; do
  sleep 1
done
echo "  Database ready."
echo ""

# ── Backend ───────────────────────────────────────────────────────────────────
echo "→ Starting backend  →  http://127.0.0.1:8000"
uv run --package backend uvicorn backend.app.main:app \
  --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "→ Starting frontend →  http://localhost:3000"
cd "${REPO_ROOT}/frontend"
BACKEND_URL=http://127.0.0.1:8000 npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Press Ctrl+C to stop."
echo ""

# ── Cleanup on Ctrl+C / SIGTERM ───────────────────────────────────────────────
_cleanup() {
  echo ""
  echo "→ Stopping backend and frontend..."
  kill "${BACKEND_PID}" "${FRONTEND_PID}" 2>/dev/null || true
  wait "${BACKEND_PID}" "${FRONTEND_PID}" 2>/dev/null || true
  echo "  Done. Database container is still running."
  echo "  To stop it: docker compose stop db"
}

trap _cleanup INT TERM

wait "${BACKEND_PID}" "${FRONTEND_PID}"
