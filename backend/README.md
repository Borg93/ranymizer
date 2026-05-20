# Ranymizer backend (showcase target only)

This directory is the Python `gr.Server` that powers the **public showcase**
(HF Space / ZeroGPU). The Tauri desktop build does NOT need any of this —
desktop inference runs in the WebView via transformers.js. See the root
[README.md](../README.md) for the full architecture.

## Setup with `uv`

```bash
# one-time: install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# from this directory
cd backend
uv sync                  # creates .venv and installs everything in pyproject.toml
```

For CUDA-enabled Torch (replaces the default CPU wheel):

```bash
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
```

## Run

```bash
# from the project root (recommended — paths resolve correctly):
uv --project backend run python backend/server.py

# or from inside backend/:
cd backend && uv run python server.py
```

Listens on `http://0.0.0.0:7860`. CORS is open to `http://localhost:5173` so
the SvelteKit dev server can talk to it during showcase development.

## Files

- `app.py` — pipeline code (PaddleOCR + GLiNER2 PII + span→box mapping)
- `server.py` — Gradio `gr.Server` routes (queued `/anonymize_screenshot`,
  static `/api/examples`, `/api/meta`, and the SvelteKit static mount)
- `pyproject.toml` — uv project definition
- `requirements.txt` — kept as a fallback for hosts that need pip
