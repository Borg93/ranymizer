"""
app.py — OCR + PII pipeline for the Swedish Ranymizer prototype.

Pipeline:
  1. PaddleOCR 3.5 (transformers backend, PP-OCRv5_server) → line-level text + polygons
  2. GLiNER2-PII (label-conditioned encoder) → entity spans over text
  3. Project char spans back to pixel boxes via OCR line geometry

Public surface (matches the original Ranymizer):
  - CATEGORIES_META    : per-label color + display label for the UI
  - ocr_image(img)     : Image -> {text, words}   ("words" are OCR lines here)
  - run_pii_analysis(text) -> (text, spans)
  - map_spans_to_boxes(lines, spans) -> [boxes]
"""
from __future__ import annotations

import os
from typing import Any

import numpy as np
import torch
from PIL import Image

# Real imports up front so failures surface at startup, not on first request.
# Loading the actual models is still lazy (see get_ocr / get_gliner below).
from paddleocr import PaddleOCR
from gliner2 import GLiNER2

try:
    import spaces  # ZeroGPU; no-op locally
except ImportError:
    spaces = None


# ──────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────
REQUEST_GPU = os.getenv("USE_GPU", "1").lower() not in {"0", "false", "no"}
HAS_CUDA = torch.cuda.is_available() or (spaces is not None)
DEVICE = "gpu:0" if REQUEST_GPU and HAS_CUDA else "cpu"

# PaddleOCR 3.5 supports "5 major mainstream text types: Chinese, Pinyin,
# Traditional Chinese, English, Japanese". For Western-European text we need
# the Latin recognition model, which is auto-selected when lang is any
# Latin-script language code (sv / de / fr / es / it / pt / …). Empirically
# verified: lang="sv" -> latin_PP-OCRv5_mobile_rec.
OCR_LANG = os.getenv("OCR_LANG", "sv")

# Optional preprocessing. Each costs a bit of latency but improves recall on
# scanned / rotated / skewed pages — turn on when redacting real-world docs.
USE_DOC_ORIENTATION_CLASSIFY = os.getenv("USE_DOC_ORIENTATION_CLASSIFY", "0").lower() in {
    "1", "true", "yes",
}
USE_DOC_UNWARPING = os.getenv("USE_DOC_UNWARPING", "0").lower() in {"1", "true", "yes"}
USE_TEXTLINE_ORIENTATION = os.getenv("USE_TEXTLINE_ORIENTATION", "0").lower() in {
    "1", "true", "yes",
}

# GLiNER2-PII model id.
GLINER_MODEL = os.getenv("GLINER_MODEL", "fastino/gliner2-privacy-filter-PII-multi")

# Label-conditioned schema. Descriptions are in English (the model has English +
# Dutch/German/French/Italian/Spanish/Portuguese training); Swedish entity
# *surface forms* are handled by the multilingual encoder. Swedish-specific
# identifiers (personnummer, orgnr) need format hints in the description because
# the model has not seen those formats during training — this is zero-shot until
# you LoRA-tune. Expect modest recall on personnummer/orgnr out of the box.
PII_LABELS: dict[str, str] = {
    "person":              "Full name of a person",
    "email":               "Email address",
    "phone_number":        "Phone number, including country code variants",
    "address":             "Street address, postal address, or physical location",
    "date_of_birth":       "Date of birth",
    "personnummer":        "Swedish personal identity number, format YYMMDD-XXXX or YYYYMMDD-XXXX, 10 or 12 digits with hyphen or plus separator",
    "organisationsnummer": "Swedish organisation number, format NNNNNN-NNNN, 10 digits with hyphen",
    "bank_account":        "Bank account number including Swedish bankgiro or plusgiro",
    "iban":                "International Bank Account Number, starts with two-letter country code",
    "card_number":         "Credit or debit card number",
    "url":                 "URL or web link",
    "ip_address":          "IP address",
    "username":            "User name or login handle",
}

# Per-category metadata used by the frontend overlay.
CATEGORIES_META: dict[str, dict[str, str]] = {
    "person":              {"color": "#ef4444", "label": "Person"},
    "email":               {"color": "#f97316", "label": "Email"},
    "phone_number":        {"color": "#f59e0b", "label": "Phone"},
    "address":             {"color": "#84cc16", "label": "Address"},
    "date_of_birth":       {"color": "#22c55e", "label": "Date of birth"},
    "personnummer":        {"color": "#06b6d4", "label": "Personnummer"},
    "organisationsnummer": {"color": "#0ea5e9", "label": "Organisationsnr"},
    "bank_account":        {"color": "#6366f1", "label": "Bank account"},
    "iban":                {"color": "#8b5cf6", "label": "IBAN"},
    "card_number":         {"color": "#a855f7", "label": "Card"},
    "url":                 {"color": "#ec4899", "label": "URL"},
    "ip_address":          {"color": "#f43f5e", "label": "IP"},
    "username":            {"color": "#64748b", "label": "Username"},
}


