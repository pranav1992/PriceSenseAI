FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace manifests and lock file
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml ./backend/

# Install dependencies into .venv (no editable installs)
RUN uv sync --frozen --no-install-workspace --no-dev


FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the synced virtualenv from builder
COPY --from=builder /app/.venv ./.venv

# Copy application source
COPY backend/ ./backend/
COPY ingestion/ ./ingestion/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

CMD uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
