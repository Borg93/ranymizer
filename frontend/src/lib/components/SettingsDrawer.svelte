<script lang="ts">
import { Play, RotateCcw, X } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
import {
  DEFAULT_PII_LABELS,
  type InferenceEngine,
  type PipelineVersion,
  type VlmBackend,
} from '$lib/types';
import { Button } from '$lib/components/ui/button';
import CollapsibleSection from './CollapsibleSection.svelte';

function close(): void {
  editor.settingsOpen = false;
}

function persist(): void {
  editor.persistPipelineConfig();
}

function toggleLabel(label: string): void {
  const enabled = new Set(editor.pipelineConfig.gliner.enabledLabels);
  if (enabled.has(label)) enabled.delete(label);
  else enabled.add(label);
  editor.pipelineConfig.gliner.enabledLabels = [...enabled];
  persist();
}

function applyAndRun(): Promise<void> {
  close();
  return editor.run();
}

function resetDefaults(): void {
  editor.resetPipelineConfig();
}

function onKeyDown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && editor.settingsOpen) close();
}

const enabledSet = $derived(new Set(editor.pipelineConfig.gliner.enabledLabels));
const labelCount = $derived(editor.pipelineConfig.gliner.enabledLabels.length);

// Shared classnames for the form controls (kept identical so the drawer feels uniform).
const inputCls =
  'min-w-0 w-full rounded-sm border border-border bg-background px-2 py-1 text-[12px] text-foreground outline-none focus:border-primary';
const selectCls =
  'w-full rounded-sm border border-border bg-background px-2 py-1 text-[12px] text-foreground';
const fieldLabelCls =
  'flex flex-col gap-1 text-[11px] text-muted-foreground';
const rowToggleCls =
  'flex items-center gap-2 rounded-md border border-border bg-transparent px-2 py-1.5 text-[12px] text-foreground hover:bg-surface2';
</script>

<svelte:window onkeydown={onKeyDown} />

