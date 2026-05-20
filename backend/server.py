"""
Gradio Server backend for the Swedish Ranymizer.

Same pattern as the BiRefNet demo: gr.Server() with @server.api(...) for the
queued compute endpoint, plain @server.get for static reads, plus a static-file
mount for the SvelteKit build.

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

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
EXAMPLES_DIR = PROJECT_ROOT / "example-images"
BUILD_DIR = PROJECT_ROOT / "frontend" / "build"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
THUMBNAIL_SIZE = (480, 480)
THUMBNAIL_QUALITY = 82


def _is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def list_example_images() -> list[str]:
    if not EXAMPLES_DIR.is_dir():
        return []
    return sorted(p.name for p in EXAMPLES_DIR.iterdir() if _is_image_file(p))


@functools.lru_cache(maxsize=64)
def build_thumbnail(name: str) -> bytes:
    image = Image.open(EXAMPLES_DIR / name).convert("RGB")
    image.thumbnail(THUMBNAIL_SIZE)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
    return buffer.getvalue()


server = gr.Server()

# CORS for local SvelteKit dev (vite on :5173/:5174). Production is same-origin.
server.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@server.get("/api/examples")
async def api_examples():
    return JSONResponse({"examples": list_example_images()})


@server.get("/examples/{name}")
async def get_example(name: str, thumb: int = 0):
    safe_name = Path(name).name
    if Path(safe_name).suffix.lower() not in IMAGE_EXTENSIONS:
        return JSONResponse({"error": "invalid file type"}, 400)

    path = EXAMPLES_DIR / safe_name
    if not path.is_file():
        return JSONResponse({"error": "not found"}, 404)

    if thumb:
        return Response(
            content=build_thumbnail(safe_name),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return FileResponse(path, headers={"Cache-Control": "public, max-age=3600"})


@server.get("/api/meta")
async def api_meta():
    categories = {
        key: {"color": meta["color"], "label": meta["label"]}
        for key, meta in CATEGORIES_META.items()
    }
    return JSONResponse(
        {"categories_meta": categories},
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _ocr_line_to_debug_overlay(line: dict) -> dict:
    return {"text": line["text"], "x": line["x"], "y": line["y"], "w": line["w"], "h": line["h"]}


@server.api(name="anonymize_screenshot")
def anonymize_screenshot_api(image: FileData) -> dict:
    """OCR + PII over an uploaded image. JSON-only response (client keeps the original)."""
    try:
        path = image.get("path") or image.get("url") or ""
        if not path:
            return {"error": "expected an image file"}

        pil_image = Image.open(path).convert("RGB")
        ocr = ocr_image(pil_image)

        spans: list = []
        boxes: list = []
        if ocr["text"].strip():
            source_text, spans = run_pii_analysis(ocr["text"])
            if source_text != ocr["text"]:
                spans = [s for s in spans if s["end"] <= len(ocr["text"])]
            boxes = map_spans_to_boxes(ocr["words"], spans)

        return {
            "filename": Path(path).name,
            "width": pil_image.width,
            "height": pil_image.height,
            "boxes": boxes,
            "text": ocr["text"],
            "spans": spans,
            "ocr_lines": [_ocr_line_to_debug_overlay(line) for line in ocr["words"]],
        }
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return {"error": f"{type(exc).__name__}: {exc}"}


# adapter-static emits build/index.html (SPA fallback) + build/_app/<chunks>.
if BUILD_DIR.is_dir():
    app_chunks_dir = BUILD_DIR / "_app"
    if app_chunks_dir.is_dir():
        server.mount("/_app", StaticFiles(directory=app_chunks_dir), name="_app")

    @server.get("/", response_class=HTMLResponse)
    async def serve_index():
        return (BUILD_DIR / "index.html").read_text(encoding="utf-8")

    @server.get("/favicon.svg")
    async def serve_favicon():
        favicon = BUILD_DIR / "favicon.svg"
        if favicon.is_file():
            return FileResponse(favicon)
        return Response(status_code=404)
else:

    @server.get("/", response_class=HTMLResponse)
    async def serve_dev_hint():
        return (
            "<h1>frontend not built</h1>"
            "<p>run <code>cd frontend &amp;&amp; bun install &amp;&amp; bun run build</code> "
            "for production, or use <code>bun run dev</code> on port 5173.</p>"
        )


if __name__ == "__main__":
    server.launch(server_name="0.0.0.0", server_port=7860, show_error=True)
