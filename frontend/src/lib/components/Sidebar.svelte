<script lang="ts">
import { Copy, Download, MousePointer2, Palette, ScanText, Square } from 'lucide-svelte';
import ShortcutHelp from './ShortcutHelp.svelte';

let helpOpen = $state(false);
import { editor } from '$lib/state.svelte';
import { Button } from '$lib/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '$lib/components/ui/toggle-group';
import { Badge } from '$lib/components/ui/badge';
import CollapsibleSection from './CollapsibleSection.svelte';

// All known category keys, sorted so the picker order is stable.
const categoryKeys = $derived(['custom', ...Object.keys(editor.catMeta).sort()]);

let categoriesExpanded = $state(true);

type Props = {
  onDownload: () => void;
  onCopy: () => void | Promise<void>;
  onExportText: () => void;
};
let { onDownload, onCopy, onExportText }: Props = $props();

// Resizable width — drag the left edge to adjust.
const MIN_W = 220;
const MAX_W = 520;
let width = $state(272);
let resizing = $state(false);
let startX = 0;
let startW = 0;

function onResizeStart(ev: MouseEvent) {
  if (ev.button !== 0) return;
  ev.preventDefault();
  resizing = true;
  startX = ev.clientX;
  startW = width;
}

function onResizeMove(ev: MouseEvent) {
  if (!resizing) return;
  const next = startW + (startX - ev.clientX);
  width = Math.max(MIN_W, Math.min(MAX_W, next));
}

function onResizeEnd() {
  resizing = false;
}

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

<svelte:window onmousemove={onResizeMove} onmouseup={onResizeEnd} />

<aside
  class="relative flex shrink-0 flex-col overflow-y-auto border-l border-border bg-card max-md:w-full max-md:max-h-[44vh] max-md:border-l-0 max-md:border-t"
  style:width="{width}px"
