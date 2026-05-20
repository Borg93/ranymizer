// Showcase engine: pass-through to the @gradio/client wrapper (server
// inference on the Python gr.Server / ZeroGPU).
//
// PipelineConfig is accepted on analyze() but not yet forwarded — backend
// needs to grow matching parameters first (TODO: extend server.py's
// `anonymize_screenshot` to accept threshold + label list + ocr toggles).
import { anonymizeScreenshot, fetchMeta } from '../api';
import type { AnonymizeResult, CatMeta } from '../types';
import type { AnalyzeOptions, AnonymizerEngine } from './types';

export function createGradioEngine(): AnonymizerEngine {
  return {
    name: 'server · zerogpu',
    local: false,
    meta: (): Promise<Record<string, CatMeta>> => fetchMeta(),
    async analyze(file: File, opts?: AnalyzeOptions): Promise<AnonymizeResult> {
      opts?.onProgress?.({ phase: 'analyzing' });
      const result = await anonymizeScreenshot(file);
      opts?.onProgress?.({ phase: 'ready' });
      return result;
    },
    dispose() {},
  };
}
