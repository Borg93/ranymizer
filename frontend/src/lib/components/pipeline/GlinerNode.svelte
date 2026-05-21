<script lang="ts">
/**
 * Compact GLiNER2 node — title + status chips (threshold, label count,
 * rule count) + the global threshold slider. All form-heavy editing
 * (labels grid, custom labels, per-label rules) lives in the inspector
 * on the right when this node is selected.
 */
import { Handle, Position, type NodeProps } from '@xyflow/svelte';
import { editor } from '$lib/state.svelte';
import { DEFAULT_LABEL_RULES, EMPTY_LABEL_RULE } from '$lib/types';

let { selected }: NodeProps = $props();

const cfg = $derived(editor.pipelineConfig.gliner);
const customCount = $derived(Object.keys(cfg.customLabels).length);
const ruleCount = $derived(
  Object.entries(cfg.rules).filter(([key, r]) => {
    if (!r) return false;
    const def = DEFAULT_LABEL_RULES[key] ?? EMPTY_LABEL_RULE;
    return (
      r.regex !== def.regex ||
      r.regexMode !== def.regexMode ||
      r.threshold !== def.threshold ||
      r.validateLuhn !== def.validateLuhn
    );
  }).length,
);
</script>

<div
  class="rounded-md border border-primary bg-card shadow-sm transition-all data-[selected=true]:ring-2 data-[selected=true]:ring-primary"
  data-selected={selected}
  style:width="240px"
>
  <Handle type="target" position={Position.Left} class="!h-2 !w-2 !bg-primary" />

  <div class="flex items-center gap-2 border-b border-border px-3 py-2">
    <span class="h-2 w-2 rounded-full bg-primary"></span>
    <div class="min-w-0 flex-1">
      <div class="text-[12px] font-semibold text-foreground">GLiNER2</div>
      <div class="font-mono text-[10px] text-text3 truncate" title={cfg.modelName}>
        {cfg.modelName.split('/').pop()}
      </div>
    </div>
  </div>

  <div class="flex flex-col gap-1.5 p-3">
    <div class="flex items-center justify-between text-[10.5px] text-muted-foreground">
      <span>Threshold</span>
      <span class="font-mono tabular-nums text-foreground">{cfg.threshold.toFixed(2)}</span>
    </div>
    <input
      type="range"
      min="0.1"
      max="0.95"
      step="0.05"
      value={cfg.threshold}
      oninput={(e) => {
        cfg.threshold = Number((e.currentTarget as HTMLInputElement).value);
        editor.persistPipelineConfig();
      }}
      class="nodrag accent-primary"
    />

    <div class="mt-1 flex flex-wrap gap-1">
      <span class="rounded-sm border border-border bg-background/40 px-1 text-[9.5px] font-mono text-muted-foreground">
        {cfg.enabledLabels.length} labels
      </span>
      {#if customCount > 0}
        <span class="rounded-sm border border-[var(--accent)] bg-[var(--accent-bg)] px-1 text-[9.5px] font-mono text-foreground">
          +{customCount} custom
        </span>
      {/if}
      {#if ruleCount > 0}
        <span class="rounded-sm border border-amber-500/50 bg-amber-500/10 px-1 text-[9.5px] font-mono text-amber-500">
          {ruleCount} rule{ruleCount === 1 ? '' : 's'}
        </span>
      {/if}
    </div>

    <div class="mt-1 text-[10px] text-text3">
      Click node → edit on the right.
    </div>
  </div>

  <Handle type="source" position={Position.Right} class="!h-2 !w-2 !bg-primary" />
</div>
