FROM python:3.12-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy full source so uv can resolve all workspace member dependencies
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
COPY ingestion/ ./ingestion/

RUN uv sync --frozen --no-dev --package backend


FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the populated venv and application source
COPY --from=builder /app/.venv ./.venv
COPY backend/ ./backend/
COPY ingestion/ ./ingestion/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