>
  <!-- Resize handle — drag horizontally to set sidebar width. Visible by
       default with a subtle grip; primary-tinted on hover / active. -->
  <div
    role="separator"
    aria-orientation="vertical"
    aria-label="Resize sidebar"
    class="resize-handle absolute -left-1.5 top-0 z-10 flex h-full w-3 cursor-ew-resize items-center justify-center max-md:hidden"
    class:active={resizing}
    onmousedown={onResizeStart}
  >
    <span class="grip" aria-hidden="true"></span>
  </div>
  <!-- Tool -->
  <section class="border-b border-border px-4 py-3.5">
    <div class="mb-2 flex items-center gap-2 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
      <span class="flex-1">Tool</span>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-md border border-border bg-card px-1.5 py-0.5 normal-case tracking-normal text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
        onclick={() => (helpOpen = true)}
        title="Show all keyboard shortcuts (press ? anywhere)"
      >
        <kbd class="rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px] text-foreground">
          ?
        </kbd>
        <span class="text-[10.5px]">Shortcuts</span>
      </button>
    </div>

    <ToggleGroup
      type="single"
      value={editor.mode}
      onValueChange={(v) => v && editor.setMode(v as 'select' | 'draw')}
      class="grid w-full grid-cols-2 gap-1.5"
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
        <Square class="h-4 w-4" />
        <span class="flex-1 text-left text-[13px] font-medium tracking-tight">Draw</span>
        <span class="rounded-sm border border-border bg-background px-1 font-mono text-[10.5px] text-text3">B</span>
      </ToggleGroupItem>
    </ToggleGroup>

    <!-- Category picker sits inline with the tool toggle so the user
         doesn't have to hunt for it after pressing Draw. Re-labels the
         current selection if one exists, otherwise pre-sets the category
         for the next drawn box. -->
    {#if editor.selectedBox || editor.mode === 'draw'}
      <div class="mt-2.5 flex flex-col gap-1">
        <span class="text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
          {editor.selectedBox ? 'Selected box category' : 'Next box category'}
        </span>
        {#if editor.selectedBox}
          <select
            class="w-full rounded-md border border-border bg-card px-2 py-1.5 text-[12.5px] text-foreground"
            value={editor.selectedBox.label}
            onchange={(e) =>
              editor.selected !== null &&
              editor.setBoxLabel(editor.selected, (e.currentTarget as HTMLSelectElement).value)}
          >
            {#each categoryKeys as cat (cat)}
              <option value={cat}>{editor.catMeta[cat]?.label ?? cat}</option>
            {/each}
          </select>
        {:else}
          <select
            class="w-full rounded-md border border-border bg-card px-2 py-1.5 text-[12.5px] text-foreground"
            bind:value={editor.drawLabel}
          >
            {#each categoryKeys as cat (cat)}
              <option value={cat}>{editor.catMeta[cat]?.label ?? cat}</option>
            {/each}
          </select>
        {/if}
      </div>
    {/if}
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

    <button
      type="button"
      class="mt-3 flex w-full items-center gap-2 rounded-md border border-border bg-transparent px-2.5 py-1.5 text-left transition-colors hover:bg-surface2 data-[active=true]:border-primary data-[active=true]:bg-accent data-[active=true]:text-accent-foreground"
      data-active={editor.showOcrLines}
      onclick={() => (editor.showOcrLines = !editor.showOcrLines)}
      disabled={editor.ocrLines.length === 0}
    >
      <ScanText class="h-3.5 w-3.5" />
      <span class="flex-1 text-[12.5px] font-medium tracking-tight">OCR lines</span>
      <Badge variant="secondary" class="font-mono text-[10.5px]">{editor.ocrLines.length}</Badge>
    </button>

    <button
      type="button"
      class="mt-1.5 flex w-full items-center gap-2 rounded-md border border-border bg-transparent px-2.5 py-1.5 text-left transition-colors hover:bg-surface2 data-[active=true]:border-primary data-[active=true]:bg-accent data-[active=true]:text-accent-foreground"
      data-active={editor.showCategoryColors}
      onclick={() => (editor.showCategoryColors = !editor.showCategoryColors)}
      title="Preview-only — exports always use solid bars"
    >
      <Palette class="h-3.5 w-3.5" />
      <span class="flex-1 text-[12.5px] font-medium tracking-tight">Color masks</span>
    </button>

    {#if editor.showCategoryColors}
      <!-- Unified | Per-category -->
      <div class="mt-2 grid grid-cols-2 gap-1 rounded-md border border-border bg-background p-0.5">
        <button
          type="button"
          class="rounded-sm py-1 text-[11px] tracking-tight transition-colors data-[active=true]:bg-accent data-[active=true]:text-accent-foreground data-[active=false]:text-muted-foreground data-[active=false]:hover:text-foreground"
          data-active={editor.colorMaskMode === 'unified'}
          onclick={() => (editor.colorMaskMode = 'unified')}
        >
          Unified
        </button>
        <button
          type="button"
          class="rounded-sm py-1 text-[11px] tracking-tight transition-colors data-[active=true]:bg-accent data-[active=true]:text-accent-foreground data-[active=false]:text-muted-foreground data-[active=false]:hover:text-foreground"
          data-active={editor.colorMaskMode === 'per-category'}
          onclick={() => (editor.colorMaskMode = 'per-category')}
        >
          Per category
        </button>
      </div>

      <label class="mt-2 flex items-center gap-2 px-1 text-[11px] text-muted-foreground">
        <span class="w-12 shrink-0">Opacity</span>
        <input
          type="range"
          min="0.1"
          max="1"
          step="0.05"
          bind:value={editor.maskAlpha}
          class="flex-1 accent-primary"
        />
        <span class="w-8 text-right font-mono tabular-nums text-foreground">
          {Math.round(editor.maskAlpha * 100)}%
        </span>
      </label>

      {#if editor.colorMaskMode === 'unified'}
        <label class="mt-2 flex items-center gap-2 px-1 text-[11px] text-muted-foreground">
          <span class="w-12 shrink-0">Color</span>
          <input
            type="color"
            bind:value={editor.maskColor}
            class="h-6 w-9 cursor-pointer rounded border border-border bg-transparent p-0.5"
            aria-label="Mask color"
            title="Unified mask color (also used by the exported PNG)"
          />
          <span class="flex-1 font-mono text-[10.5px] uppercase tabular-nums text-foreground">
            {editor.maskColor}
          </span>
        </label>
      {/if}
    {/if}
  </section>


  <CollapsibleSection title="Categories" count={categoryRows.length} bind:expanded={categoriesExpanded}>
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
  </CollapsibleSection>

  <CollapsibleSection title="Export" expanded={false} bordered={false}>
    <div class="flex flex-col gap-1">
      <Button variant="outline" class="justify-between" onclick={onDownload}>
        <span class="flex items-center gap-2">
          <Download class="h-3.5 w-3.5" />
          {editor.pageCount > 1 ? `Download ZIP (${editor.pageCount} pages)` : 'Download PNG'}
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
  </CollapsibleSection>

</aside>

<ShortcutHelp bind:open={helpOpen} />

<style>
  .resize-handle .grip {
    width: 2px;
    height: 28px;
    border-radius: 2px;
    background: var(--border-strong, rgba(255, 255, 255, 0.22));
    transition: background-color 120ms ease, height 120ms ease;
  }
  .resize-handle:hover .grip {
    background: var(--primary, #818cf8);
    height: 56px;
  }
  .resize-handle.active .grip {
    background: var(--primary, #818cf8);
    height: 100%;
  }
</style>
