<script lang="ts">
import { MousePointer2, Minus, Download, Copy } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
import { Button } from '$lib/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '$lib/components/ui/toggle-group';
import { Badge } from '$lib/components/ui/badge';

type Props = {
  onDownload: () => void;
  onCopy: () => void | Promise<void>;
  onExportText: () => void;
};
let { onDownload, onCopy, onExportText }: Props = $props();

const summary = $derived.by(() => {
  const visible = editor.visibleBoxes;
  const cats = new Set<string>();
  for (const b of visible) cats.add(b.custom ? 'custom' : b.label);
  return { bars: visible.length, cats: cats.size };
});

const distribution = $derived.by(() => {
  const visible = editor.visibleBoxes;
  if (!visible.length) return [] as Array<{ key: string; pct: number; color: string }>;
  const counts: Record<string, number> = {};
  for (const b of visible) {
    const k = b.custom ? 'custom' : b.label;
    counts[k] = (counts[k] ?? 0) + 1;
  }
  const total = visible.length;
  return Object.entries(counts).map(([k, n]) => ({
    key: k,
    pct: (n / total) * 100,
    color: k === 'custom' ? '#9ca3af' : (editor.catMeta[k]?.color ?? '#888'),
  }));
});

const categoryRows = $derived(
  Object.keys(editor.catCounts).map((cat) => ({
    cat,
    meta: editor.catMeta[cat] ?? { color: '#888', label: cat },
    count: editor.catCounts[cat],
    active: editor.activeCats.has(cat),
  })),
);
</script>

<aside
  class="flex w-[272px] shrink-0 flex-col overflow-y-auto border-l border-border bg-card max-md:w-full max-md:max-h-[44vh] max-md:border-l-0 max-md:border-t"
>
  <!-- Tool -->
  <section class="border-b border-border px-4 py-3.5">
    <div class="mb-2 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
      Tool
    </div>

    <ToggleGroup
      type="single"
      value={editor.mode}
      onValueChange={(v) => v && editor.setMode(v as 'select' | 'draw')}
      class="mb-3 grid w-full grid-cols-2 gap-1.5"
    >
      <ToggleGroupItem
        value="select"
        class="data-[state=on]:border-primary data-[state=on]:bg-accent data-[state=on]:text-accent-foreground h-auto justify-start gap-2 border border-border bg-transparent p-2.5 text-muted-foreground hover:border-border hover:text-foreground"
        aria-label="Select tool"
      >
        <MousePointer2 class="h-4 w-4" />
        <span class="flex-1 text-left text-[13px] font-medium tracking-tight">Select</span>
        <span class="rounded-sm border border-border bg-background px-1 font-mono text-[10.5px] text-text3">V</span>
      </ToggleGroupItem>
      <ToggleGroupItem
        value="draw"
        class="data-[state=on]:border-primary data-[state=on]:bg-accent data-[state=on]:text-accent-foreground h-auto justify-start gap-2 border border-border bg-transparent p-2.5 text-muted-foreground hover:border-border hover:text-foreground"
        aria-label="Draw tool"
      >
        <Minus class="h-4 w-4" strokeWidth={3} />
        <span class="flex-1 text-left text-[13px] font-medium tracking-tight">Draw</span>
        <span class="rounded-sm border border-border bg-background px-1 font-mono text-[10.5px] text-text3">B</span>
      </ToggleGroupItem>
    </ToggleGroup>

    <div class="rounded-md border border-border bg-surface2 px-2.5 py-2 text-xs text-muted-foreground">
      {#if editor.mode === 'select'}
        <div>Click a bar to select. Drag to move. <kbd class="rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px]">Del</kbd> to remove.</div>
        <div class="mt-1.5 flex flex-wrap gap-1.5">
          <kbd class="rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px]">V</kbd>
          <span class="text-text3">·</span>
          <kbd class="rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px]">B</kbd>
          <span class="text-text3">·</span>
          <kbd class="rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px]">Esc</kbd>
        </div>
      {:else}
        <div>Drag on empty canvas to add a black bar. Release to confirm.</div>
        <div class="mt-1.5 flex flex-wrap gap-1.5">
          <kbd class="rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px]">B</kbd>
          <span class="text-text3">·</span>
          <kbd class="rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px]">V</kbd>
          <span class="text-text3">·</span>
          <kbd class="rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px]">0</kbd>
        </div>
      {/if}
    </div>
  </section>

  <!-- Detected -->
  <section class="border-b border-border px-4 py-3.5">
    <div class="mb-2 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
      Detected
    </div>
    <div class="mb-2 font-mono text-[11.5px] text-muted-foreground">
      <span class="text-foreground">{summary.bars}</span>
      {summary.bars === 1 ? 'bar' : 'bars'} across
      <span class="text-foreground">{summary.cats}</span>
      {summary.cats === 1 ? 'category' : 'categories'}
    </div>
    <div class="flex h-1 overflow-hidden rounded-sm bg-surface2">
      {#each distribution as seg (seg.key)}
        <div
          class="h-full transition-[width] duration-300 ease-out"
          style:width="{seg.pct}%"
          style:background={seg.color}
        ></div>
      {/each}
    </div>
  </section>

  <!-- Categories -->
  <section class="border-b border-border px-4 py-3.5">
    <div class="mb-2 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
      Categories
    </div>
    <div class="flex flex-col gap-0.5">
      {#if categoryRows.length === 0}
        <div class="py-1 text-xs italic text-text3">no pii detected</div>
      {:else}
        {#each categoryRows as row (row.cat)}
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-md border border-transparent px-2 py-1.5 text-left transition-colors hover:bg-surface2 data-[active=true]:border-border data-[active=true]:bg-surface2 data-[active=false]:opacity-40"
            data-active={row.active}
            onclick={() => editor.toggleCategory(row.cat)}
          >
            <span
              class="h-3.5 w-[3px] shrink-0 rounded-[1.5px]"
              style:background={row.meta.color}
            ></span>
            <span class="flex-1 text-[12.5px] text-foreground">{row.meta.label}</span>
            <Badge variant="secondary" class="font-mono text-[10.5px]">{row.count}</Badge>
          </button>
        {/each}
      {/if}
    </div>
  </section>

  <!-- Export -->
  <section class="px-4 py-3.5">
    <div class="mb-2 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
      Export
    </div>
    <div class="flex flex-col gap-1">
      <Button variant="outline" class="justify-between" onclick={onDownload}>
        <span class="flex items-center gap-2">
          <Download class="h-3.5 w-3.5" />
          Download PNG
        </span>
        <kbd class="rounded-sm border border-border bg-card px-1 py-px font-mono text-[10.5px] text-muted-foreground">⌘S</kbd>
      </Button>
      <Button variant="outline" class="justify-between" onclick={onCopy}>
        <span class="flex items-center gap-2">
          <Copy class="h-3.5 w-3.5" />
          Copy to clipboard
        </span>
        <kbd class="rounded-sm border border-border bg-card px-1 py-px font-mono text-[10.5px] text-muted-foreground">⌘⇧C</kbd>
      </Button>
      <button
        type="button"
        class="px-0.5 pt-1.5 text-left text-[11.5px] text-muted-foreground transition-colors hover:text-text2"
        onclick={onExportText}
      >
        Export sanitized text only →
      </button>
    </div>
  </section>
</aside>
