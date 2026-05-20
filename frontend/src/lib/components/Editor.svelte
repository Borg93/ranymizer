<script lang="ts">
import {
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  Rows3,
  FilePlus2,
  Play,
  Settings2,
  Undo2,
  Redo2,
} from 'lucide-svelte';
import { toast } from 'svelte-sonner';
import { editor } from '$lib/state.svelte';
import { Button } from '$lib/components/ui/button';
import Canvas from './Canvas.svelte';
import Sidebar from './Sidebar.svelte';
import SettingsDrawer from './SettingsDrawer.svelte';
import TextSidebar from './TextSidebar.svelte';
import Thumbnails from './Thumbnails.svelte';

// Editable page-number input — Enter jumps directly to that page.
function onPageInput(e: Event) {
  const t = e.currentTarget as HTMLInputElement;
  const n = parseInt(t.value, 10);
  if (Number.isFinite(n)) editor.goTo(n - 1);
  t.value = String(editor.activeIdx + 1);
}

// Theme toggle — `class="dark"` on <html> is the default (set in app.html).
// We persist the choice in localStorage so it survives reloads.
let theme = $state<'dark' | 'light'>('dark');

$effect(() => {
  const saved = localStorage.getItem('ranymizer-theme');
  if (saved === 'light' || saved === 'dark') theme = saved;
});

$effect(() => {
  const root = document.documentElement;
  root.classList.toggle('dark', theme === 'dark');
  root.classList.toggle('light', theme === 'light');
  localStorage.setItem('ranymizer-theme', theme);
});

function toggleTheme() {
  theme = theme === 'dark' ? 'light' : 'dark';
}

function downloadImage() {
  const c = editor.renderExportCanvas();
  c.toBlob((blob) => {
    if (!blob) return;
    const base = (editor.filename || 'image').replace(/\.[^/.]+$/, '');
    const a = document.createElement('a');
    a.download = `${base}-redacted.png`;
    a.href = URL.createObjectURL(blob);
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    toast.success(`saved ${a.download}`);
  }, 'image/png');
}

async function copyToClipboard() {
  const c = editor.renderExportCanvas();
  try {
    await new Promise<void>((res, rej) => {
      c.toBlob(async (blob) => {
        if (!blob) return rej(new Error('blob failed'));
        try {
          if (!navigator.clipboard || !window.ClipboardItem) {
            return rej(new Error('clipboard api not supported'));
          }
          await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
          res();
        } catch (e) {
          rej(e);
        }
      }, 'image/png');
    });
    toast.success('copied to clipboard');
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    toast.error(`copy failed · ${msg}`);
  }
}

function exportText() {
  const text = editor.renderSanitizedText();
  const blob = new Blob([text], { type: 'text/plain' });
  const base = (editor.filename || 'image').replace(/\.[^/.]+$/, '');
  const a = document.createElement('a');
  a.download = `${base}-redacted.txt`;
  a.href = URL.createObjectURL(blob);
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  toast.success(`saved ${a.download}`);
}

// Hidden file input behind the navbar "Add" button. Appends so existing
// pages stay alongside the newly-uploaded ones.
let addFileInput = $state<HTMLInputElement>();
function onAddFiles(event: Event) {
  const input = event.currentTarget as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  if (files.length > 0) editor.uploadFiles(files, { append: true });
  input.value = '';
}

function onKeyDown(e: KeyboardEvent) {
  const tgt = e.target as HTMLElement | null;
  if (tgt && (tgt.tagName === 'INPUT' || tgt.tagName === 'TEXTAREA')) return;

  const cmd = e.metaKey || e.ctrlKey;
  if (cmd && e.key.toLowerCase() === 's') {
    e.preventDefault();
    downloadImage();
    return;
  }
  if (cmd && e.shiftKey && e.key.toLowerCase() === 'c') {
    e.preventDefault();
    copyToClipboard();
    return;
  }
  if (cmd && e.key.toLowerCase() === 'z') {
    e.preventDefault();
    if (e.shiftKey) editor.redo();
    else editor.undo();
    return;
  }
  if (cmd && e.key.toLowerCase() === 'y') {
    e.preventDefault();
    editor.redo();
    return;
  }

  // Multi-page navigation: PageUp/PageDown, or Cmd/Ctrl + ←/→.
  if (editor.hasMultiple) {
    const goPrev =
      e.key === 'PageUp' ||
      (cmd && e.key === 'ArrowLeft') ||
      (cmd && e.key === 'ArrowUp');
    const goNext =
      e.key === 'PageDown' ||
      (cmd && e.key === 'ArrowRight') ||
      (cmd && e.key === 'ArrowDown');
    if (goPrev) {
      e.preventDefault();
      editor.prev();
      return;
    }
    if (goNext) {
      e.preventDefault();
      editor.next();
      return;
    }
  }

  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (editor.selected !== null) {
      editor.removeSelected();
      e.preventDefault();
    }
  } else if (e.key === 'Escape') {
    editor.selected = null;
    editor.drag = null;
  } else if (e.key === 'v' || e.key === 'V') editor.setMode('select');
  else if (e.key === 'b' || e.key === 'B') editor.setMode('draw');
  else if (e.key === '0') editor.zoomReset();
  else if (e.key === '+' || e.key === '=') editor.zoomStep(1);
  else if (e.key === '-' || e.key === '_') editor.zoomStep(-1);
}

const meta = $derived(editor.img ? `${editor.filename} · ${editor.width}×${editor.height}` : '—');
</script>

<svelte:window onkeydown={onKeyDown} />

