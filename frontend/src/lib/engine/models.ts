/**
 * Local-engine model manifest.
 *
 * The desktop target should ship the SAME models as the Python showcase —
 * PaddleOCR 3.5 (det → cls → rec) for OCR-with-line-polygons and
 * GLiNER2-PII for label-conditioned PII spans — both converted to ONNX
 * (Paddle2ONNX + the GLiNER2 ONNX export) and run via onnxruntime-web
 * inside the worker.
 *
 * ⚠️ DUMMY MANIFEST: the URLs below point to where the ONNX artefacts
 * WILL live once converted. Until then `worker.ts` falls back to the
 * transformers.js placeholders (TrOCR + multilingual NER) so the pipeline
 * is wired end-to-end. See ../../../../TODO.md for the conversion plan.
 *
 * Expected layout (Tauri build copies frontend/public/models/** into the
 * bundle; the showcase build serves the same path from the SvelteKit
 * static dir):
 *
 *   public/models/paddleocr/det.onnx       — text detection (line polygons)
 *   public/models/paddleocr/cls.onnx       — angle classifier
 *   public/models/paddleocr/rec.onnx       — text recognition
 *   public/models/paddleocr/dict.txt       — char dictionary for rec
 *   public/models/gliner2/model.onnx       — PII NER (label-conditioned)
 *   public/models/gliner2/tokenizer.json
 *   public/models/gliner2/labels.json      — categories + descriptions
 */

export type OnnxSpec = {
  /** Path served by the SvelteKit static dir / Tauri bundle. */
  url: string;
  /** Friendly size hint for the UI (fill in once we have real artefacts). */
  sizeNote: string;
  /** Where this file comes from / how to regenerate it. */
  provenance: string;
};

/** PaddleOCR 3.5 (PP-OCRv5_server) — same checkpoint the Python backend loads. */
export const PADDLE_OCR = {
  det: {
    url: '/models/paddleocr/det.onnx',
    sizeNote: '~50 MB',
    provenance: 'paddle2onnx PP-OCRv5_server_det → opset 11',
  } satisfies OnnxSpec,
  cls: {
    url: '/models/paddleocr/cls.onnx',
    sizeNote: '~2 MB',
    provenance: 'paddle2onnx ch_ppocr_mobile_v2.0_cls → opset 11',
  } satisfies OnnxSpec,
  rec: {
    url: '/models/paddleocr/rec.onnx',
    sizeNote: '~80 MB',
    provenance: 'paddle2onnx PP-OCRv5_server_rec → opset 11',
  } satisfies OnnxSpec,
  dict: {
    url: '/models/paddleocr/dict.txt',
    sizeNote: '~30 KB',
    provenance: 'ppocr/utils/dict/ppocr_keys_v1.txt (or the lang-specific dict)',
  } satisfies OnnxSpec,
};

/** GLiNER2-PII — same checkpoint as `fastino/gliner2-privacy-filter-PII-multi`. */
export const GLINER2 = {
  model: {
    url: '/models/gliner2/model.onnx',
    sizeNote: '~300 MB',
    provenance: 'GLiNER2 ONNX export (label-conditioned encoder, ~300M params)',
  } satisfies OnnxSpec,
  tokenizer: {
    url: '/models/gliner2/tokenizer.json',
    sizeNote: '~2 MB',
    provenance: 'AutoTokenizer.from_pretrained(...).save_pretrained()',
  } satisfies OnnxSpec,
  labels: {
    url: '/models/gliner2/labels.json',
    sizeNote: '~1 KB',
    provenance: 'app.py PII_LABELS — name + description per category',
  } satisfies OnnxSpec,
};

/** HEAD-probe used by worker.ts to decide which pipeline to run. */
export async function onnxModelsAvailable(): Promise<boolean> {
  try {
    const r = await fetch(PADDLE_OCR.det.url, { method: 'HEAD' });
    return r.ok;
  } catch {
    return false;
  }
}

// ─────────────────────────────────────────────────────────────────────────
// FALLBACK (transformers.js) — used while the ONNX artefacts above are absent.
// Remove these once `onnxModelsAvailable()` returns true on every install.
// ─────────────────────────────────────────────────────────────────────────
import type { DataType } from '@huggingface/transformers';

export type ModelSpec = { modelId: string; dtype: DataType; sizeNote: string };

export const OCR_MODEL: ModelSpec = {
  // TODO(model-parity): replace with PaddleOCR ONNX (see PADDLE_OCR above)
  modelId: 'Xenova/trocr-small-printed',
  dtype: 'q8',
  sizeNote: '~120 MB',
};

export const PII_MODEL: ModelSpec = {
  // TODO(model-parity): replace with GLiNER2 ONNX (see GLINER2 above)
  modelId: 'Xenova/bert-base-multilingual-cased-ner-hrl',
  dtype: 'q8',
  sizeNote: '~180 MB',
};

// Shipped offline; the Gradio engine fetches the equivalent from /api/meta.
export const LOCAL_CAT_META: Record<string, { color: string; label: string }> = {
  person: { color: '#f87171', label: 'Name' },
  email: { color: '#60a5fa', label: 'Email' },
  phone: { color: '#34d399', label: 'Phone' },
  address: { color: '#fbbf24', label: 'Address' },
  personnummer: { color: '#a78bfa', label: 'Personnummer' },
  organisationsnummer: { color: '#f472b6', label: 'Org. number' },
  bank: { color: '#22d3ee', label: 'Bank details' },
  date: { color: '#94a3b8', label: 'Date' },
  url: { color: '#818cf8', label: 'URL' },
};
