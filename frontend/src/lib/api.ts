/**
 * Talks to the Gradio Server.
 *
 *   - Dev: SvelteKit runs on :5174, Python on :7860. CORS is open on the
 *     Python side so we connect directly.
 *   - Prod: Python serves the SvelteKit build from /; same origin.
 */
import { Client, handle_file } from '@gradio/client';
import type { AnonymizeResult, CatMeta, PipelineConfig } from './types';

const GRADIO_URL = import.meta.env.DEV
  ? 'http://localhost:7860'
  : typeof window !== 'undefined'
    ? window.location.origin
    : '';

let clientPromise: ReturnType<typeof Client.connect> | null = null;
function getClient() {
  if (!clientPromise) clientPromise = Client.connect(GRADIO_URL);
  return clientPromise;
}

/**
 * One streaming frame from the backend generator. Matches the `yield {...}`
 * payloads in `backend/server.py::anonymize_screenshot_api`. Every frame
 * carries the `stage`; the rest of the payload is partial up until `done`.
 */
export type AnonymizeStageEvent =
  | { stage: 'ocr_started'; filename: string }
  | {
      stage: 'ocr_done';
      filename: string;
      width: number;
      height: number;
      text: string;
      ocr_lines: AnonymizeResult['ocr_lines'];
    }
  | { stage: 'gliner_started' }
  | ({ stage: 'done' } & AnonymizeResult);

/** Upload + run OCR+PII pipeline as an SSE stream. The supplied `onStage`
 *  callback fires for every yielded frame so the UI can paint OCR text
 *  before GLiNER2 finishes and flip pipeline-graph indicators per stage.
 *  Resolves with the final `done` payload (same shape as the legacy single
 *  response). `config` is the request's PipelineConfig; `undefined` falls
 *  back to server defaults. */
export async function anonymizeScreenshot(
  file: File,
  config?: PipelineConfig,
  onStage?: (event: AnonymizeStageEvent) => void,
): Promise<AnonymizeResult> {
  const client = await getClient();
  const job = client.submit('/anonymize_screenshot', {
    image: handle_file(file),
    config: config ?? null,
  });

  let last: AnonymizeResult | undefined;
  try {
    for await (const msg of job) {
      // The Gradio JS client surfaces yielded frames as `{type:'data', data:[...]}`.
      // We only care about `data` frames; ignore status/log frames.
      if (msg.type !== 'data') continue;
      const frame = (msg.data as unknown[])[0] as AnonymizeStageEvent | undefined;
      if (!frame) continue;
      onStage?.(frame);
      if (frame.stage === 'done') {
        // `done` carries the full AnonymizeResult — destructure off the
        // discriminator and break out. The Gradio iterator can sit open
        // after the last yield waiting for the queue's `process_completes`
        // status; breaking + `job.cancel()` releases the SSE stream so the
        // loading spinner actually clears.
        const { stage: _stage, ...rest } = frame;
        last = rest as AnonymizeResult;
        break;
      }
    }
  } finally {
    job.cancel?.().catch(() => {
      /* job already closed or never started — ignore */
    });
  }
  return last ?? ({ error: 'no data returned' } as AnonymizeResult);
}

/**
 * GET /api/meta — static category color/label table.
 * Cached in-memory because it never changes during a session.
 */
let metaPromise: Promise<Record<string, CatMeta>> | null = null;

export function fetchMeta(): Promise<Record<string, CatMeta>> {
  if (metaPromise) return metaPromise;
  metaPromise = (async () => {
    const response = await fetch(`${GRADIO_URL}/api/meta`);
    if (!response.ok) throw new Error(`meta: ${response.status}`);
    const data = await response.json();
    return (data.categories_meta as Record<string, CatMeta>) ?? {};
  })();
  return metaPromise;
}
