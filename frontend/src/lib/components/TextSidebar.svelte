<script lang="ts">
import { Trash2, Search, X, AlertTriangle, Copy, ChevronDown, ChevronRight } from 'lucide-svelte';
import { SvelteSet } from 'svelte/reactivity';
import { editor } from '$lib/state.svelte';

let query = $state('');
// Track which category groups are collapsed. Empty = all expanded.
const collapsed = new SvelteSet<string>();
function toggleGroup(key: string) {
  if (collapsed.has(key)) collapsed.delete(key);
  else collapsed.add(key);
}

// Resizable width — drag the right edge to adjust.
const MIN_W = 220;
const MAX_W = 520;
let width = $state(300);
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
  const next = startW + (ev.clientX - startX);
  width = Math.max(MIN_W, Math.min(MAX_W, next));
}

function onResizeEnd() {
  resizing = false;
}

const categoryKeys = $derived(['custom', ...Object.keys(editor.catMeta).sort()]);

// One row per editor box, joined with its source PII span (if any) for the
// confidence score. Custom boxes have no span → confidence is null.
type Row = {
  id: number;
  label: string;
  text: string;
  confidence: number | null;
  custom: boolean;
};

const rows = $derived.by<Row[]>(() => {
  const out: Row[] = [];
  for (const b of editor.boxes) {
    let conf: number | null = null;
    if (!b.custom) {
      // Match by label + text since boxes don't carry span ids.
      const sp = editor.spans.find((s) => s.label === b.label && s.text === b.text);
      if (sp) conf = sp.confidence;
    }
    out.push({ id: b.id, label: b.label, text: b.text, confidence: conf, custom: b.custom });
  }
  return out;
});

// Filter by free-text search (matches text or category label, case-insensitive).
const filteredRows = $derived.by<Row[]>(() => {
  const q = query.trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((r) => {
    const catLabel = (editor.catMeta[r.label]?.label ?? r.label).toLowerCase();
    return r.text.toLowerCase().includes(q) || catLabel.includes(q) || r.label.toLowerCase().includes(q);
  });
});

