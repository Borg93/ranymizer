/**
 * The seam between the UI and inference. state.svelte.ts depends only on
 * this — never on @gradio/client or the worker directly. The implementation
 * is chosen at build time by VITE_ENGINE (see ./index.ts).
 */
import type { AnonymizeResult, CatMeta } from '../types';

export type EngineProgress =
  | { phase: 'loading'; message: string; file?: string; percent?: number }
  | { phase: 'analyzing' }
  | { phase: 'ready' };

export interface AnonymizerEngine {
  readonly name: string;
  /** True when nothing leaves the device. */
  readonly local: boolean;
  meta(): Promise<Record<string, CatMeta>>;
  analyze(file: File, onProgress?: (p: EngineProgress) => void): Promise<AnonymizeResult>;
  dispose(): void;
}
