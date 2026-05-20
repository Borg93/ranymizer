/// <reference lib="webworker" />
/**
 * Local inference worker — OCR + PII on-device. Lazy pipeline singleton;
 * browser-cache on so weights are fetched once then served offline.
 * See models.ts for the model-parity caveat.
 */
import { pipeline, env, RawImage } from '@huggingface/transformers';
import { resolveBackend, type BackendPreference } from './webgpu';
import { OCR_MODEL, PII_MODEL } from './models';
import type { Box, PiiSpan } from '../types';

env.useBrowserCache = true;

const BACKEND_PREF = (import.meta.env.VITE_BACKEND as BackendPreference) ?? 'auto';

type OcrPipe = Awaited<ReturnType<typeof pipeline<'image-to-text'>>>;
type PiiPipe = Awaited<ReturnType<typeof pipeline<'token-classification'>>>;

// Module-level lazy singleton (replaces a static-only class).
const Pipeline = {
  device: 'wasm' as 'webgpu' | 'wasm',
  ocr: null as Promise<OcrPipe> | null,
  pii: null as Promise<PiiPipe> | null,
  get(progress_callback?: (x: unknown) => void) {
    Pipeline.ocr ??= pipeline('image-to-text', OCR_MODEL.modelId, {
      dtype: OCR_MODEL.dtype,
      device: Pipeline.device,
      progress_callback,
    });
    Pipeline.pii ??= pipeline('token-classification', PII_MODEL.modelId, {
      dtype: PII_MODEL.dtype,
      device: Pipeline.device,
      progress_callback,
    });
    return Promise.all([Pipeline.ocr, Pipeline.pii]);
  },
};

let backendReady = false;

async function ensureBackend() {
  if (backendReady) return;
  self.postMessage({ status: 'loading', message: 'Selecting compute backend…' });
  Pipeline.device = await resolveBackend(BACKEND_PREF);
  self.postMessage({ status: 'loading', message: `Loading models (${Pipeline.device})…` });
  await Pipeline.get((x: unknown) => {
    const p = x as { status?: string; file?: string; progress?: number };
    if (p.status === 'progress') {
      self.postMessage({ status: 'progress', file: p.file, percent: p.progress });
    }
  });
  backendReady = true;
}

// TODO(model-parity): needs an OCR model that emits per-line boxes; with a
// geometry-less model this is empty (mirrors app.py's span→line overlap).
function spansToBoxes(_spans: PiiSpan[], _lines: { text: string; box: Box }[]): Box[] {
  return [];
}

async function analyze(id: number, image: ImageBitmap) {
  try {
    await ensureBackend();
    self.postMessage({ status: 'loading', message: 'Reading text…' });

    const [ocr, pii] = await Pipeline.get();
    const img = new RawImage(
      new Uint8ClampedArray(await bitmapToRGBA(image)),
      image.width,
      image.height,
      4,
    );

    const ocrOut = (await ocr(img)) as { generated_text: string }[] | { generated_text: string };
    const text = Array.isArray(ocrOut)
      ? ocrOut.map((o) => o.generated_text).join('\n')
      : ocrOut.generated_text;
    const lines: { text: string; box: Box }[] = [];

    self.postMessage({ status: 'loading', message: 'Finding personal data…' });
    const ents = (await pii(text)) as Array<{
      entity?: string;
      entity_group?: string;
      start: number;
      end: number;
      word: string;
      score: number;
    }>;
    const spans: PiiSpan[] = ents.map((e) => ({
      label: (e.entity_group ?? e.entity ?? 'misc').toLowerCase(),
      text: e.word,
      start: e.start,
      end: e.end,
      confidence: e.score,
    }));

    self.postMessage({
      status: 'result',
      id,
      result: {
        filename: '',
        width: image.width,
        height: image.height,
        boxes: spansToBoxes(spans, lines),
        text,
        spans,
      },
    });
  } catch (err) {
    self.postMessage({
      status: 'error',
      id,
      message: `local analysis failed: ${err instanceof Error ? err.message : String(err)}`,
    });
  }
}

// ImageBitmap → RGBA via OffscreenCanvas (worker-safe).
async function bitmapToRGBA(bmp: ImageBitmap): Promise<ArrayBufferLike> {
  const c = new OffscreenCanvas(bmp.width, bmp.height);
  const ctx = c.getContext('2d');
  if (!ctx) throw new Error('OffscreenCanvas: 2d context unavailable');
  ctx.drawImage(bmp, 0, 0);
  return ctx.getImageData(0, 0, bmp.width, bmp.height).data.buffer;
}

self.addEventListener('message', (e: MessageEvent) => {
  const { type, data } = e.data;
  if (type === 'analyze') analyze(data.id, data.image);
});
