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
 * User-configurable pipeline knobs that change *what the model produces*.
 * Infrastructure choices (engine, device, backend URL, API keys,
 * quantize/compile, etc.) live elsewhere — those control how inference runs,
 * not the content of the output. Persisted to localStorage and read by the
 * engine before each analyse().
 */
export type PipelineConfig = {
  /** PaddleOCR-VL layout + preprocessing knobs that change the parsed output. */
  paddleocr: {
    /** Layout detection score threshold (0..1). */
    layoutThreshold: number;
    useDocOrientationClassify: boolean;
    useDocUnwarping: boolean;
    useTextlineOrientation: boolean;
    useChartRecognition: boolean;
    useSealRecognition: boolean;
    useOcrForImageBlock: boolean;
  };

  /** VLM sampling parameters that change how the recogniser writes its output. */
  vlm: {
    temperature: number;
    topP: number;
    repetitionPenalty: number;
    maxNewTokens: number;
    minPixels: number;
    maxPixels: number;
  };

  /** GLiNER2 PII detection knobs. */
  gliner: {
    /** Hugging Face model id or local path. */
    modelName: string;
    /** Confidence floor (0..1). Hits below this are dropped. */
    threshold: number;
    /** Label keys to detect. Empty array = use the engine's default. */
    enabledLabels: string[];
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
  paddleocr: {
    layoutThreshold: 0.5,
    useDocOrientationClassify: false,
    useDocUnwarping: false,
    useTextlineOrientation: false,
    useChartRecognition: false,
    useSealRecognition: false,
    useOcrForImageBlock: false,
  },
  vlm: {
    temperature: 0,
    topP: 1,
    repetitionPenalty: 1,
    maxNewTokens: 2048,
    minPixels: 0,
    maxPixels: 0,
  },
  gliner: {
    modelName: 'fastino/gliner2-privacy-filter-PII-multi',
    threshold: 0.5,
    enabledLabels: [...DEFAULT_PII_LABELS],
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
