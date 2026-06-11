"""
OCR + PII pipeline for the Swedish Ranymizer.

Public surface:
  - CATEGORIES_META         per-label colour + display label for the UI
  - ocr_image(img)          Image -> {text, words}   (lines are surfaced as "words")
  - run_pii_analysis(text)  text -> (text, spans)
  - map_spans_to_boxes(lines, spans) -> [boxes]
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
import torch
from gliner2 import GLiNER2
from paddleocr import PaddleOCR
from PIL import Image

try:
    import spaces
except ImportError:
    spaces = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "1" if default else "0").lower()
    return raw not in {"0", "false", "no"}


USE_GPU = _env_bool("USE_GPU", True)
HAS_CUDA = torch.cuda.is_available() or (spaces is not None)
DEVICE = "gpu:0" if USE_GPU and HAS_CUDA else "cpu"

# `lang=sv` triggers PaddleOCR's `latin_PP-OCRv5_mobile_rec`, which covers
# å/ä/ö. The default (no `lang`) loads the Chinese-trained recogniser and
# silently emits `□` for any non-Chinese/-English/-Japanese glyph.
OCR_LANG = os.getenv("OCR_LANG", "sv")

USE_DOC_ORIENTATION_CLASSIFY = _env_bool("USE_DOC_ORIENTATION_CLASSIFY", False)
USE_DOC_UNWARPING = _env_bool("USE_DOC_UNWARPING", False)
USE_TEXTLINE_ORIENTATION = _env_bool("USE_TEXTLINE_ORIENTATION", False)

GLINER_MODEL = os.getenv("GLINER_MODEL", "fastino/gliner2-privacy-filter-PII-multi")

_MODELS_DIR = Path(__file__).resolve().parent / "models"
LORA_ADAPTER_PATH = _MODELS_DIR / "lora_pf"  # privacy-filter base + our dense LoRA
FT_MODEL_PATH = _MODELS_DIR / "ft_pf"  # full fine-tune of the privacy-filter base


class ModelVariant(StrEnum):
    """Which Swedish-PII checkpoint to run. The frontend's ``modelName`` selects one."""

    BASELINE = "baseline"  # off-the-shelf privacy-filter (no fine-tuning)
    LORA = "lora"  # privacy-filter + our dense LoRA adapter (~0.99 on synthetic)
    FT = "ft"  # full fine-tune of the privacy-filter base


# The trained models (lora/ft) were fine-tuned conditioning on THESE Swedish label
# names. Querying them with the English-canonical names below (phone_number,
# bank_account) measurably hurt recall, so we always condition on the trained names
# and remap the output to the canonical keys the frontend colours by.
TRAINED_LABELS: dict[str, str] = {
    "person": "An individual's name (given name + surname, or initials).",
    "email": "An email address, e.g. firstname.lastname@example.se.",
    "phone": "A phone number in Swedish or international format (+46, 070-..., 08-...).",
    "address": "A street address: street name + number, postnummer, city.",
    "personnummer": "A Swedish personal identity number (YYYYMMDD-XXXX or YYMMDD-XXXX).",
    "organisationsnummer": "A Swedish organisation number (XXXXXX-XXXX).",
    "bank": "Bank account information: bankgiro, plusgiro, IBAN, BIC, clearing+account.",
    "date": "A calendar date in Swedish format (2024-05-20, 20 maj 2024, etc).",
    "url": "A web URL (https://..., www...).",
    "health": "Health data: diagnoses, medication, treatment, disability, sick leave, mental health.",
    "religion_ethnicity": "Religious belief, philosophical conviction, ethnic origin, or trade-union membership.",
    "criminal": "Criminal offences or convictions (GDPR Art. 10): misstanke, åtal, fällande dom, påföljd.",
    "card_number": "A payment card PAN (primary account number).",
    "iban": "A Swedish IBAN (international bank account number).",
    "ip_address": "An IP address (IPv4 or IPv6).",
    "username": "An account login handle (username).",
    "date_of_birth": "A person's date of birth.",
}

# Trained label name -> the canonical key the frontend's CATEGORIES_META colours by.
# Only the two that differ need an entry; everything else maps to itself.
LABEL_ALIAS: dict[str, str] = {"phone": "phone_number", "bank": "bank_account"}