// Group rows by category label so they render as collapsible sections.
type Group = { key: string; label: string; color: string; rows: Row[] };
const groups = $derived.by<Group[]>(() => {
  const m = new Map<string, Row[]>();
  for (const r of filteredRows) {
    const list = m.get(r.label);
    if (list) list.push(r);
    else m.set(r.label, [r]);
  }
  return [...m.entries()]
    .map<Group>(([key, rs]) => {
      const meta = editor.catMeta[key];
      return {
        key,
        label: meta?.label ?? key,
        color: key === 'custom' ? '#9ca3af' : (meta?.color ?? '#9ca3af'),
        rows: rs,
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label));
});
</script>

<svelte:window onmousemove={onResizeMove} onmouseup={onResizeEnd} />

<aside
  class="relative flex shrink-0 flex-col overflow-x-hidden overflow-y-auto border-r border-border bg-card max-md:hidden"
  style:width="{width}px"
>
  <header class="sticky top-0 z-10 border-b border-border bg-card px-4 py-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
      Detected text
    </div>
    <div class="mt-1 flex flex-wrap items-center gap-2 font-mono text-[11px] text-muted-foreground">
      <span>{filteredRows.length} / {rows.length} {rows.length === 1 ? 'box' : 'boxes'}</span>
      {#if editor.overlappingIds.size > 0}
        <span class="flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-500">
          <AlertTriangle class="h-3 w-3" />
          {editor.overlappingIds.size} overlap
        </span>
      {/if}
      {#if editor.duplicateIds.size > 0}
        <span class="flex items-center gap-1 rounded bg-sky-500/10 px-1.5 py-0.5 text-sky-400">
          <Copy class="h-3 w-3" />
          {editor.duplicateIds.size} duplicate
        </span>
      {/if}
    </div>

    <div class="relative mt-2">
      <Search class="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text3" />
      <input
        type="search"
        bind:value={query}
        placeholder="Search text or category"
        class="w-full rounded-md border border-border bg-background py-1.5 pl-7 pr-7 text-[12px] text-foreground outline-none focus:border-primary"
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
  </header>

  {#if filteredRows.length === 0}
    <div class="px-4 py-6 text-center text-xs italic text-text3">
      {rows.length === 0 ? 'No boxes yet. Run analysis or draw one on the canvas.' : 'No matches.'}
    </div>
  {:else}
    <div class="flex flex-col">
      {#each groups as g (g.key)}
        {@const isCollapsed = collapsed.has(g.key)}
        <button
          type="button"
          class="flex w-full items-center gap-2 border-b border-border bg-card/60 px-3 py-1.5 text-left transition-colors hover:bg-surface2"
          onclick={() => toggleGroup(g.key)}
        >
          {#if isCollapsed}
            <ChevronRight class="h-3.5 w-3.5 text-muted-foreground" />
          {:else}
            <ChevronDown class="h-3.5 w-3.5 text-muted-foreground" />
          {/if}
          <span class="h-3 w-[3px] shrink-0 rounded-[1.5px]" style:background={g.color}></span>
          <span class="flex-1 truncate text-[11.5px] font-medium uppercase tracking-[0.05em] text-foreground">
            {g.label}
          </span>
          <span class="font-mono text-[10.5px] tabular-nums text-muted-foreground">
            {g.rows.length}
          </span>
        </button>

        {#if !isCollapsed}
          {#each g.rows as r (r.id)}
        {@const meta = editor.catMeta[r.label] ?? { color: '#9ca3af', label: r.label }}
        {@const isOverlap = editor.overlappingIds.has(r.id)}
        {@const isDup = editor.duplicateIds.has(r.id)}
        <div
          class="flex items-start gap-2 border-b border-border px-3 py-2 text-[12px] transition-colors hover:bg-surface2 data-[selected=true]:bg-surface2"
          data-selected={editor.selected === r.id}
        >
          <button
            type="button"
            class="mt-0.5 h-3.5 w-[3px] shrink-0 rounded-[1.5px]"
            style:background={r.custom ? '#9ca3af' : meta.color}
            onclick={() => (editor.selected = r.id)}
            aria-label="Select box"
          ></button>

          <div class="flex min-w-0 flex-1 flex-col gap-1">
            <input
              type="text"
              class="min-w-0 max-w-full truncate border-none bg-transparent p-0 text-foreground outline-none focus:bg-background focus:px-1 focus:ring-1 focus:ring-primary"
              value={r.text}
              placeholder="(no text)"
              onfocus={() => (editor.selected = r.id)}
              onchange={(e) =>
                editor.setBoxText(r.id, (e.currentTarget as HTMLInputElement).value)}
              title={r.text || '(no text)'}
            />

            <div class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-[10.5px] text-muted-foreground">
              <select
                class="min-w-0 max-w-full truncate rounded-sm border border-border bg-background px-1 py-0.5 text-[10.5px] text-foreground"
                value={r.label}
                onchange={(e) =>
                  editor.setBoxLabel(r.id, (e.currentTarget as HTMLSelectElement).value)}
              >
                {#each categoryKeys as cat}
                  <option value={cat}>{editor.catMeta[cat]?.label ?? cat}</option>
                {/each}
              </select>

              {#if r.confidence !== null}
                <span class="font-mono tabular-nums">
                  {(r.confidence * 100).toFixed(0)}%
                </span>
              {:else}
                <span class="font-mono text-text3">—</span>
              {/if}

              {#if isOverlap}
                <span
                  class="flex items-center gap-0.5 rounded bg-amber-500/10 px-1 py-0.5 text-[9.5px] text-amber-500"
                  title="This box overlaps another visible box"
                >
                  <AlertTriangle class="h-2.5 w-2.5" />
                  overlap
                </span>
              {/if}
              {#if isDup}
                <span
                  class="flex items-center gap-0.5 rounded bg-sky-500/10 px-1 py-0.5 text-[9.5px] text-sky-400"
                  title="Same category + text as another box"
                >
                  <Copy class="h-2.5 w-2.5" />
                  dup
                </span>
              {/if}
            </div>
          </div>

          <button
            type="button"
            class="rounded-md p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
            onclick={() => editor.removeBox(r.id)}
            aria-label="Delete box"
            title="Delete box"
          >
            <Trash2 class="h-3.5 w-3.5" />
          </button>
        </div>
          {/each}
        {/if}
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
