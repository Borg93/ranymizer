<script lang="ts">
/**
 * Live status indicator on each pipeline node. Three visual states:
 *  - idle:    dim gray dot
 *  - active:  primary-tinted dot with an animated `ping` halo
 *  - done:    solid emerald dot
 *
 * Consumers derive `status` from `editor.pipelineStage` — the SSE-driven
 * stage from `state.svelte.ts`.
 */
type Props = { status: 'idle' | 'active' | 'done' };
let { status }: Props = $props();
</script>

<span class="relative inline-flex h-2.5 w-2.5 items-center justify-center" aria-hidden="true">
  {#if status === 'active'}
    <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75"></span>
    <span class="relative inline-flex h-2 w-2 rounded-full bg-primary"></span>
  {:else if status === 'done'}
    <span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
  {:else}
    <span class="relative inline-flex h-2 w-2 rounded-full bg-text3 opacity-50"></span>
  {/if}
</span>
