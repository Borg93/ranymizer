<script lang="ts">
import { MousePointer2, Square, Download, Copy, ScanText, FilePlus2, Palette } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
import { Button } from '$lib/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '$lib/components/ui/toggle-group';
import { Badge } from '$lib/components/ui/badge';

// All known category keys, sorted so the picker order is stable.
const categoryKeys = $derived(['custom', ...Object.keys(editor.catMeta).sort()]);

// Hidden file input for the "Add image" action at the bottom of the sidebar.
let addFileInput = $state<HTMLInputElement>();
function onAddFiles(e: Event) {
  const t = e.currentTarget as HTMLInputElement;
  const list = t.files ? Array.from(t.files) : [];
  if (list.length > 0) editor.uploadFiles(list, { append: true });
  t.value = ''; // allow re-selecting the same file later
}

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
        <Square class="h-4 w-4" />
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
      title="Preview-only — exports still use solid black bars"
    >
      <Palette class="h-3.5 w-3.5" />
      <span class="flex-1 text-[12.5px] font-medium tracking-tight">Color masks</span>
    </button>

    {#if editor.showCategoryColors}
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
    {/if}

    <!-- Solid mask color (used when color masks is off, and always for the
         exported PNG). -->
    <label class="mt-2 flex items-center gap-2 px-1 text-[11px] text-muted-foreground">
      <span class="w-12 shrink-0">Mask</span>
      <input
        type="color"
        bind:value={editor.maskColor}
        class="h-6 w-9 cursor-pointer rounded border border-border bg-transparent p-0.5"
        aria-label="Mask color"
        title="Mask color (also applied to the exported PNG)"
      />
      <span class="flex-1 font-mono text-[10.5px] uppercase tabular-nums text-foreground">
        {editor.maskColor}
      </span>
    </label>
  </section>

  <!-- Box category: re-labels the selected box, or pre-sets the category
       for the next drawn box. Hidden when neither applies. -->
  {#if editor.selectedBox || editor.mode === 'draw'}
    <section class="border-b border-border px-4 py-3.5">
      <div class="mb-2 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
        {editor.selectedBox ? 'Selected box category' : 'Next box category'}
      </div>
      {#if editor.selectedBox}
        <select
          class="w-full rounded-md border border-border bg-card px-2 py-1.5 text-[12.5px] text-foreground"
          value={editor.selectedBox.label}
          onchange={(e) =>
            editor.selected !== null &&
            editor.setBoxLabel(editor.selected, (e.currentTarget as HTMLSelectElement).value)}
        >
          {#each categoryKeys as cat}
            <option value={cat}>{editor.catMeta[cat]?.label ?? cat}</option>
          {/each}
        </select>
      {:else}
        <select
          class="w-full rounded-md border border-border bg-card px-2 py-1.5 text-[12.5px] text-foreground"
          bind:value={editor.drawLabel}
        >
          {#each categoryKeys as cat}
            <option value={cat}>{editor.catMeta[cat]?.label ?? cat}</option>
          {/each}
        </select>
      {/if}
    </section>
  {/if}

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

  <!-- Add another image / PDF — appends to the current set so pagination
       keeps the old uploads alongside the new one. -->
  <section class="border-t border-border px-4 py-3.5">
    <input
      bind:this={addFileInput}
      type="file"
      class="hidden"
      accept="image/*,application/pdf"
      multiple
      onchange={onAddFiles}
    />
    <Button
      variant="default"
      class="w-full justify-center"
      onclick={() => addFileInput?.click()}
    >
      <FilePlus2 class="mr-2 h-3.5 w-3.5" />
      Add image
    </Button>
  </section>
</aside>

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