PII_LABELS: dict[str, str] = {
    "person": "Full name of a person",
    "email": "Email address",
    "phone_number": "Phone number, including country code variants",
    "address": "Street address, postal address, or physical location",
    "date_of_birth": "Date of birth",
    "personnummer": "Swedish personal identity number, format YYMMDD-XXXX or YYYYMMDD-XXXX, 10 or 12 digits with hyphen or plus separator",
    "organisationsnummer": "Swedish organisation number, format NNNNNN-NNNN, 10 digits with hyphen",
    "bank_account": "Bank account number including Swedish bankgiro or plusgiro",
    "iban": "International Bank Account Number, starts with two-letter country code",
    "card_number": "Credit or debit card number",
    "url": "URL or web link",
    "ip_address": "IP address",
    "username": "User name or login handle",
    # GDPR Art. 9 / dataskyddslag 3 kap. — sensitive personal data. Required
    # for municipal documents (social services, school, healthcare) per
    # Slutrapport IMY-2024-5156, §4.3 and §6.3.
    "health": "Health information: diagnoses, medication, treatment, disability, sick leave, mental health",
    "religion_ethnicity": "Religious belief, philosophical conviction, ethnic origin, or trade-union membership",
    "criminal": "Criminal offences or convictions (GDPR Art. 10)",
    "date": "A calendar date",
}

CATEGORIES_META: dict[str, dict[str, str]] = {
    "person": {"color": "#ef4444", "label": "Person"},
    "email": {"color": "#f97316", "label": "Email"},
    "phone_number": {"color": "#f59e0b", "label": "Phone"},
    "address": {"color": "#84cc16", "label": "Address"},
    "date_of_birth": {"color": "#22c55e", "label": "Date of birth"},
    "personnummer": {"color": "#06b6d4", "label": "Personnummer"},
    "organisationsnummer": {"color": "#0ea5e9", "label": "Organisationsnr"},
    "bank_account": {"color": "#6366f1", "label": "Bank account"},
    "iban": {"color": "#8b5cf6", "label": "IBAN"},
    "card_number": {"color": "#a855f7", "label": "Card"},
    "url": {"color": "#ec4899", "label": "URL"},
    "ip_address": {"color": "#f43f5e", "label": "IP"},
    "username": {"color": "#64748b", "label": "Username"},
    "health": {"color": "#dc2626", "label": "Health"},
    "religion_ethnicity": {"color": "#7c3aed", "label": "Religion / ethnicity"},
    "criminal": {"color": "#b91c1c", "label": "Criminal"},
    "date": {"color": "#10b981", "label": "Date"},
}


_ocr_instance: PaddleOCR | None = None
_models: dict[ModelVariant, GLiNER2] = {}


def get_ocr() -> PaddleOCR:
    """Default OCR pipeline using env-var-driven flags. Used when the request
    didn't override preprocessing settings."""
    global _ocr_instance
    if _ocr_instance is not None:
        return _ocr_instance

    _ocr_instance = _build_ocr(
        use_doc_orientation_classify=USE_DOC_ORIENTATION_CLASSIFY,
        use_doc_unwarping=USE_DOC_UNWARPING,
        use_textline_orientation=USE_TEXTLINE_ORIENTATION,
    )
    return _ocr_instance


# Cache of PaddleOCR pipelines keyed by the (orient, unwarp, textline) tuple.
# Building a pipeline reloads model weights, so we memoise so toggling a
# preprocessing flag on one request doesn't pay the cold start every time.
_ocr_cache: dict[tuple[bool, bool, bool], PaddleOCR] = {}


def _build_ocr(
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    use_textline_orientation: bool,
) -> PaddleOCR:
    dtype = os.getenv("INFERENCE_DTYPE", "float32")
    print(
        f"[ocr] loading PaddleOCR 3.5  device={DEVICE}  lang={OCR_LANG}  dtype={dtype}  "
        f"orient={use_doc_orientation_classify}  unwarp={use_doc_unwarping}  "
        f"textline={use_textline_orientation}"
    )
    return PaddleOCR(
        device=DEVICE,
        engine="transformers",
        lang=OCR_LANG,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        use_textline_orientation=use_textline_orientation,
        engine_config={"dtype": dtype},
    )