{#if editor.settingsOpen}
  <div
    class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
    role="button"
    tabindex="-1"
    aria-label="Close settings"
    onclick={close}
    onkeydown={(e) => e.key === 'Enter' && close()}
  ></div>

  <div
    class="fixed right-0 top-0 z-50 flex h-screen w-[400px] max-w-[92vw] flex-col border-l border-border bg-card shadow-xl"
    role="dialog"
    aria-modal="true"
    aria-label="Pipeline settings"
  >
    <header class="flex h-10 shrink-0 items-center gap-2 border-b border-border px-4">
      <span class="flex-1 text-[13.5px] font-medium tracking-tight">Pipeline settings</span>
      <Button variant="ghost" size="icon-sm" onclick={close} aria-label="Close">
        <X />
      </Button>
    </header>

    <div class="flex-1 overflow-y-auto">
      <!-- ─── Runtime ────────────────────────────────────────────────── -->
      <CollapsibleSection title="Runtime">
        <div class="flex flex-col gap-3">
          <label class={fieldLabelCls}>
            <span>Pipeline version</span>
            <select
              class={selectCls}
              value={editor.pipelineConfig.pipelineVersion}
              onchange={(e) => {
                editor.pipelineConfig.pipelineVersion = (e.currentTarget as HTMLSelectElement)
                  .value as PipelineVersion;
                persist();
              }}
            >
              <option value="v1.5">v1.5 (default)</option>
              <option value="v1">v1</option>
            </select>
          </label>

          <label class={fieldLabelCls}>
            <span>Inference engine</span>
            <select
              class={selectCls}
              value={editor.pipelineConfig.engine}
              onchange={(e) => {
                editor.pipelineConfig.engine = (e.currentTarget as HTMLSelectElement)
                  .value as InferenceEngine;
                persist();
              }}
            >
              <option value="paddle">paddle (auto)</option>
              <option value="paddle_static">paddle_static</option>
              <option value="paddle_dynamic">paddle_dynamic</option>
              <option value="transformers">transformers</option>
            </select>
          </label>

          <label class={fieldLabelCls}>
            <span>Device</span>
            <input
              type="text"
              class={inputCls}
              placeholder="cpu, gpu:0, mps, npu:0…"
              value={editor.pipelineConfig.device}
              oninput={(e) => {
                editor.pipelineConfig.device = (e.currentTarget as HTMLInputElement).value;
                persist();
              }}
            />
            <span class="text-[10.5px] text-text3">Free-form. Server picks the first GPU when empty.</span>
          </label>
        </div>
      </CollapsibleSection>

      <!-- ─── GLiNER2 (PII) ──────────────────────────────────────────── -->
      <CollapsibleSection title="GLiNER2 — PII detection">
        <div class="flex flex-col gap-3">
          <label class={fieldLabelCls}>
            <span>Model</span>
            <input
              type="text"
              class={inputCls}
              value={editor.pipelineConfig.gliner.modelName}
              oninput={(e) => {
                editor.pipelineConfig.gliner.modelName = (e.currentTarget as HTMLInputElement).value;
                persist();
              }}
            />
          </label>

          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
              <span>Confidence threshold</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.gliner.threshold.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.95"
              step="0.05"
              value={editor.pipelineConfig.gliner.threshold}
              oninput={(e) => {
                editor.pipelineConfig.gliner.threshold = Number(
                  (e.currentTarget as HTMLInputElement).value,
                );
                persist();
              }}
              class="accent-primary"
            />
            <span class="text-[10.5px] text-text3">Lower = more recall, more false positives.</span>
          </label>

          <label class={fieldLabelCls}>
            <span>Device map</span>
            <select
              class={selectCls}
              value={editor.pipelineConfig.gliner.mapLocation}
              onchange={(e) => {
                editor.pipelineConfig.gliner.mapLocation = (e.currentTarget as HTMLSelectElement)
                  .value as 'cpu' | 'cuda';
                persist();
              }}
            >
              <option value="cuda">cuda</option>
              <option value="cpu">cpu</option>
            </select>
          </label>

          <label class={rowToggleCls}>
            <input
              type="checkbox"
              class="accent-primary"
              checked={editor.pipelineConfig.gliner.quantize}
              onchange={() => {
                editor.pipelineConfig.gliner.quantize = !editor.pipelineConfig.gliner.quantize;
                persist();
              }}
            />
            <span class="flex-1">Quantize (GPU only)</span>
          </label>
          <label class={rowToggleCls}>
            <input
              type="checkbox"
              class="accent-primary"
              checked={editor.pipelineConfig.gliner.compile}
              onchange={() => {
                editor.pipelineConfig.gliner.compile = !editor.pipelineConfig.gliner.compile;
                persist();
              }}
            />
            <span class="flex-1">torch.compile (GPU only)</span>
          </label>
        </div>
      </CollapsibleSection>

      <!-- ─── PII labels ─────────────────────────────────────────────── -->
      <CollapsibleSection title="PII labels" count={labelCount}>
        <div class="grid grid-cols-2 gap-1">
          {#each DEFAULT_PII_LABELS as label (label)}
            {@const isOn = enabledSet.has(label)}
            <button
              type="button"
              class="flex items-center gap-2 rounded-md border border-transparent px-2 py-1.5 text-left text-[12.5px] text-foreground transition-colors hover:bg-surface2 data-[active=true]:border-border data-[active=true]:bg-surface2 data-[active=false]:opacity-50"
              data-active={isOn}
              onclick={() => toggleLabel(label)}
            >
              <span
                class="h-3.5 w-[3px] shrink-0 rounded-[1.5px]"
                style:background={editor.catMeta[label]?.color ?? '#888'}
              ></span>
              <span class="flex-1 truncate">
                {editor.catMeta[label]?.label ?? label}
              </span>
            </button>
          {/each}
        </div>
      </CollapsibleSection>

      <!-- ─── PaddleOCR-VL layout + preprocessing ────────────────────── -->
      <CollapsibleSection title="PaddleOCR — layout & preprocessing" expanded={false}>
        <div class="flex flex-col gap-3">
          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
              <span>Layout threshold</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.paddleocr.layoutThreshold.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.95"
              step="0.05"
              value={editor.pipelineConfig.paddleocr.layoutThreshold}
              oninput={(e) => {
                editor.pipelineConfig.paddleocr.layoutThreshold = Number(
                  (e.currentTarget as HTMLInputElement).value,
                );
                persist();
              }}
              class="accent-primary"
            />
          </label>

          <div class="flex flex-col gap-2 text-[12px]">
            {#each [
              ['useDocOrientationClassify', 'Document orientation classify'],
              ['useDocUnwarping', 'Document unwarping'],
              ['useTextlineOrientation', 'Text-line orientation'],
              ['useChartRecognition', 'Chart recognition'],
              ['useSealRecognition', 'Seal (stamp) recognition'],
              ['useOcrForImageBlock', 'OCR inside image blocks'],
            ] as [key, label] (key)}
              {@const k = key as keyof typeof editor.pipelineConfig.paddleocr}
              <label class={rowToggleCls}>
                <input
                  type="checkbox"
                  class="accent-primary"
                  checked={editor.pipelineConfig.paddleocr[k] as boolean}
                  onchange={() => {
                    editor.pipelineConfig.paddleocr[k] =
                      !editor.pipelineConfig.paddleocr[k] as never;
                    persist();
                  }}
                />
                <span class="flex-1">{label}</span>
              </label>
            {/each}
          </div>
        </div>
      </CollapsibleSection>

      <!-- ─── VLM inference service ──────────────────────────────────── -->
      <CollapsibleSection title="VLM inference service" expanded={false}>
        <div class="flex flex-col gap-3">
          <label class={fieldLabelCls}>
            <span>Backend</span>
            <select
              class={selectCls}
              value={editor.pipelineConfig.vlm.backend}
              onchange={(e) => {
                editor.pipelineConfig.vlm.backend = (e.currentTarget as HTMLSelectElement)
                  .value as VlmBackend;
                persist();
              }}
            >
              <option value="">— local (no remote VLM) —</option>
              <option value="vllm-server">vllm-server</option>
              <option value="sglang-server">sglang-server</option>
              <option value="fastdeploy-server">fastdeploy-server</option>
              <option value="mlx-vlm-server">mlx-vlm-server (Apple Silicon)</option>
              <option value="llama-cpp-server">llama-cpp-server</option>
            </select>
          </label>

          <label class={fieldLabelCls}>
            <span>Server URL</span>
            <input
              type="text"
              class={inputCls}
              placeholder="http://localhost:8118/v1"
              value={editor.pipelineConfig.vlm.serverUrl}
              oninput={(e) => {
                editor.pipelineConfig.vlm.serverUrl = (e.currentTarget as HTMLInputElement).value;
                persist();
              }}
            />
          </label>

          <label class={fieldLabelCls}>
            <span>API model name</span>
            <input
              type="text"
              class={inputCls}
              placeholder="PaddlePaddle/PaddleOCR-VL-1.5"
              value={editor.pipelineConfig.vlm.apiModelName}
              oninput={(e) => {
                editor.pipelineConfig.vlm.apiModelName = (e.currentTarget as HTMLInputElement).value;
                persist();
              }}
            />
          </label>

          <label class={fieldLabelCls}>
            <span>API key</span>
            <input
              type="password"
              class={inputCls}
              placeholder="(only for hosted services)"
              value={editor.pipelineConfig.vlm.apiKey}
              oninput={(e) => {
                editor.pipelineConfig.vlm.apiKey = (e.currentTarget as HTMLInputElement).value;
                persist();
              }}
            />
            <span class="text-[10.5px] text-text3">
              Stored in localStorage. Rotate or clear before sharing the machine.
            </span>
          </label>
        </div>
      </CollapsibleSection>

      <!-- ─── VLM sampling ───────────────────────────────────────────── -->
      <CollapsibleSection title="VLM sampling" expanded={false}>
        <div class="flex flex-col gap-3">
          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
              <span>Temperature</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.vlm.temperature.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1.5"
              step="0.05"
              value={editor.pipelineConfig.vlm.temperature}
              oninput={(e) => {
                editor.pipelineConfig.vlm.temperature = Number(
                  (e.currentTarget as HTMLInputElement).value,
                );
                persist();
              }}
              class="accent-primary"
            />
          </label>

          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
              <span>top_p</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.vlm.topP.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0.1"
              max="1"
              step="0.05"
              value={editor.pipelineConfig.vlm.topP}
              oninput={(e) => {
                editor.pipelineConfig.vlm.topP = Number((e.currentTarget as HTMLInputElement).value);
                persist();
              }}
              class="accent-primary"
            />
          </label>

          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
              <span>Repetition penalty</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.vlm.repetitionPenalty.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="2"
              step="0.05"
              value={editor.pipelineConfig.vlm.repetitionPenalty}
              oninput={(e) => {
                editor.pipelineConfig.vlm.repetitionPenalty = Number(
                  (e.currentTarget as HTMLInputElement).value,
                );
                persist();
              }}
              class="accent-primary"
            />
          </label>

          <label class={fieldLabelCls}>
            <span>Max new tokens</span>
            <input
              type="number"
              min="32"
              max="32768"
              step="32"
              class={inputCls}
              value={editor.pipelineConfig.vlm.maxNewTokens}
              oninput={(e) => {
                const value = Number((e.currentTarget as HTMLInputElement).value);
                if (Number.isFinite(value)) {
                  editor.pipelineConfig.vlm.maxNewTokens = value;
                  persist();
                }
              }}
            />
          </label>

          <div class="grid grid-cols-2 gap-2">
            <label class={fieldLabelCls}>
              <span>min_pixels</span>
              <input
                type="number"
                min="0"
                step="1000"
                class={inputCls}
                value={editor.pipelineConfig.vlm.minPixels}
                oninput={(e) => {
                  const value = Number((e.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(value)) {
                    editor.pipelineConfig.vlm.minPixels = value;
                    persist();
                  }
                }}
              />
            </label>
            <label class={fieldLabelCls}>
              <span>max_pixels</span>
              <input
                type="number"
                min="0"
                step="1000"
                class={inputCls}
                value={editor.pipelineConfig.vlm.maxPixels}
                oninput={(e) => {
                  const value = Number((e.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(value)) {
                    editor.pipelineConfig.vlm.maxPixels = value;
                    persist();
                  }
                }}
              />
            </label>
          </div>
          <span class="text-[10.5px] text-text3">
            VLM image preprocessing bounds. 0 = leave default.
          </span>
        </div>
      </CollapsibleSection>
    </div>

    <footer class="flex shrink-0 items-center gap-2 border-t border-border px-4 py-3">
      <Button variant="ghost" size="sm" onclick={resetDefaults}>
        <RotateCcw />
        Reset
      </Button>
      <span class="flex-1"></span>
      <Button
        variant="default"
        size="sm"
        disabled={!editor.hasImage || editor.loading}
        onclick={applyAndRun}
      >
        <Play />
        Apply & Run
      </Button>
    </footer>
  </div>
{/if}
