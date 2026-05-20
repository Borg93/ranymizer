<script lang="ts">
import { editor } from '$lib/state.svelte';

// Auto-scroll the active thumbnail into view as pagination changes.
let stripEl = $state<HTMLDivElement>();
$effect(() => {
  void editor.activeIdx;
  if (!stripEl) return;
  const el = stripEl.querySelector<HTMLElement>(`[data-idx="${editor.activeIdx}"]`);
  el?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
});
</script>

<div
  class="flex h-[88px] shrink-0 items-center gap-2 border-t border-border bg-card px-3"
>
  <div
    bind:this={stripEl}
    class="thumbs flex h-full flex-1 items-center gap-2 overflow-x-auto overflow-y-hidden py-2"
  >
    {#each editor.pages as p, i (p.objectUrl)}
      <button
        type="button"
        data-idx={i}
        class="group relative h-full w-[96px] shrink-0 overflow-hidden rounded-md border bg-background transition-colors data-[active=true]:border-primary"
        class:border-border={editor.activeIdx !== i}
        data-active={editor.activeIdx === i}
        onclick={() => editor.goTo(i)}
        title={p.filename}
      >
        <img src={p.objectUrl} alt={p.filename} class="h-full w-full object-cover" />
        <span
          class="absolute bottom-0 left-0 right-0 truncate bg-background/80 px-1 py-px text-center font-mono text-[9.5px] text-muted-foreground"
        >
          {i + 1}
        </span>
      </button>
    {/each}
  </div>
</div>

<style>
  /* Thin scrollbar on the thumb strip. */
  .thumbs::-webkit-scrollbar {
    height: 6px;
  }
  .thumbs::-webkit-scrollbar-thumb {
    background: var(--border-strong, rgba(255, 255, 255, 0.18));
    border-radius: 3px;
  }
</style>
