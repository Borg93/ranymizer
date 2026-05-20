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
 * ignore it gracefully — mock honours what it can simulate, backend honours
 * what server.py supports. Field names mirror PaddleOCR-VL / GLiNER2 docs
 * so the wire mapping stays one-to-one.
 */
export type PipelineVersion = 'v1' | 'v1.5';
export type InferenceEngine = 'paddle' | 'paddle_static' | 'paddle_dynamic' | 'transformers';
export type VlmBackend =
  | ''
  | 'vllm-server'
  | 'sglang-server'
  | 'fastdeploy-server'
  | 'mlx-vlm-server'
  | 'llama-cpp-server';

export type PipelineConfig = {
  /** PaddleOCR-VL pipeline version. */
  pipelineVersion: PipelineVersion;
  /** Inference engine PaddleOCR resolves to (paddle / transformers). */
  engine: InferenceEngine;
  /** Device string, e.g. 'cpu', 'gpu:0', 'mps'. Free-form. */
  device: string;

  /** PaddleOCR-VL layout + preprocessing knobs. */
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

  /** VLM-recognition backend + sampling. */
  vlm: {
    backend: VlmBackend;
    serverUrl: string;
    apiModelName: string;
    /** Stored in plain localStorage — fine for local dev, rotate before sharing. */
    apiKey: string;
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
    mapLocation: 'cpu' | 'cuda';
    quantize: boolean;
    compile: boolean;
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
  pipelineVersion: 'v1.5',
  engine: 'paddle',
  device: 'gpu:0',
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
    backend: '',
    serverUrl: '',
    apiModelName: 'PaddlePaddle/PaddleOCR-VL-1.5',
    apiKey: '',
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
    mapLocation: 'cuda',
    quantize: true,
    compile: true,
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
