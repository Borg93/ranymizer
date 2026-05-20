/**
 * Talks to the Gradio Server.
 *
 *   - Dev: SvelteKit runs on :5173, Python on :7860. CORS is open on the
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

const HTTP_BASE = GRADIO_URL;

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

/** GET /api/examples — list of example filenames in the backend's example-images/ */
export async function fetchExamples(): Promise<string[]> {
  const r = await fetch(`${HTTP_BASE}/api/examples`);
  if (!r.ok) throw new Error(`examples list: ${r.status}`);
  const d = await r.json();
  return (d.examples as string[]) ?? [];
}

/** Build URL for an example image (optionally a thumbnail). */
export function exampleUrl(name: string, thumb = false): string {
  return `${HTTP_BASE}/examples/${encodeURIComponent(name)}${thumb ? '?thumb=1' : ''}`;
}

/** Fetch an example as a File so we can route it through the same upload path. */
export async function fetchExampleAsFile(name: string): Promise<File> {
  const r = await fetch(exampleUrl(name));
  if (!r.ok) throw new Error(`fetch failed: ${r.status}`);
  const blob = await r.blob();
  return new File([blob], name, { type: blob.type || 'image/png' });
}

/**
 * GET /api/meta — static category color/label table.
 * Cached in-memory because it never changes during a session.
 */
let _metaPromise: Promise<Record<string, CatMeta>> | null = null;

export function fetchMeta(): Promise<Record<string, CatMeta>> {
  if (_metaPromise) return _metaPromise;
  _metaPromise = (async () => {
    const r = await fetch(`${HTTP_BASE}/api/meta`);
    if (!r.ok) throw new Error(`meta: ${r.status}`);
    const d = await r.json();
    return (d.categories_meta as Record<string, CatMeta>) ?? {};
  })();
  return _metaPromise;
}