# ──────────────────────────────────────────────────────────────────────
# Lazy model singletons
# ──────────────────────────────────────────────────────────────────────
_OCR = None
_GLINER = None


def get_ocr() -> PaddleOCR:
    """PaddleOCR 3.5 with transformers backend, Latin-script recognition.

    `lang=sv` (Swedish) triggers PaddleOCR's `latin_PP-OCRv5_mobile_rec`
    model, which covers å/ä/ö and the rest of extended Latin. The default
    (no `lang`) would load the Chinese-trained `PP-OCRv5_*_rec`, which
    silently emits `□` for any non-Chinese/-English/-Japanese glyph.
    """
    global _OCR
    if _OCR is None:
        dtype = os.getenv("INFERENCE_DTYPE", "float32")
        print(
            f"[ocr] loading PaddleOCR 3.5  device={DEVICE}  lang={OCR_LANG}  dtype={dtype}  "
            f"orient={USE_DOC_ORIENTATION_CLASSIFY}  unwarp={USE_DOC_UNWARPING}  "
            f"textline={USE_TEXTLINE_ORIENTATION}"
        )
        _OCR = PaddleOCR(
            device=DEVICE,
            engine="transformers",
            lang=OCR_LANG,
            use_doc_orientation_classify=USE_DOC_ORIENTATION_CLASSIFY,
            use_doc_unwarping=USE_DOC_UNWARPING,
            use_textline_orientation=USE_TEXTLINE_ORIENTATION,
            engine_config={"dtype": dtype},
        )
    return _OCR


def get_gliner() -> GLiNER2:
    """GLiNER2-PII; quantize + compile when CUDA is available."""
    global _GLINER
    if _GLINER is None:
        print(f"[pii] loading {GLINER_MODEL}")
        map_location = "cuda" if HAS_CUDA else "cpu"
        kwargs: dict[str, Any] = {"map_location": map_location}
        if HAS_CUDA:
            kwargs["quantize"] = True
            kwargs["compile"] = os.getenv("GLINER_COMPILE", "1").lower() not in {"0", "false", "no"}
        _GLINER = GLiNER2.from_pretrained(GLINER_MODEL, **kwargs)
        _GLINER.eval()
    return _GLINER


# Eager-load so the first request doesn't pay the cold-start tax.
if os.getenv("LOAD_MODELS_ON_STARTUP", "1").lower() not in {"0", "false", "no"}:
    try:
        get_ocr()
        get_gliner()
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] eager model load failed: {exc!r}")


# ──────────────────────────────────────────────────────────────────────
# OCR
# ──────────────────────────────────────────────────────────────────────
def _to_python(v: Any) -> Any:
    """Numpy/Tensor scalars/arrays -> plain Python."""
    if hasattr(v, "tolist"):
        return v.tolist()
    if hasattr(v, "item"):
        return v.item()
    return v


