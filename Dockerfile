# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_CACHE_DIR=/tmp/.uv-cache \
    HSK5_DATA_DIR=/data \
    ROOT_PATH=/mini-hsk5

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

RUN useradd -m -u 1000 appuser && mkdir -p /data && chown -R appuser:appuser /app /data

FROM base AS builder
COPY pyproject.toml uv.lock README.md ./
COPY hsk5 ./hsk5
COPY main.py ./
RUN uv sync --frozen --no-dev

FROM base AS runtime
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser hsk5 ./hsk5
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser templates ./templates
COPY --chown=appuser:appuser data/vocab ./data/vocab

USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8097
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8097"]
