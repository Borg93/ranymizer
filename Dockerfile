# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the SHOWCASE target (Python gr.Server + static SPA).
# This image is NOT for the Tauri desktop build — bundle that natively with
# `bun run tauri build` on a machine matching the OS/arch.
#
#   docker build -t ranymizer .
#   docker run --rm -p 7860:7860 ranymizer
#
# Layers (large → small change rate to maximise cache reuse):
#   1) bun installs frontend deps, builds the SvelteKit SPA (default = Gradio engine)
#   2) uv installs backend Python deps
#   3) sources copied + final layer

# ── 1) Frontend build ─────────────────────────────────────────────────
FROM oven/bun:1.3 AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/bun.lock* ./
RUN bun install --frozen-lockfile || bun install
COPY frontend/ ./
RUN bun run build

# ── 2) Backend runtime ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# OpenCV / PaddleOCR runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libgomp1 ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# uv — fast, reproducible Python deps
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY backend/pyproject.toml backend/.python-version /app/backend/
RUN cd /app/backend && uv sync --no-dev --no-install-project

COPY backend /app/backend
COPY example-images /app/example-images
COPY --from=frontend /app/frontend/build /app/frontend/build

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/backend/.venv/bin:${PATH}" \
    LOAD_MODELS_ON_STARTUP=1

EXPOSE 7860
WORKDIR /app/backend
CMD ["python", "server.py"]