def get_ocr_for(
    use_doc_orientation_classify: bool | None = None,
    use_doc_unwarping: bool | None = None,
    use_textline_orientation: bool | None = None,
) -> PaddleOCR:
    """Per-request pipeline. `None` for any flag means "use the env default"
    so an empty config still hits the shared singleton."""
    key = (
        USE_DOC_ORIENTATION_CLASSIFY
        if use_doc_orientation_classify is None
        else use_doc_orientation_classify,
        USE_DOC_UNWARPING if use_doc_unwarping is None else use_doc_unwarping,
        USE_TEXTLINE_ORIENTATION if use_textline_orientation is None else use_textline_orientation,
    )
    # The default singleton owns the default-key slot — share it.
    if key == (USE_DOC_ORIENTATION_CLASSIFY, USE_DOC_UNWARPING, USE_TEXTLINE_ORIENTATION):
        return get_ocr()
    cached = _ocr_cache.get(key)
    if cached is not None:
        return cached
    pipeline = _build_ocr(*key)
    _ocr_cache[key] = pipeline
    return pipeline


def _load_variant(variant: ModelVariant) -> GLiNER2:
    """Build one GLiNER2 checkpoint. The base is shared by name, but each variant
    gets its OWN instance so adapter state never leaks between requests."""
    kwargs: dict[str, Any] = {"map_location": "cuda" if HAS_CUDA else "cpu"}
    if variant is ModelVariant.FT:
        if not (FT_MODEL_PATH / "model.safetensors").exists():
            raise FileNotFoundError(f"full-FT checkpoint missing at {FT_MODEL_PATH}")
        print(f"[pii] loading FT checkpoint {FT_MODEL_PATH}")
        model = GLiNER2.from_pretrained(str(FT_MODEL_PATH), **kwargs)
    else:
        print(f"[pii] loading {GLINER_MODEL} (variant={variant})")
        model = GLiNER2.from_pretrained(GLINER_MODEL, **kwargs)
        if variant is ModelVariant.LORA:
            if not (LORA_ADAPTER_PATH / "adapter_config.json").exists():
                raise FileNotFoundError(f"LoRA adapter missing at {LORA_ADAPTER_PATH}")
            model.load_adapter(str(LORA_ADAPTER_PATH))
    model.eval()
    return model


def get_gliner(variant: ModelVariant = ModelVariant.BASELINE) -> GLiNER2:
    """Return the requested PII model, loading + caching it on first use.

    Variants are cached as separate instances (cheap: mdeberta-base ~0.3-0.5 GB
    each), so switching is instant after the first load and thread-safe — no
    per-request adapter swapping.
    """
    cached = _models.get(variant)
    if cached is not None:
        return cached
    model = _load_variant(variant)
    _models[variant] = model
    return model


if _env_bool("LOAD_MODELS_ON_STARTUP", True):
    try:
        get_ocr()
        get_gliner(ModelVariant.BASELINE)  # lora/ft load lazily on first request
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] eager model load failed: {exc!r}")


