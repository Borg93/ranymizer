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

export type View = 'landing' | 'editor';
export type Mode = 'select' | 'draw';

export type DragState =
  | { type: 'draw'; startX: number; startY: number; newBox: Box }
  | {
      type: 'move';
      startX: number;
      startY: number;
      origBox: { x: number; y: number; w: number; h: number };
      boxId: number;
    };
