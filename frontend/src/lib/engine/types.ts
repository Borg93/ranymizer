/**
 * The seam between the UI and inference. state.svelte.ts depends only on
 * this — never on @gradio/client or the worker directly. The implementation
 * is chosen at build time by VITE_ENGINE (see ./index.ts).
 */
import type { AnonymizeResult, CatMeta, PipelineConfig } from '../types';

export type EngineProgress =
  | { phase: 'loading'; message: string; file?: string; percent?: number }
  | { phase: 'analyzing' }
  | { phase: 'ready' };

export type AnalyzeOptions = {
  config?: PipelineConfig;
  onProgress?: (p: EngineProgress) => void;
};

export interface AnonymizerEngine {
  readonly name: string;
  /** True when nothing leaves the device. */
  readonly local: boolean;
  meta(): Promise<Record<string, CatMeta>>;
  analyze(file: File, opts?: AnalyzeOptions): Promise<AnonymizeResult>;
  dispose(): void;
}
