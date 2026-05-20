import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  // ONNX runtime stays out of pre-bundling so the worker loads it lazily.
  optimizeDeps: {
    exclude: ['@huggingface/transformers']
  },
  worker: {
    format: 'es'
  },
  server: {
    port: 5173,
    strictPort: false
  }
});
