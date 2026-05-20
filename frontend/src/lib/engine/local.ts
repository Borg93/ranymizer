// Local engine: drives the inference worker. The image is transferred as an
// ImageBitmap — never serialised to network or disk.
//
// PipelineConfig is accepted but not yet plumbed through to the worker.
// TODO: forward config (threshold + enabled labels) to worker.ts so the
// on-device GLiNER call respects user settings.

import type { AnonymizeResult, CatMeta } from '../types';
import { LOCAL_CAT_META } from './models';
import type { AnalyzeOptions, AnonymizerEngine, EngineProgress } from './types';

export function createLocalEngine(): AnonymizerEngine {
  let worker: Worker | null = null;
  let seq = 0;
  const pending = new Map<
    number,
    {
      resolve: (r: AnonymizeResult) => void;
      reject: (e: Error) => void;
      onProgress?: (p: EngineProgress) => void;
    }
  >();

  function getWorker(): Worker {
    if (worker) return worker;
    worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
    worker.addEventListener('message', (e: MessageEvent) => {
      const d = e.data;
      switch (d.status) {
        case 'loading':
          for (const p of pending.values())
            p.onProgress?.({ phase: 'loading', message: d.message });
          break;
        case 'progress':
          for (const p of pending.values())
            p.onProgress?.({
              phase: 'loading',
              message: `Downloading ${d.file ?? 'model'}…`,
              file: d.file,
              percent: d.percent,
            });
          break;
        case 'result': {
          const p = pending.get(d.id);
          if (p) {
            pending.delete(d.id);
            p.onProgress?.({ phase: 'ready' });
            p.resolve(d.result as AnonymizeResult);
          }
          break;
        }
        case 'error': {
          const p = d.id != null ? pending.get(d.id) : undefined;
          if (p) {
            pending.delete(d.id);
            p.reject(new Error(d.message));
          }
          break;
        }
      }
    });
    return worker;
  }

  return {
    name: 'local · webgpu',
    local: true,
    async meta(): Promise<Record<string, CatMeta>> {
      return LOCAL_CAT_META;
    },
    async analyze(file: File, opts?: AnalyzeOptions): Promise<AnonymizeResult> {
      const w = getWorker();
      const id = ++seq;
      const image = await createImageBitmap(file);
      opts?.onProgress?.({ phase: 'analyzing' });
      return new Promise<AnonymizeResult>((resolve, reject) => {
        pending.set(id, { resolve, reject, onProgress: opts?.onProgress });
        w.postMessage({ type: 'analyze', data: { id, image } }, [image]);
      }).then((r) => ({ ...r, filename: r.filename || file.name }));
    },
    dispose() {
      worker?.terminate();
      worker = null;
      pending.clear();
    },
  };
}
