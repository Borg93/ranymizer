<script lang="ts">
/**
 * Compact PaddleOCR node. Shows only the title, live status chips, and the
 * primary "Layout threshold" slider. Everything else (preprocessing toggles)
 * lives in the right-side PipelineInspector when this node is selected.
 */
import { Handle, Position, type NodeProps } from '@xyflow/svelte';
import { editor } from '$lib/state.svelte';

let { selected }: NodeProps = $props();

const cfg = $derived(editor.pipelineConfig.paddleocr);
const optCount = $derived(
  [
    cfg.useDocOrientationClassify,
    cfg.useDocUnwarping,
    cfg.useTextlineOrientation,
    cfg.useChartRecognition,
    cfg.useSealRecognition,
    cfg.useOcrForImageBlock,
  ].filter(Boolean).length,
);
</script>

<div
  class="rounded-md border bg-card shadow-sm transition-all data-[selected=true]:ring-2 data-[selected=true]:ring-primary"
  class:border-primary={true}
  data-selected={selected}
  style:width="220px"
>
  <Handle type="target" position={Position.Left} class="!h-2 !w-2 !bg-primary" />

  <div class="flex items-center gap-2 border-b border-border px-3 py-2">
    <span class="h-2 w-2 rounded-full bg-primary"></span>
    <div class="min-w-0 flex-1">
      <div class="text-[12px] font-semibold text-foreground">PaddleOCR</div>
      <div class="font-mono text-[10px] text-text3">det + rec</div>
    </div>
  </div>

  <div class="flex flex-col gap-1.5 p-3">
    <div class="flex items-center justify-between text-[10.5px] text-muted-foreground">
      <span>Layout ≥</span>
      <span class="font-mono tabular-nums text-foreground">{cfg.layoutThreshold.toFixed(2)}</span>
    </div>
    <input
      type="range"
      min="0.1"
      max="0.95"
      step="0.05"
      value={cfg.layoutThreshold}
      oninput={(e) => {
        cfg.layoutThreshold = Number((e.currentTarget as HTMLInputElement).value);
        editor.persistPipelineConfig();
      }}
      class="nodrag accent-primary"
    />

    {#if optCount > 0}
      <div class="mt-1 flex flex-wrap gap-1">
        {#if cfg.useDocOrientationClassify}
          <span class="rounded-sm border border-[var(--accent)] bg-[var(--accent-bg)] px-1 text-[9.5px] text-foreground">orient</span>
        {/if}
        {#if cfg.useDocUnwarping}
          <span class="rounded-sm border border-[var(--accent)] bg-[var(--accent-bg)] px-1 text-[9.5px] text-foreground">unwarp</span>
        {/if}
        {#if cfg.useTextlineOrientation}
          <span class="rounded-sm border border-[var(--accent)] bg-[var(--accent-bg)] px-1 text-[9.5px] text-foreground">textline</span>
        {/if}
        {#if cfg.useChartRecognition}
          <span class="rounded-sm border border-[var(--accent)] bg-[var(--accent-bg)] px-1 text-[9.5px] text-foreground">chart</span>
        {/if}
        {#if cfg.useSealRecognition}
          <span class="rounded-sm border border-[var(--accent)] bg-[var(--accent-bg)] px-1 text-[9.5px] text-foreground">seal</span>
        {/if}
        {#if cfg.useOcrForImageBlock}
          <span class="rounded-sm border border-[var(--accent)] bg-[var(--accent-bg)] px-1 text-[9.5px] text-foreground">img-ocr</span>
        {/if}
      </div>
    {:else}
      <div class="text-[10px] text-text3">No preprocessing enabled.</div>
    {/if}

    <div class="mt-1 text-[10px] text-text3">
      Click node → edit on the right.
    </div>
  </div>

  <Handle type="source" position={Position.Right} class="!h-2 !w-2 !bg-primary" />
</div>