<div class="flex h-screen flex-col">
  <header class="grid h-10 shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-3 border-b border-border bg-background px-4">
    <!-- Left: brand + filename -->
    <div class="flex min-w-0 items-center gap-3">
      <div class="flex items-center gap-2">
        <svg class="h-[18px] w-[18px] text-foreground" viewBox="0 0 20 20" aria-hidden="true">
          <rect x="2" y="4" width="12" height="3" rx="0.5" fill="currentColor" />
          <rect x="2" y="9" width="16" height="3" rx="0.5" fill="currentColor" />
          <rect x="2" y="14" width="8" height="3" rx="0.5" fill="currentColor" />
        </svg>
        <span class="text-[13.5px] font-medium tracking-tight">Ranymizer</span>
      </div>

      <span
        class="truncate rounded-sm border border-border px-1.5 py-px font-mono text-[11px] text-muted-foreground"
      >
        {meta}
      </span>
    </div>

    <!-- Center: pagination (visually centered in the nav bar) -->
    <div class="flex justify-center">
      {#if editor.hasMultiple}
        <div
          class="flex items-center gap-1 rounded-md border border-border bg-card p-0.5"
          title="Switch page (PageUp / PageDown). Type a number to jump."
        >
          <Button
            variant="ghost"
            size="sm"
            class="h-6 w-6 p-0"
            disabled={editor.activeIdx === 0}
            onclick={() => editor.prev()}
            aria-label="Previous page"
          >
            <ChevronLeft class="h-3.5 w-3.5" />
          </Button>
          <input
            type="number"
            min="1"
            max={editor.pageCount}
            value={editor.activeIdx + 1}
            onchange={onPageInput}
            onkeydown={(e) => {
              if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur();
            }}
            class="h-5 w-9 rounded-sm border border-transparent bg-transparent px-1 text-center font-mono text-[11px] tabular-nums text-foreground focus:border-border focus:bg-background focus:outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            aria-label="Page number"
          />
          <span class="px-0.5 font-mono text-[11px] tabular-nums text-muted-foreground">
            / {editor.pageCount}
          </span>
          <Button
            variant="ghost"
            size="sm"
            class="h-6 w-6 p-0"
            disabled={editor.activeIdx === editor.pageCount - 1}
            onclick={() => editor.next()}
            aria-label="Next page"
          >
            <ChevronRight class="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            class="ml-0.5 h-6 w-6 p-0 data-[active=true]:bg-accent"
            data-active={editor.showThumbnails}
            onclick={() => (editor.showThumbnails = !editor.showThumbnails)}
            aria-label="Toggle thumbnails"
            title={editor.showThumbnails ? 'Hide thumbnails' : 'Show thumbnails'}
          >
            <Rows3 class="h-3.5 w-3.5" />
          </Button>
        </div>
      {/if}
    </div>

    <!-- Right: actions -->
    <div class="flex items-center justify-end gap-1.5">
      <input
        bind:this={addFileInput}
        type="file"
        class="hidden"
        accept="image/*,application/pdf"
        multiple
        onchange={onAddFiles}
      />
      <Button
        variant="secondary"
        size="sm"
        class="h-7 gap-1.5 border border-border px-2 text-foreground"
        onclick={() => addFileInput?.click()}
        title={editor.hasImage ? 'Append another image or PDF' : 'Upload an image or PDF'}
      >
        <FilePlus2 class="h-3.5 w-3.5" />
        <span class="text-[12px] font-medium tracking-tight">Add</span>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        class="h-7 w-7 p-0"
        disabled={!editor.canUndo}
        onclick={() => editor.undo()}
        aria-label="Undo"
        title="Undo (⌘Z)"
      >
        <Undo2 class="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        class="h-7 w-7 p-0"
        disabled={!editor.canRedo}
        onclick={() => editor.redo()}
        aria-label="Redo"
        title="Redo (⌘⇧Z)"
      >
        <Redo2 class="h-3.5 w-3.5" />
      </Button>

      <Button
        variant="default"
        size="sm"
        class="h-7 gap-1.5 px-2"
        disabled={!editor.hasImage || editor.loading}
        onclick={() => editor.run()}
        title="Run the pipeline on all pages with the current settings"
      >
        <Play class="h-3.5 w-3.5" />
        <span class="text-[12px] font-medium tracking-tight">Run</span>
      </Button>

      <Button
        variant="secondary"
        size="sm"
        class="h-7 w-7 border border-border p-0 text-foreground"
        onclick={() => (editor.settingsOpen = !editor.settingsOpen)}
        aria-label="Pipeline settings"
        title="Pipeline settings"
      >
        <Settings2 class="h-3.5 w-3.5" />
      </Button>

      <Button
        variant="secondary"
        size="sm"
        class="h-7 w-7 border border-border p-0 text-foreground"
        onclick={toggleTheme}
        aria-label="Toggle theme"
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {#if theme === 'dark'}
          <Sun class="h-3.5 w-3.5" />
        {:else}
          <Moon class="h-3.5 w-3.5" />
        {/if}
      </Button>
    </div>
  </header>

  {#if editor.error}
    <div
      class="mx-4 mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 font-mono text-xs text-destructive"
    >
      {editor.error}
    </div>
  {/if}

  <div class="flex min-h-0 flex-1 max-md:flex-col">
    {#if editor.hasImage}
      <TextSidebar />
    {/if}
    <!-- Canvas column owns its own footer (thumbnails) so the sidebars stay
         full-height and aren't pushed up by the carousel. -->
    <div class="flex min-h-0 min-w-0 flex-1 flex-col">
      <Canvas />
      {#if editor.hasMultiple && editor.showThumbnails}
        <Thumbnails />
      {/if}
    </div>
    {#if editor.hasImage}
      <Sidebar onDownload={downloadImage} onCopy={copyToClipboard} onExportText={exportText} />
    {/if}
  </div>
</div>

<SettingsDrawer />
