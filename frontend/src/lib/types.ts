/**
 * Wire-format types matching what the Python backend returns from
 * /anonymize_screenshot. Keep these in sync with app.py / server.py.
 */

export type Box = {
  label: string;
  text: string;
  x: number;
  y: number;
  w: number;
  h: number;
};

export type PiiSpan = {
  label: string;
  text: string;
  start: number;
  end: number;
  confidence: number;
};

export type CatMeta = {
  color: string;
  label: string;
};

export type OcrLine = {
  text: string;
  x: number;
  y: number;
  w: number;
  h: number;
};

export type AnonymizeResult = {
  filename: string;
  width: number;
  height: number;
  boxes: Box[];
  text: string;
  spans: PiiSpan[];
  ocr_lines?: OcrLine[];
  error?: string;
};

/** Editor box with frontend-only fields. */
export type EditorBox = Box & {
  id: number;
  enabled: boolean;
  custom: boolean;
};

export type Mode = 'select' | 'draw';

/**
 * User-configurable pipeline knobs. Persisted to localStorage, read by the
 * engine before each analyse(). Engines that don't honour a field should
 * ignore it gracefully — mock honours all of them, backend honours what
 * server.py supports.
 */
export type PipelineConfig = {
  gliner: {
    /** Confidence floor (0..1). Hits below this are dropped. */
    threshold: number;
    /** Label keys to detect. Empty array = use the engine's default. */
    enabledLabels: string[];
  };
  ocr: {
    useDocOrientationClassify: boolean;
    useDocUnwarping: boolean;
    useTextlineOrientation: boolean;
  };
};

export const DEFAULT_PII_LABELS = [
  'person',
  'email',
  'phone_number',
  'address',
  'date_of_birth',
  'personnummer',
  'organisationsnummer',
  'bank_account',
  'iban',
  'card_number',
  'url',
  'ip_address',
  'username',
] as const;

export const DEFAULT_PIPELINE_CONFIG: PipelineConfig = {
  gliner: { threshold: 0.5, enabledLabels: [...DEFAULT_PII_LABELS] },
  ocr: {
    useDocOrientationClassify: false,
    useDocUnwarping: false,
    useTextlineOrientation: false,
  },
};

export type DragState =
  | { type: 'draw'; startX: number; startY: number; newBox: Box }
  | {
      type: 'move';
      startX: number;
      startY: number;
      origBox: { x: number; y: number; w: number; h: number };
      boxId: number;
    };
