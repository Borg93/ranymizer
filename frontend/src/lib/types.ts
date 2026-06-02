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
    /** Global confidence floor (0..1). Per-label overrides win when > 0. */
    threshold: number;
    /** Label keys to detect. Empty array = use the engine's default. */
    enabledLabels: string[];
    /**
     * Per-label natural-language descriptions sent to the model alongside
     * the label key. GLiNER2 uses these as soft prompts — better descriptions
     * usually mean better recall + precision, especially for Swedish-specific
     * identifiers (personnummer, organisationsnummer, bankgiro) that don't
     * appear verbatim in the model's training data.
     */
    descriptions: Record<string, string>;
    /** Per-label post-filters. See {@link LabelRule}. */
    rules: Record<string, LabelRule>;
    /**
     * User-defined labels on top of the default PII set. GLiNER2 is
     * label-conditioned — any key + description we pass at inference time
     * becomes a candidate category. The frontend uses `displayLabel` for
     * UI text and `color` for the box stripe; the description is sent to
     * the model (same shape as `descriptions[label]`).
     */
    customLabels: Record<string, { displayLabel: string; color: string; description: string }>;
  };
};

/** How a per-label regex applies to the candidate text. */
export type RegexMode = 'full' | 'partial' | 'exclude';

/**
 * Per-label post-filter applied *after* GLiNER2 emits candidate spans.
 * Empty fields = no filter. These are precision knobs only — they reject
 * false positives but never invent matches the model didn't propose.
 */
export type LabelRule = {
  /** Regex pattern applied to the matched text. Empty = no regex filter. */
  regex: string;
  /**
   * full     - the entire span text must match the regex.
   * partial  - the regex must match somewhere inside the span.
   * exclude  - drop the span if the regex matches.
   */
  regexMode: RegexMode;
  /** Per-label confidence override (0..1). 0 = inherit the global threshold. */
  threshold: number;
  /** Run a Luhn checksum on digit-only spans (personnummer / card_number). */
  validateLuhn: boolean;
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
  // GDPR Art. 9 / dataskyddslag 3 kap. — sensitive personal data. Mandatory
  // coverage for municipal documents (social services, school, healthcare).
  // See Slutrapport IMY-2024-5156 §4.3 + §6.3.
  'health',
  'religion_ethnicity',
] as const;

/** Empty rule (default for labels without a useful regex). */
export const EMPTY_LABEL_RULE: LabelRule = {
  regex: '',
  regexMode: 'full',
  threshold: 0,
  validateLuhn: false,
};

/**
 * Default per-label rules tuned for Swedish PII. Each pattern is a
 * conservative *post-filter*: GLiNER2 proposes the span, the regex rejects
 * obvious false positives. Names / addresses / dates have no regex because
 * regex can't validate "is this a name."
 */
export const DEFAULT_LABEL_RULES: Record<string, LabelRule> = {
  person: { ...EMPTY_LABEL_RULE },
  email: {
    regex: '^[\\w.+-]+@[\\w.-]+\\.\\w+$',
    regexMode: 'full',
    threshold: 0,
    validateLuhn: false,
  },
  phone_number: {
    regex: '^\\+?\\d[\\d\\s-]{6,}$',
    regexMode: 'full',
    threshold: 0,
    validateLuhn: false,
  },
  address: { ...EMPTY_LABEL_RULE },
  date_of_birth: { ...EMPTY_LABEL_RULE },
  personnummer: {
    regex: '^\\d{6,8}[-+]\\d{4}$',
    regexMode: 'full',
    threshold: 0,
    validateLuhn: false,
  },
  organisationsnummer: {
    regex: '^\\d{6}-\\d{4}$',
    regexMode: 'full',
    threshold: 0,
    validateLuhn: false,
  },
  bank_account: {
    regex: '^\\d{3,4}-\\d{3,4}$',
    regexMode: 'full',
    threshold: 0,
    validateLuhn: false,
  },
  iban: {
    regex: '^[A-Z]{2}\\d{2}[A-Z0-9]+$',
    regexMode: 'full',
    threshold: 0,
    validateLuhn: false,
  },
  card_number: {
    regex: '^(\\d[ -]?){13,19}$',
    regexMode: 'full',
    threshold: 0,
    validateLuhn: false,
  },
  // GLiNER2 often extracts URL candidates without the scheme (`www.x.se`,
  // `example.com/page`). A `^https?://` regex would reject those. Trust the
  // model by default; tighten via the inspector if needed.
  url: { ...EMPTY_LABEL_RULE },
  ip_address: {
    regex: '^(\\d{1,3}\\.){3}\\d{1,3}$',
    regexMode: 'full',
    threshold: 0,
    validateLuhn: false,
  },
  username: { ...EMPTY_LABEL_RULE },
  // Sensitive categories — no regex possible (free-form text). The
  // handläggare can still raise the per-label threshold to require higher
  // model confidence before flagging.
  health: { ...EMPTY_LABEL_RULE },
  religion_ethnicity: { ...EMPTY_LABEL_RULE },
};

/**
 * Default GLiNER2 label descriptions. Match `PII_LABELS` in `backend/app.py`
 * so the frontend and the Python service start from the same baseline.
 * Users can override any of these in the Settings drawer.
 */
export const DEFAULT_LABEL_DESCRIPTIONS: Record<string, string> = {
  person: 'Full name of a person',
  email: 'Email address',
  phone_number: 'Phone number, including country code variants',
  address: 'Street address, postal address, or physical location',
  date_of_birth: 'Date of birth',
  personnummer:
    'Swedish personal identity number, format YYMMDD-XXXX or YYYYMMDD-XXXX, 10 or 12 digits with hyphen or plus separator',
  organisationsnummer: 'Swedish organisation number, format NNNNNN-NNNN, 10 digits with hyphen',
  bank_account: 'Bank account number including Swedish bankgiro or plusgiro',
  iban: 'International Bank Account Number, starts with two-letter country code',
  card_number: 'Credit or debit card number',
  url: 'URL or web link',
  ip_address: 'IP address',
  username: 'User name or login handle',
  health:
    'Health information: diagnoses, medication, treatment, disability, sick leave, mental health',
  religion_ethnicity:
    'Religious belief, philosophical conviction, ethnic origin, or trade-union membership',
};

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
    descriptions: { ...DEFAULT_LABEL_DESCRIPTIONS },
    rules: structuredClone(DEFAULT_LABEL_RULES),
    customLabels: {},
  },
};

/** One of the 8 anchor handles on a selected box: 4 corners + 4 edge mids. */
export type ResizeHandle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w';

export type DragState =
  | { type: 'draw'; startX: number; startY: number; newBox: Box }
  | {
      type: 'move';
      startX: number;
      startY: number;
      origBox: { x: number; y: number; w: number; h: number };
      boxId: number;
    }
  | {
      type: 'resize';
      handle: ResizeHandle;
      startX: number;
      startY: number;
      origBox: { x: number; y: number; w: number; h: number };
      boxId: number;
    };