def _to_python(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    return value


def _polygon_bounds(poly: Any) -> tuple[int, int, int, int] | None:
    try:
        xs = [int(point[0]) for point in poly]
        ys = [int(point[1]) for point in poly]
    except (TypeError, IndexError, ValueError):
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _is_non_empty_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _extract_page_lines(page: Any, char_offset: int) -> tuple[list[dict[str, Any]], int]:
    """Convert one PaddleOCR page into structured lines. Returns (lines, next_offset)."""
    page_json = getattr(page, "json", {}) or {}
    # PaddleOCR 3.5 transformers engine nests results under "res"; older
    # versions had them at the top level.
    page_res = page_json.get("res", page_json) or {}
    rec_texts = page_res.get("rec_texts", []) or []
    rec_polys = page_res.get("rec_polys", []) or []

    lines: list[dict[str, Any]] = []
    offset = char_offset
    # strict=False — PaddleOCR can drop entries from one array but not the
    # other when post-processing rejects them.
    for raw_text, raw_poly in zip(rec_texts, rec_polys, strict=False):
        text = str(raw_text) if raw_text is not None else ""
        if not text.strip():
            continue

        bounds = _polygon_bounds(_to_python(raw_poly))
        if bounds is None:
            continue
        x0, y0, x1, y1 = bounds

        end = offset + len(text)
        lines.append(
            {
                "text": text,
                "start": offset,
                "end": end,
                "x": x0,
                "y": y0,
                "w": x1 - x0,
                "h": y1 - y0,
            }
        )
        offset = end + 1  # +1 for the '\n' separator

    return lines, offset


def ocr_image(
    image: Image.Image,
    use_doc_orientation_classify: bool | None = None,
    use_doc_unwarping: bool | None = None,
    use_textline_orientation: bool | None = None,
) -> dict[str, Any]:
    """Run PaddleOCR. Returns {"text": joined, "words": [line_dict, ...]}."""
    pipeline = get_ocr_for(
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        use_textline_orientation=use_textline_orientation,
    )
    array = np.array(image.convert("RGB"))
    result = pipeline.predict(array)

    all_lines: list[dict[str, Any]] = []
    char_offset = 0
    detected_polys = 0
    recognised_texts = 0

    for page in result:
        page_json = getattr(page, "json", {}) or {}
        page_res = page_json.get("res", page_json) or {}
        detected_polys += len(page_res.get("rec_polys", []) or [])
        recognised_texts += sum(
            1 for t in (page_res.get("rec_texts") or []) if _is_non_empty_text(t)
        )

        page_lines, char_offset = _extract_page_lines(page, char_offset)
        all_lines.extend(page_lines)

    print(
        f"[ocr] image={image.width}x{image.height}  "
        f"detected_polys={detected_polys}  recognised_texts={recognised_texts}  "
        f"kept_lines={len(all_lines)}"
    )
    joined = "\n".join(line["text"] for line in all_lines)
    return {"text": joined, "words": all_lines}


def _gpu(fn):
    """ZeroGPU decorator; no-op when running locally."""
    if spaces is None:
        return fn
    return spaces.GPU(duration=60)(fn)


def _entity_to_span(label: str, entity: Any) -> dict[str, Any] | None:
    if not isinstance(entity, dict):
        return None
    try:
        start = int(entity["start"])
        end = int(entity["end"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "label": label,
        "text": entity.get("text", ""),
        "start": start,
        "end": end,
        "confidence": float(entity.get("confidence", 1.0)),
    }


def _luhn_check(digits: str) -> bool:
    """Standard Luhn checksum. Works on digit-only strings (post-stripping)."""
    if not digits or not digits.isdigit():
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _apply_post_filter(span: dict[str, Any], rule: dict[str, Any]) -> bool:
    """Return True if the span passes this label's rule. Rule fields are
    the same shape as the frontend's LabelRule type."""
    if not rule:
        return True
    text = str(span.get("text", ""))

    # Per-label confidence floor (rule.threshold > 0 overrides the global).
    rule_threshold = float(rule.get("threshold", 0) or 0)
    if rule_threshold > 0 and float(span.get("confidence", 1)) < rule_threshold:
        return False

    # Regex filter — full / partial / exclude.
    pattern = (rule.get("regex") or "").strip()
    if pattern:
        try:
            re_obj = __import__("re").compile(pattern)
        except Exception:  # noqa: BLE001
            re_obj = None
        if re_obj is not None:
            mode = rule.get("regexMode", "full")
            match = re_obj.search(text)
            if mode == "full":
                if not (match and match.group(0) == text):
                    return False
            elif mode == "partial":
                if not match:
                    return False
            elif mode == "exclude":
                if match:
                    return False

    # Luhn — only meaningful on digit-only spans (with separator chars
    # stripped). Skip when the span has non-digit content (e.g. names).
    if rule.get("validateLuhn"):
        digits = "".join(c for c in text if c.isdigit())
        if digits and not _luhn_check(digits):
            return False

    return True


@_gpu
def run_pii_analysis(
    text: str,
    threshold: float = 0.5,
    labels: dict[str, str] | None = None,
    rules: dict[str, dict[str, Any]] | None = None,
    allowed_labels: set[str] | None = None,
    variant: ModelVariant = ModelVariant.BASELINE,
) -> tuple[str, list[dict[str, Any]]]:
    """Run the selected GLiNER2 ``variant`` then apply per-label post-filters.

    - `variant` picks the checkpoint (baseline / lora / ft).
    - `labels` is the dict the model conditions on; defaults to the trained
      Swedish names (TRAINED_LABELS) that all three variants respond to best.
    - output labels are remapped to the canonical frontend keys via LABEL_ALIAS
      (e.g. ``phone`` -> ``phone_number``) before `allowed_labels`/`rules` apply.
    - `allowed_labels` (canonical keys) filters to the labels the request enabled.
    - `rules` is the per-label post-filter map (regex / threshold / Luhn).
    """
    if not text or not text.strip():
        return text, []

    label_dict = labels if labels is not None else TRAINED_LABELS
    if not label_dict:
        return text, []

    model = get_gliner(variant)
    with torch.inference_mode():
        result = model.extract_entities(
            text,
            label_dict,
            threshold=threshold,
            include_spans=True,
            include_confidence=True,
        )

    spans: list[dict[str, Any]] = []
    for raw_label, entities in (result.get("entities") or {}).items():
        label = LABEL_ALIAS.get(raw_label, raw_label)
        if allowed_labels is not None and label not in allowed_labels:
            continue
        rule = (rules or {}).get(label) or {}
        for entity in entities or []:
            span = _entity_to_span(label, entity)
            if span is None:
                continue
            if not _apply_post_filter(span, rule):
                continue
            spans.append(span)

    spans.sort(key=lambda s: (s["start"], s["end"]))
    return text, spans


def mask_text(text: str, spans: list[dict[str, Any]]) -> str:
    """Redact every detected span in ``text`` with a ``[LABEL]`` placeholder.

    Splices right-to-left so earlier character offsets stay valid, and skips a
    span that overlaps one already replaced (keeps the right-most match).
    """
    ordered = sorted(spans, key=lambda s: s["start"])
    masked = text
    next_start = len(text)
    for span in reversed(ordered):
        start, end = int(span["start"]), int(span["end"])
        if not 0 <= start < end <= len(text) or end > next_start:
            continue
        masked = masked[:start] + f"[{str(span['label']).upper()}]" + masked[end:]
        next_start = start
    return masked


BOX_PADDING_PX = 2


def _line_overlaps_span(line: dict[str, Any], span_start: int, span_end: int) -> bool:
    return not (line["end"] <= span_start or line["start"] >= span_end)


def _single_line_box(span: dict[str, Any], line: dict[str, Any]) -> dict[str, Any]:
    """Narrow a span to its proportional x-range within one OCR line.

    Assumes roughly uniform per-character width — approximate, but works
    well for screen-rendered text and is tighter than line-level masking.
    """
    line_length = max(1, line["end"] - line["start"])
    local_start = max(0, span["start"] - line["start"])
    local_end = min(line_length, span["end"] - line["start"])
    x_start = line["x"] + int(line["w"] * local_start / line_length)
    x_end = line["x"] + int(line["w"] * local_end / line_length)
    return {
        "label": span["label"],
        "text": span.get("text", ""),
        "x": max(0, x_start - BOX_PADDING_PX),
        "y": line["y"],
        "w": max(1, (x_end - x_start) + 2 * BOX_PADDING_PX),
        "h": line["h"],
    }


def _union_box(span: dict[str, Any], lines: list[dict[str, Any]]) -> dict[str, Any]:
    x0 = min(line["x"] for line in lines)
    y0 = min(line["y"] for line in lines)
    x1 = max(line["x"] + line["w"] for line in lines)
    y1 = max(line["y"] + line["h"] for line in lines)
    return {
        "label": span["label"],
        "text": span.get("text", ""),
        "x": x0,
        "y": y0,
        "w": x1 - x0,
        "h": y1 - y0,
    }


def map_spans_to_boxes(
    lines: list[dict[str, Any]],
    spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for span in spans:
        overlapping = [ln for ln in lines if _line_overlaps_span(ln, span["start"], span["end"])]
        if not overlapping:
            continue
        if len(overlapping) == 1:
            boxes.append(_single_line_box(span, overlapping[0]))
        else:
            boxes.append(_union_box(span, overlapping))
    return boxes
