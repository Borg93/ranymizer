<script lang="ts">
/** Small read-only I/O bookend (Image input, Pixel boxes output). */
import { Handle, Position, type Node, type NodeProps } from '@xyflow/svelte';

type IoData = { label: string; sub: string; side: 'in' | 'out' };
type IoNodeType = Node<IoData, 'io'>;
let { data, selected }: NodeProps<IoNodeType> = $props();
</script>

<div
  class="rounded-md border border-border bg-background/60 px-3 py-2 shadow-sm transition-all data-[selected=true]:ring-2 data-[selected=true]:ring-primary"
  data-selected={selected}
  style:width="120px"
>
  {#if data.side === 'in'}
    <Handle type="source" position={Position.Right} class="!h-2 !w-2 !bg-[var(--text3)]" />
  {:else}
    <Handle type="target" position={Position.Left} class="!h-2 !w-2 !bg-[var(--text3)]" />
  {/if}
  <div class="text-[11px] font-medium text-foreground">{data.label}</div>
  <div class="font-mono text-[9.5px] text-text3">{data.sub}</div>
</div>
