"""
Gradio Server backend for the Swedish Ranymizer.

Same pattern as the BiRefNet demo: gr.Server() with @server.api(...) for the
queued compute endpoint, plain @server.get for static reads, plus a static-file
mount for the SvelteKit build.

Routes:
  GET  /                          → frontend/build/index.html
  GET  /_app/*                    → static SvelteKit chunks
  GET  /favicon.svg               → frontend/build/favicon.svg
  GET  /api/meta                  → category colours/labels (cacheable)
  POST /anonymize_screenshot      → queued compute (Gradio JS client)
"""

from __future__ import annotations

import traceback
from collections.abc import Iterator
from pathlib import Path

import gradio as gr
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from gradio.data_classes import FileData
from PIL import Image

from app import (
    CATEGORIES_META,
    PII_LABELS,
    map_spans_to_boxes,
    ocr_image,
    run_pii_analysis,
)
from schema import parse_config

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
BUILD_DIR = PROJECT_ROOT / "frontend" / "build"


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


@server.api(name="anonymize_screenshot", stream_every=0.05)
def anonymize_screenshot_api(image: FileData, config: dict | None = None) -> Iterator[dict]:
    """OCR + PII over an uploaded image. **Streaming** generator — yields a
    sequence of partial dicts so the client can paint OCR text/lines as soon
    as PaddleOCR finishes and update the pipeline graph between stages.

    Wire shape (each yield is one SSE frame):

      {"stage": "ocr_started", "filename": ...}
      {"stage": "ocr_done",    "filename","width","height","text","ocr_lines"}
      {"stage": "gliner_started"}
      {"stage": "done", ...full AnonymizeResult...}

    Final `done` frame carries the complete payload so any legacy caller that
    only reads the last frame stays compatible.
    """
    try:
        path = image.get("path") or image.get("url") or ""
        if not path:
            yield {"stage": "done", "error": "expected an image file"}
            return

        cfg = parse_config(config)
        pil_image = Image.open(path).convert("RGB")
        filename = Path(path).name

        yield {"stage": "ocr_started", "filename": filename}

        # OCR with optional preprocessing overrides.
        ocr = ocr_image(
            pil_image,
            use_doc_orientation_classify=cfg.paddleocr.useDocOrientationClassify,
            use_doc_unwarping=cfg.paddleocr.useDocUnwarping,
            use_textline_orientation=cfg.paddleocr.useTextlineOrientation,
        )

        ocr_lines = [_ocr_line_to_debug_overlay(line) for line in ocr["words"]]

        # Surface OCR results immediately so the text sidebar populates while
        # GLiNER2 is still warming up.
        yield {
            "stage": "ocr_done",
            "filename": filename,
            "width": pil_image.width,
            "height": pil_image.height,
            "text": ocr["text"],
            "ocr_lines": ocr_lines,
        }

        spans: list = []
        boxes: list = []
        if ocr["text"].strip():
            yield {"stage": "gliner_started"}

            # Build the labels dict GLiNER2 conditions on. Defaults + custom
            # labels (merged), filtered by `enabledLabels` if the client sent
            # an explicit selection.
            gliner_cfg = cfg.gliner
            labels_dict = dict(PII_LABELS)
            # Allow client to override default descriptions.
            for key, desc in gliner_cfg.descriptions.items():
                if key in labels_dict and desc:
                    labels_dict[key] = desc
            # Inject custom labels — these are the user-defined PII types.
            for key, meta in gliner_cfg.customLabels.items():
                labels_dict[key] = meta.description or meta.displayLabel

            allowed = set(gliner_cfg.enabledLabels) if gliner_cfg.enabledLabels else None
            # If the client sent an empty allowed set, treat it as "all" so
            # we don't accidentally silence the model on an unfilled request.
            if allowed is not None and not allowed:
                allowed = None

            rules_dict = {k: v.model_dump() for k, v in gliner_cfg.rules.items()}

            source_text, spans = run_pii_analysis(
                ocr["text"],
                threshold=gliner_cfg.threshold or 0.5,
                labels=labels_dict if labels_dict else None,
                rules=rules_dict,
                allowed_labels=allowed,
            )
            if source_text != ocr["text"]:
                spans = [s for s in spans if s["end"] <= len(ocr["text"])]
            boxes = map_spans_to_boxes(ocr["words"], spans)

        yield {
            "stage": "done",
            "filename": filename,
            "width": pil_image.width,
            "height": pil_image.height,
            "boxes": boxes,
            "text": ocr["text"],
            "spans": spans,
            "ocr_lines": ocr_lines,
        }
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        yield {"stage": "done", "error": f"{type(exc).__name__}: {exc}"}


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
            "for production, or use <code>bun run dev</code> on port 5174.</p>"
        )


if __name__ == "__main__":
    server.launch(server_name="0.0.0.0", server_port=7860, show_error=True)
