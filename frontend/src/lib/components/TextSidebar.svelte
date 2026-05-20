<script lang="ts">
import { AlertTriangle, Check, Copy, Pencil, Search, Trash2, X } from 'lucide-svelte';
import { SvelteSet } from 'svelte/reactivity';
import { editor } from '$lib/state.svelte';

let query = $state('');
let editingId = $state<number | null>(null);
const activeLabelFilter = new SvelteSet<string>();

// Resizable width — drag the right edge to adjust.
const MIN_WIDTH = 220;
const MAX_WIDTH = 520;
let width = $state(300);
let resizing = $state(false);
let resizeStartX = 0;
let resizeStartWidth = 0;

function onResizeStart(event: MouseEvent): void {
  if (event.button !== 0) return;
  event.preventDefault();
  resizing = true;
  resizeStartX = event.clientX;
  resizeStartWidth = width;
}

function onResizeMove(event: MouseEvent): void {
  if (!resizing) return;
  const next = resizeStartWidth + (event.clientX - resizeStartX);
  width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, next));
}

function onResizeEnd(): void {
  resizing = false;
}

function toggleLabelFilter(label: string): void {
  if (activeLabelFilter.has(label)) activeLabelFilter.delete(label);
  else activeLabelFilter.add(label);
}

function clearLabelFilter(): void {
  activeLabelFilter.clear();
}

function startEditing(id: number): void {
  editingId = id;
  editor.selected = id;
}

function stopEditing(): void {
  editingId = null;
}

function commitText(id: number, value: string): void {
  editor.setBoxText(id, value);
  stopEditing();
}

const categoryKeys = $derived(['custom', ...Object.keys(editor.catMeta).sort()]);

type Row = {
  id: number;
  label: string;
  text: string;
  confidence: number | null;
  custom: boolean;
};

const rows = $derived.by<Row[]>(() => {
  const out: Row[] = [];
  for (const box of editor.boxes) {
    let confidence: number | null = null;
    if (!box.custom) {
      const span = editor.spans.find((s) => s.label === box.label && s.text === box.text);
      if (span) confidence = span.confidence;
    }
    out.push({
      id: box.id,
      label: box.label,
      text: box.text,
      confidence,
      custom: box.custom,
    });
  }
  return out;
});

// One pill per category that actually has rows, sorted by count desc.
type LabelPill = { label: string; count: number; displayLabel: string; color: string };

const labelPills = $derived.by<LabelPill[]>(() => {
  const counts = new Map<string, number>();
  for (const r of rows) counts.set(r.label, (counts.get(r.label) ?? 0) + 1);
  return [...counts.entries()]
    .map(([label, count]): LabelPill => {
      const meta = editor.catMeta[label];
      return {
        label,
        count,
        displayLabel: meta?.label ?? label,
        color: label === 'custom' ? '#9ca3af' : (meta?.color ?? '#9ca3af'),
      };
    })
    .sort((a, b) => b.count - a.count);
});

const filteredRows = $derived.by<Row[]>(() => {
  const q = query.trim().toLowerCase();
  return rows.filter((r) => {
    if (activeLabelFilter.size > 0 && !activeLabelFilter.has(r.label)) return false;
    if (!q) return true;
    const catLabel = (editor.catMeta[r.label]?.label ?? r.label).toLowerCase();
    return (
      r.text.toLowerCase().includes(q) ||
      catLabel.includes(q) ||
      r.label.toLowerCase().includes(q)
    );
  });
});

function colorFor(label: string): string {
  if (label === 'custom') return '#9ca3af';
  return editor.catMeta[label]?.color ?? '#9ca3af';
}

function displayLabelFor(label: string): string {
  return editor.catMeta[label]?.label ?? label;
}
</script>

<svelte:window onmousemove={onResizeMove} onmouseup={onResizeEnd} />

<aside
  class="relative flex shrink-0 flex-col overflow-x-hidden overflow-y-auto border-r border-border bg-card max-md:hidden"
  style:width="{width}px"
