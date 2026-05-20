/**
 * Mock engine — no backend, no GPU, no network. Returns a deterministic
 * dummy AnonymizeResult derived from the image's dimensions so the editor,
 * sidebar, draw/select modes and persistence flows can be exercised end-to-
 * end on any machine.
 *
 * Enable with `VITE_ENGINE=mock` (see scripts in package.json).
 */
import type { AnonymizeResult, Box, CatMeta, OcrLine, PiiSpan } from '../types';
import type { AnonymizerEngine, EngineProgress } from './types';

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
  yFraction: number; // 0..1 (top-down position of this fake redaction)
  xFraction: number;
  widthFraction: number;
  heightFraction: number;
};

const MOCK_HITS: MockHit[] = [
  {
    label: 'person',
    text: 'Sven Andersson',
    yFraction: 0.1,
    xFraction: 0.08,
    widthFraction: 0.25,
    heightFraction: 0.035,
  },
  {
    label: 'email',
    text: 'sven.andersson@exempel.se',
    yFraction: 0.16,
    xFraction: 0.08,
    widthFraction: 0.32,
    heightFraction: 0.035,
  },
  {
    label: 'phone_number',
    text: '070-123 45 67',
    yFraction: 0.22,
    xFraction: 0.08,
    widthFraction: 0.2,
    heightFraction: 0.035,
  },
  {
    label: 'address',
    text: 'Sveavägen 12, 113 57 Stockholm',
    yFraction: 0.28,
    xFraction: 0.08,
    widthFraction: 0.38,
    heightFraction: 0.035,
  },
  {
    label: 'personnummer',
    text: '19850315-2389',
    yFraction: 0.34,
    xFraction: 0.21,
    widthFraction: 0.18,
    heightFraction: 0.035,
  },
  {
    label: 'organisationsnummer',
    text: '556677-1234',
    yFraction: 0.4,
    xFraction: 0.15,
    widthFraction: 0.15,
    heightFraction: 0.035,
  },
  {
    label: 'bank_account',
    text: '5050-1055',
    yFraction: 0.46,
    xFraction: 0.15,
    widthFraction: 0.12,
    heightFraction: 0.035,
  },
  {
    label: 'url',
    text: 'https://ranymizer.dev',
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

function buildMockBoxes(width: number, height: number): Box[] {
  return MOCK_HITS.map((hit) => ({
    label: hit.label,
    text: hit.text,
    x: Math.round(width * hit.xFraction),
    y: Math.round(height * hit.yFraction),
    w: Math.max(1, Math.round(width * hit.widthFraction)),
    h: Math.max(1, Math.round(height * hit.heightFraction)),
  }));
}

function buildMockSpans(): PiiSpan[] {
  const spans: PiiSpan[] = [];
  let cursor = 0;
  for (const hit of MOCK_HITS) {
    const start = FAKE_TEXT.indexOf(hit.text, cursor);
    if (start < 0) continue;
    const end = start + hit.text.length;
    spans.push({
      label: hit.label,
      text: hit.text,
      start,
      end,
      confidence: 0.99,
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
    async analyze(file: File, onProgress?: (p: EngineProgress) => void): Promise<AnonymizeResult> {
      onProgress?.({ phase: 'analyzing' });
      const [{ width, height }] = await Promise.all([
        readImageDimensions(file),
        delay(MOCK_LATENCY_MS),
      ]);
      onProgress?.({ phase: 'ready' });
      return {
        filename: file.name,
        width,
        height,
        boxes: buildMockBoxes(width, height),
        text: FAKE_TEXT,
        spans: buildMockSpans(),
        ocr_lines: buildMockOcrLines(width, height),
      };
    },
    dispose() {},
  };
}
