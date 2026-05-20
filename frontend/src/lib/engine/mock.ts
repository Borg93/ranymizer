/**
 * Mock engine — no backend, no GPU, no network. Returns a deterministic
 * dummy AnonymizeResult derived from the image's dimensions so the editor,
 * sidebar, draw/select modes and persistence flows can be exercised end-to-
 * end on any machine.
 *
 * Honours PipelineConfig:
 *   - gliner.threshold       filters MOCK_HITS by per-hit fake confidence
 *   - gliner.enabledLabels   filters MOCK_HITS by category
 *   - ocr.*                  stored on config but doesn't change mock output
 *
 * Enable with `VITE_ENGINE=mock` (see scripts in package.json).
 */

import type { AnonymizeResult, Box, CatMeta, OcrLine, PiiSpan, PipelineConfig } from '../types';
import { DEFAULT_PIPELINE_CONFIG } from '../types';
import type { AnalyzeOptions, AnonymizerEngine } from './types';

const MOCK_LATENCY_MS = 600;
const FAKE_TEXT = [
  'Sven Andersson',
  'sven.andersson@exempel.se',
  '070-123 45 67',
  'Sveavägen 12, 113 57 Stockholm',
  'Personnummer: 19850315-2389',
  'Org. nr 556677-1234',
  'Bankgiro 5050-1055',
  'https://ranymizer.dev',
].join('\n');

const MOCK_CATEGORIES_META: Record<string, CatMeta> = {
  person: { color: '#ef4444', label: 'Person' },
  email: { color: '#f97316', label: 'Email' },
  phone_number: { color: '#f59e0b', label: 'Phone' },
  address: { color: '#84cc16', label: 'Address' },
  personnummer: { color: '#06b6d4', label: 'Personnummer' },
  organisationsnummer: { color: '#0ea5e9', label: 'Organisationsnr' },
  bank_account: { color: '#6366f1', label: 'Bank account' },
  url: { color: '#ec4899', label: 'URL' },
};

type MockHit = {
  label: keyof typeof MOCK_CATEGORIES_META;
  text: string;
  confidence: number;
  yFraction: number;
  xFraction: number;
  widthFraction: number;
  heightFraction: number;
};

const MOCK_HITS: MockHit[] = [
  {
    label: 'person',
    text: 'Sven Andersson',
    confidence: 0.97,
    yFraction: 0.1,
    xFraction: 0.08,
    widthFraction: 0.25,
    heightFraction: 0.035,
  },
  {
    label: 'email',
    text: 'sven.andersson@exempel.se',
    confidence: 0.95,
    yFraction: 0.16,
    xFraction: 0.08,
    widthFraction: 0.32,
    heightFraction: 0.035,
  },
  {
    label: 'phone_number',
    text: '070-123 45 67',
    confidence: 0.88,
    yFraction: 0.22,
    xFraction: 0.08,
    widthFraction: 0.2,
    heightFraction: 0.035,
  },
  {
    label: 'address',
    text: 'Sveavägen 12, 113 57 Stockholm',
    confidence: 0.78,
    yFraction: 0.28,
    xFraction: 0.08,
    widthFraction: 0.38,
    heightFraction: 0.035,
  },
  {
    label: 'personnummer',
    text: '19850315-2389',
    confidence: 0.68,
    yFraction: 0.34,
    xFraction: 0.21,
    widthFraction: 0.18,
    heightFraction: 0.035,
  },
  {
    label: 'organisationsnummer',
    text: '556677-1234',
    confidence: 0.58,
    yFraction: 0.4,
    xFraction: 0.15,
    widthFraction: 0.15,
    heightFraction: 0.035,
  },
  {
    label: 'bank_account',
    text: '5050-1055',
    confidence: 0.48,
    yFraction: 0.46,
    xFraction: 0.15,
    widthFraction: 0.12,
    heightFraction: 0.035,
  },
  {
    label: 'url',
    text: 'https://ranymizer.dev',
    confidence: 0.38,
    yFraction: 0.52,
    xFraction: 0.08,
    widthFraction: 0.22,
    heightFraction: 0.035,
  },
];

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function readImageDimensions(file: File): Promise<{ width: number; height: number }> {
  const bitmap = await createImageBitmap(file);
  try {
    return { width: bitmap.width, height: bitmap.height };
  } finally {
    bitmap.close();
  }
}

function filterHits(config: PipelineConfig): MockHit[] {
  const threshold = config.gliner.threshold;
  const allowed =
    config.gliner.enabledLabels.length === 0 ? null : new Set(config.gliner.enabledLabels);
  return MOCK_HITS.filter(
    (hit) => hit.confidence >= threshold && (allowed === null || allowed.has(hit.label)),
  );
}

function buildMockBoxes(hits: MockHit[], width: number, height: number): Box[] {
  return hits.map((hit) => ({
    label: hit.label,
    text: hit.text,
    x: Math.round(width * hit.xFraction),
    y: Math.round(height * hit.yFraction),
    w: Math.max(1, Math.round(width * hit.widthFraction)),
    h: Math.max(1, Math.round(height * hit.heightFraction)),
  }));
}

function buildMockSpans(hits: MockHit[]): PiiSpan[] {
  const spans: PiiSpan[] = [];
  let cursor = 0;
  for (const hit of hits) {
    const start = FAKE_TEXT.indexOf(hit.text, cursor);
    if (start < 0) continue;
    const end = start + hit.text.length;
    spans.push({
      label: hit.label,
      text: hit.text,
      start,
      end,
      confidence: hit.confidence,
    });
    cursor = end;
  }
  return spans;
}

function buildMockOcrLines(width: number, height: number): OcrLine[] {
  const lines = FAKE_TEXT.split('\n');
  const lineHeight = Math.round(height * 0.035);
  return lines.map((line, idx) => ({
    text: line,
    x: Math.round(width * 0.06),
    y: Math.round(height * (0.1 + 0.06 * idx)),
    w: Math.round(width * 0.5),
    h: lineHeight,
  }));
}

export function createMockEngine(): AnonymizerEngine {
  return {
    name: 'mock · no backend',
    local: true,
    async meta(): Promise<Record<string, CatMeta>> {
      return MOCK_CATEGORIES_META;
    },
    async analyze(file: File, opts?: AnalyzeOptions): Promise<AnonymizeResult> {
      opts?.onProgress?.({ phase: 'analyzing' });
      const config = opts?.config ?? DEFAULT_PIPELINE_CONFIG;
      const [{ width, height }] = await Promise.all([
        readImageDimensions(file),
        delay(MOCK_LATENCY_MS),
      ]);
      const hits = filterHits(config);
      opts?.onProgress?.({ phase: 'ready' });
      return {
        filename: file.name,
        width,
        height,
        boxes: buildMockBoxes(hits, width, height),
        text: FAKE_TEXT,
        spans: buildMockSpans(hits),
        ocr_lines: buildMockOcrLines(width, height),
      };
    },
    dispose() {},
  };
}
