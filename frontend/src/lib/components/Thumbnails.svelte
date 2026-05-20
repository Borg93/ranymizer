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

/**
 * Paint a thumbnail with redaction masks burned in. Re-runs whenever the
 * active page's working copy, the active idx (so we switch sources), or
 * the mask colour change. Other pages re-render whenever their snapshot
 * box count moves.
 */
function paintThumbnail(canvas: HTMLCanvasElement, pageIdx: number) {
  $effect(() => {
    // Track the reactive dependencies we care about.
    void editor.activeIdx;
    void editor.maskColor;
    if (pageIdx === editor.activeIdx) {
      void editor.boxes;
    } else {
      void editor.pages[pageIdx]?.boxes;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const rendered = editor.renderThumbnailCanvas(pageIdx, 240);
    if (!rendered) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    canvas.width = rendered.width;
    canvas.height = rendered.height;
    ctx.drawImage(rendered, 0, 0);
  });
}
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
        <canvas
          class="block h-full w-full object-cover"
          {@attach (node: HTMLCanvasElement) => paintThumbnail(node, i)}
          aria-label={p.filename}
        ></canvas>
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
