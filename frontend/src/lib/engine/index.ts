/**
 * Build-time engine selection.
 *   VITE_ENGINE=local → desktop / on-device (transformers.js worker)
 *   VITE_ENGINE=mock  → no backend, deterministic fake results
 *   anything else     → showcase (Gradio Server)
 * Unused branches tree-shake away.
 */
import { createGradioEngine } from './gradio';
import { createLocalEngine } from './local';
import { createMockEngine } from './mock';
import type { AnonymizerEngine } from './types';

export type { AnonymizerEngine, EngineProgress } from './types';

function pickEngine(): AnonymizerEngine {
  const choice = import.meta.env.VITE_ENGINE;
  if (choice === 'local') return createLocalEngine();
  if (choice === 'mock') return createMockEngine();
  return createGradioEngine();
}

export const engine: AnonymizerEngine = pickEngine();