>
  <header class="sticky top-0 z-10 border-b border-border bg-card px-3 py-2.5">
    <div class="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
      <span class="text-foreground">{filteredRows.length}</span>
      <span>/</span>
      <span>{rows.length} {rows.length === 1 ? 'box' : 'boxes'}</span>
      {#if editor.overlappingIds.size > 0}
        <span class="flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-500">
          <AlertTriangle class="h-3 w-3" />
          {editor.overlappingIds.size}
        </span>
      {/if}
      {#if editor.duplicateIds.size > 0}
        <span class="flex items-center gap-1 rounded bg-sky-500/10 px-1.5 py-0.5 text-sky-400">
          <Copy class="h-3 w-3" />
          {editor.duplicateIds.size}
        </span>
      {/if}
    </div>

    <div class="relative mt-2">
      <Search class="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text3" />
      <input
        type="search"
        bind:value={query}
        placeholder="Search text or category"
        class="search-input w-full rounded-md border border-border bg-background py-1.5 pl-7 pr-7 text-[12px] text-foreground outline-none focus:border-primary"
      />
      {#if query}
        <button
          type="button"
          class="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-text3 hover:text-foreground"
          onclick={() => (query = '')}
          aria-label="Clear search"
        >
          <X class="h-3.5 w-3.5" />
        </button>
      {/if}
    </div>

    {#if labelPills.length > 0}
      <div class="mt-2 flex flex-wrap gap-1">
        {#each labelPills as pill (pill.label)}
          {@const isActive = activeLabelFilter.has(pill.label)}
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10.5px] transition-colors data-[active=true]:border-primary data-[active=true]:bg-accent data-[active=true]:text-accent-foreground data-[active=false]:border-border data-[active=false]:text-muted-foreground data-[active=false]:hover:text-foreground"
            data-active={isActive}
            onclick={() => toggleLabelFilter(pill.label)}
          >
            <span
              class="h-2 w-2 shrink-0 rounded-full"
              style:background={pill.color}
            ></span>
            <span class="truncate">{pill.displayLabel}</span>
            <span class="font-mono tabular-nums text-text3">{pill.count}</span>
          </button>
        {/each}
        {#if activeLabelFilter.size > 0}
          <button
            type="button"
            class="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] text-text3 hover:text-foreground"
            onclick={clearLabelFilter}
            title="Clear filters"
          >
            <X class="h-3 w-3" />
            clear
          </button>
        {/if}
      </div>
    {/if}
  </header>

  {#if filteredRows.length === 0}
    <div class="px-4 py-6 text-center text-xs italic text-text3">
      {rows.length === 0
        ? 'No boxes yet. Press Run, or draw one on the canvas.'
        : 'No matches.'}
    </div>
  {:else}
    <div class="flex flex-col">
      {#each filteredRows as r (r.id)}
        {@const isEditing = editingId === r.id}
        {@const isSelected = editor.selected === r.id}
        {@const isOverlap = editor.overlappingIds.has(r.id)}
        {@const isDuplicate = editor.duplicateIds.has(r.id)}
        <div
          class="group flex items-start gap-2 border-b border-border px-3 py-2 text-[12px] transition-colors hover:bg-surface2 data-[selected=true]:bg-surface2"
          data-selected={isSelected}
        >
          <button
            type="button"
            class="mt-0.5 h-3.5 w-[3px] shrink-0 rounded-[1.5px]"
            style:background={colorFor(r.label)}
            onclick={() => (editor.selected = r.id)}
            aria-label="Select box"
            title={displayLabelFor(r.label)}
          ></button>

          <div class="flex min-w-0 flex-1 flex-col gap-1">
            {#if isEditing}
              <input
                type="text"
                class="min-w-0 rounded-sm border border-border bg-background px-1 py-0.5 text-foreground outline-none focus:border-primary"
                value={r.text}
                {@attach (node: HTMLInputElement) => {
                  node.focus();
                  node.select();
                }}
                onfocus={() => (editor.selected = r.id)}
                onkeydown={(e) => {
                  if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur();
                  if (e.key === 'Escape') stopEditing();
                }}
                onblur={(e) => commitText(r.id, (e.currentTarget as HTMLInputElement).value)}
              />
              <select
                class="min-w-0 max-w-full rounded-sm border border-border bg-background px-1 py-0.5 text-[10.5px] text-foreground"
                value={r.label}
                onchange={(e) =>
                  editor.setBoxLabel(r.id, (e.currentTarget as HTMLSelectElement).value)}
              >
                {#each categoryKeys as cat (cat)}
                  <option value={cat}>{displayLabelFor(cat)}</option>
                {/each}
              </select>
            {:else}
              <button
                type="button"
                class="min-w-0 truncate text-left text-foreground hover:text-primary"
                onclick={() => (editor.selected = r.id)}
                ondblclick={() => startEditing(r.id)}
                title={r.text || '(no text)'}
              >
                <span class="truncate">{r.text || '(no text)'}</span>
                {#if r.confidence !== null}
                  <span class="ml-1.5 font-mono text-[10.5px] tabular-nums text-text3">
                    · {(r.confidence * 100).toFixed(0)}%
                  </span>
                {/if}
              </button>

              <div class="flex flex-wrap items-center gap-1 text-[10.5px] text-text3">
                {#if isOverlap}
                  <span
                    class="flex items-center gap-0.5 rounded bg-amber-500/10 px-1 py-0.5 text-[9.5px] text-amber-500"
                    title="Overlaps another visible box"
                  >
                    <AlertTriangle class="h-2.5 w-2.5" />
                    overlap
                  </span>
                {/if}
                {#if isDuplicate}
                  <span
                    class="flex items-center gap-0.5 rounded bg-sky-500/10 px-1 py-0.5 text-[9.5px] text-sky-400"
                    title="Same category + text as another box"
                  >
                    <Copy class="h-2.5 w-2.5" />
                    dup
                  </span>
                {/if}
              </div>
            {/if}
          </div>

          <div class="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 data-[on=true]:opacity-100" data-on={isEditing || isSelected}>
            {#if isEditing}
              <button
                type="button"
                class="rounded-md p-1 text-muted-foreground hover:bg-surface2 hover:text-foreground"
                onclick={stopEditing}
                aria-label="Done editing"
                title="Done (Enter)"
              >
                <Check class="h-3.5 w-3.5" />
              </button>
            {:else}
              <button
                type="button"
                class="rounded-md p-1 text-muted-foreground hover:bg-surface2 hover:text-foreground"
                onclick={() => startEditing(r.id)}
                aria-label="Edit row"
                title="Edit (double-click row)"
              >
                <Pencil class="h-3.5 w-3.5" />
              </button>
            {/if}
            <button
              type="button"
              class="rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              onclick={() => editor.removeBox(r.id)}
              aria-label="Delete box"
              title="Delete"
            >
              <Trash2 class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Resize handle on the right edge -->
  <div
    role="separator"
    aria-orientation="vertical"
    aria-label="Resize text panel"
    class="resize-handle absolute -right-1.5 top-0 z-10 flex h-full w-3 cursor-ew-resize items-center justify-center"
    class:active={resizing}
    onmousedown={onResizeStart}
  >
    <span class="grip" aria-hidden="true"></span>
  </div>
</aside>

<style>
  /* Hide the native WebKit / Chromium search clear button so only our
     custom one shows. */
  .search-input::-webkit-search-cancel-button,
  .search-input::-webkit-search-decoration {
    -webkit-appearance: none;
    appearance: none;
  }

  .resize-handle .grip {
    width: 2px;
    height: 28px;
    border-radius: 2px;
    background: var(--border-strong, rgba(255, 255, 255, 0.22));
    transition:
      background-color 120ms ease,
      height 120ms ease;
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
