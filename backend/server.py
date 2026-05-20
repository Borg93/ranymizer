"""
server.py — Gradio Server backend for the Swedish Ranymizer.

Same pattern as the BiRefNet demo: gr.Server() with @server.api(...) for the
queued compute endpoint, plain @server.get for static reads, plus a static-file
mount for the SvelteKit build.

Layout (paths resolved from the project root, i.e. ../ relative to here):
  ../backend/app.py     — model + pipeline code
  ../backend/server.py  — this file
  ../frontend/build/    — output of `bun run build` (SvelteKit adapter-static)
  ../example-images/    — drop screenshots here, they appear on the landing page

Routes:
  GET  /                          → frontend/build/index.html
  GET  /_app/*                    → static SvelteKit chunks
  GET  /favicon.svg               → frontend/build/favicon.svg
  GET  /api/examples              → list of example filenames
  GET  /examples/{name}           → full image or ?thumb=1 preview
  POST /anonymize_screenshot      → queued compute (Gradio JS client)
"""
from __future__ import annotations

import functools
import io
import traceback
from pathlib import Path

import gradio as gr
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from gradio.data_classes import FileData
from PIL import Image

from app import (
    CATEGORIES_META,
    map_spans_to_boxes,
    ocr_image,
    run_pii_analysis,
)

HERE = Path(__file__).resolve().parent          # backend/
PROJECT_ROOT = HERE.parent
EXAMPLES_DIR = PROJECT_ROOT / "example-images"
BUILD_DIR = PROJECT_ROOT / "frontend" / "build"
EXAMPLE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _list_examples() -> list[str]:
    if not EXAMPLES_DIR.is_dir():
        return []
    return sorted(
        p.name for p in EXAMPLES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in EXAMPLE_EXTS
    )


@functools.lru_cache(maxsize=64)
def _example_thumbnail(name: str) -> bytes:
    path = EXAMPLES_DIR / name
    img = Image.open(path).convert("RGB")
    img.thumbnail((480, 480))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True)
    return buf.getvalue()


# =====================================================================
# SERVER
# =====================================================================

server = gr.Server()

# Open CORS so the SvelteKit dev server (vite, :5173) can talk to us on :7860.
# In prod everything is same-origin and this is a no-op.
server.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Examples (plain GET, no queue) ──────────────────────────────────
@server.get("/api/examples")
async def api_examples():
    return JSONResponse({"examples": _list_examples()})


@server.get("/examples/{name}")
async def get_example(name: str, thumb: int = 0):
    safe = Path(name).name
    if Path(safe).suffix.lower() not in EXAMPLE_EXTS:
        return JSONResponse({"error": "invalid file type"}, 400)
    path = EXAMPLES_DIR / safe
    if not path.is_file():
        return JSONResponse({"error": "not found"}, 404)
    if thumb:
        return Response(
            content=_example_thumbnail(safe),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return FileResponse(path, headers={"Cache-Control": "public, max-age=3600"})


# ── Static category table (small, cacheable, hit once on app boot) ──
@server.get("/api/meta")
async def api_meta():
    return JSONResponse(
        {
            "categories_meta": {
                k: {"color": v["color"], "label": v["label"]}
                for k, v in CATEGORIES_META.items()
            }
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ── Queued compute endpoint ─────────────────────────────────────────
@server.api(name="anonymize_screenshot")
def anonymize_screenshot_api(image: FileData) -> dict:
    """OCR + PII over an uploaded image.

    Returns JSON only — the original image stays on the client (it already
    has the File). Same FileData-in pattern as the BiRefNet demo; the
    @gradio/client wraps FormData uploads for us.
    """
    try:
        path = image.get("path") or image.get("url") or ""
        if not path:
            return {"error": "expected an image file"}

        img = Image.open(path).convert("RGB")
        ocr = ocr_image(img)
        if not ocr["text"].strip():
            return {"error": "No text detected in the image."}

        source_text, spans = run_pii_analysis(ocr["text"])
        if source_text != ocr["text"]:
            spans = [s for s in spans if s["end"] <= len(ocr["text"])]
        boxes = map_spans_to_boxes(ocr["words"], spans)

        return {
            "filename": Path(path).name,
            "width":    img.width,
            "height":   img.height,
            "boxes":    boxes,
            "text":     ocr["text"],
            "spans":    spans,
        }
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return {"error": f"{type(e).__name__}: {e}"}


# ── SvelteKit static build ──────────────────────────────────────────
# adapter-static emits build/index.html (SPA fallback) + build/_app/<chunks>.
# We mount /_app for the chunks and serve top-level files explicitly.
if BUILD_DIR.is_dir():
    app_dir = BUILD_DIR / "_app"
    if app_dir.is_dir():
        server.mount("/_app", StaticFiles(directory=app_dir), name="_app")

    @server.get("/", response_class=HTMLResponse)
    async def root():
        return (BUILD_DIR / "index.html").read_text(encoding="utf-8")

    @server.get("/favicon.svg")
    async def favicon():
        p = BUILD_DIR / "favicon.svg"
        if p.is_file():
            return FileResponse(p)
        return Response(status_code=404)
else:
    @server.get("/", response_class=HTMLResponse)
    async def root_dev():
        return (
            "<h1>frontend not built</h1>"
            "<p>run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code> "
            "for production, or use <code>npm run dev</code> on port 5173.</p>"
        )


if __name__ == "__main__":
    server.launch(server_name="0.0.0.0", server_port=7860, show_error=True)
