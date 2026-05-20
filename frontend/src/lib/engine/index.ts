// Build-time engine selection. VITE_ENGINE=local → desktop (on-device);
// anything else → showcase (Gradio). The unused branch tree-shakes away.
import { createGradioEngine } from './gradio';
import { createLocalEngine } from './local';
import type { AnonymizerEngine } from './types';

export type { AnonymizerEngine, EngineProgress } from './types';

export const engine: AnonymizerEngine =
  import.meta.env.VITE_ENGINE === 'local' ? createLocalEngine() : createGradioEngine();
