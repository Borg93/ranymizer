// Showcase engine: pass-through to the @gradio/client wrapper (server
// inference on the Python gr.Server / ZeroGPU). The PipelineConfig from
// the editor state rides along with each request so per-call settings —
// preprocessing toggles, threshold, labels, rules, custom labels — take
// effect server-side. See backend/schema.py for the matching wire schema.
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
      const result = await anonymizeScreenshot(file, opts?.config);
      opts?.onProgress?.({ phase: 'ready' });
      return result;
    },
    dispose() {},
  };
}
