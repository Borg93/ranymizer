/**
 * Talks to the Gradio Server.
 *
 *   - Dev: SvelteKit runs on :5174, Python on :7860. CORS is open on the
 *     Python side so we connect directly.
 *   - Prod: Python serves the SvelteKit build from /; same origin.
 */
import { Client, handle_file } from '@gradio/client';
import type { AnonymizeResult, CatMeta } from './types';

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

/** Upload + run OCR+PII pipeline. Returns the result or an object with `error`. */
export async function anonymizeScreenshot(file: File): Promise<AnonymizeResult> {
  const client = await getClient();
  const result = await client.predict('/anonymize_screenshot', {
    image: handle_file(file),
  });
  const data = (result.data as unknown[])[0] as AnonymizeResult | undefined;
  return data ?? ({ error: 'no data returned' } as AnonymizeResult);
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