def ocr_image(img: Image.Image) -> dict[str, Any]:
    """Run PaddleOCR and emit text + per-line boxes with char offsets.

    The frontend's `map_spans_to_boxes` consumer expects a list keyed by "words";
    we use OCR *lines* here, which is what PaddleOCR returns. The math works the
    same — each line has a [start, end) char range over the joined text.

    Returns
    -------
    {
      "text":  str,                          # all lines joined with '\\n'
      "words": [                             # OCR lines, not space-separated words
        {"text", "start", "end", "x", "y", "w", "h"}, ...
      ]
    }
    """
    pipeline = get_ocr()
    arr = np.array(img.convert("RGB"))
    result = pipeline.predict(arr)

    lines: list[dict[str, Any]] = []
    text_parts: list[str] = []
    offset = 0
    raw_polys = 0
    raw_texts = 0

    for page in result:
        page_json = getattr(page, "json", {}) or {}
        # PaddleOCR 3.5 transformers engine nests fields under "res".
        # Fall back to the top level for forward/backward compatibility.
        page_res = page_json.get("res", page_json) or {}
        rec_texts = page_res.get("rec_texts", []) or []
        rec_polys = page_res.get("rec_polys", []) or []
        raw_polys += len(rec_polys)
        raw_texts += sum(1 for t in rec_texts if str(t or "").strip())

        for txt, poly in zip(rec_texts, rec_polys):
            txt = str(txt) if txt is not None else ""
            if not txt.strip():
                continue
            poly = _to_python(poly)
            try:
                xs = [int(p[0]) for p in poly]
                ys = [int(p[1]) for p in poly]
            except (TypeError, IndexError, ValueError):
                continue
            x0, y0 = min(xs), min(ys)
            x1, y1 = max(xs), max(ys)
            start = offset
            end = offset + len(txt)
            lines.append({
                "text": txt,
                "start": start, "end": end,
                "x": x0, "y": y0,
                "w": x1 - x0, "h": y1 - y0,
            })
            text_parts.append(txt)
            offset = end + 1  # account for the '\n' separator

    print(
        f"[ocr] image={img.width}x{img.height}  "
        f"detected_polys={raw_polys}  recognised_texts={raw_texts}  "
        f"kept_lines={len(lines)}"
    )
    return {"text": "\n".join(text_parts), "words": lines}


# ──────────────────────────────────────────────────────────────────────
# PII via GLiNER2
# ──────────────────────────────────────────────────────────────────────
def _gpu(fn):
    """ZeroGPU decorator; no-op when running locally."""
    if spaces is None:
        return fn
    return spaces.GPU(duration=60)(fn)


@_gpu
def run_pii_analysis(
    text: str,
    threshold: float = 0.5,
) -> tuple[str, list[dict[str, Any]]]:
    """Extract PII spans from *text*. Returns (source_text, spans)."""
    if not text or not text.strip():
        return text, []

    model = get_gliner()
    with torch.inference_mode():
        result = model.extract_entities(
            text,
            PII_LABELS,
            threshold=threshold,
            include_spans=True,
            include_confidence=True,
        )

    spans: list[dict[str, Any]] = []
    for label, entities in (result.get("entities") or {}).items():
        if label not in CATEGORIES_META:
            continue
        for ent in entities or []:
            if not isinstance(ent, dict):
                continue
            spans.append({
                "label":      label,
                "text":       ent.get("text", ""),
                "start":      int(ent["start"]),
                "end":        int(ent["end"]),
                "confidence": float(ent.get("confidence", 1.0)),
            })

    spans.sort(key=lambda s: (s["start"], s["end"]))
    return text, spans


# ──────────────────────────────────────────────────────────────────────
# Char spans  →  pixel boxes
# ──────────────────────────────────────────────────────────────────────
def map_spans_to_boxes(
    lines: list[dict[str, Any]],
    spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project each PII span onto the OCR line(s) it overlaps.

    Single-line spans are narrowed within the line by character proportion;
    multi-line spans return the union bounding box. Proportional narrowing
    is approximate (assumes roughly uniform per-character width) but works
    well for screen-rendered Swedish PDF text and gives a tighter redaction
    than line-level masking.
    """
    boxes: list[dict[str, Any]] = []
    PAD = 2

    for sp in spans:
        s, e = sp["start"], sp["end"]
        overlap = [ln for ln in lines if not (ln["end"] <= s or ln["start"] >= e)]
        if not overlap:
            continue

        if len(overlap) == 1:
            ln = overlap[0]
            line_len = max(1, ln["end"] - ln["start"])
            local_s = max(0, s - ln["start"])
            local_e = min(line_len, e - ln["start"])
            x0 = ln["x"] + int(ln["w"] * local_s / line_len)
            x1 = ln["x"] + int(ln["w"] * local_e / line_len)
            boxes.append({
                "label": sp["label"],
                "text":  sp.get("text", ""),
                "x":     max(0, x0 - PAD),
                "y":     ln["y"],
                "w":     max(1, (x1 - x0) + 2 * PAD),
                "h":     ln["h"],
            })
        else:
            x0 = min(ln["x"] for ln in overlap)
            y0 = min(ln["y"] for ln in overlap)
            x1 = max(ln["x"] + ln["w"] for ln in overlap)
            y1 = max(ln["y"] + ln["h"] for ln in overlap)
            boxes.append({
                "label": sp["label"],
                "text":  sp.get("text", ""),
                "x": x0, "y": y0,
                "w": x1 - x0, "h": y1 - y0,
            })

    return boxes
