// Showcase engine: pass-through to the @gradio/client wrapper (server
// inference on the Python gr.Server / ZeroGPU).
import { anonymizeScreenshot, fetchMeta } from '../api';
import type { AnonymizerEngine, EngineProgress } from './types';
import type { AnonymizeResult, CatMeta } from '../types';

export function createGradioEngine(): AnonymizerEngine {
  return {
    name: 'server · zerogpu',
    local: false,
    meta: (): Promise<Record<string, CatMeta>> => fetchMeta(),
    async analyze(file: File, onProgress?: (p: EngineProgress) => void): Promise<AnonymizeResult> {
      onProgress?.({ phase: 'analyzing' });
      const result = await anonymizeScreenshot(file);
      onProgress?.({ phase: 'ready' });
      return result;
    },
    dispose() {},
  };
}
