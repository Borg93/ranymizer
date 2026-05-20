// WebGPU adapter detection (model-agnostic, from the demo). The WASM
// fallback matters: WebGPU support varies across Tauri WebViews.
export type ComputeDevice = 'webgpu' | 'wasm';
export type BackendPreference = 'auto' | 'webgpu' | 'wasm';

export async function detectDevice(): Promise<ComputeDevice> {
  if (typeof navigator === 'undefined') return 'wasm';
  const gpu = (navigator as Navigator & { gpu?: { requestAdapter: () => Promise<unknown> } }).gpu;
  if (!gpu) return 'wasm';
  try {
    if (await gpu.requestAdapter()) return 'webgpu';
  } catch {
    // no usable adapter → wasm
  }
  return 'wasm';
}

export async function resolveBackend(pref: BackendPreference): Promise<ComputeDevice> {
  if (pref === 'wasm') return 'wasm';
  const detected = await detectDevice();
  if (pref === 'webgpu' && detected !== 'webgpu') {
    throw new Error('WebGPU requested but no adapter is available. Use Auto or WASM.');
  }
  return detected;
}
