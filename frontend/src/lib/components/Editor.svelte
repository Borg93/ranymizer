<script lang="ts">
import { ChevronLeft, ChevronRight } from 'lucide-svelte';
import { toast } from 'svelte-sonner';
import { editor } from '$lib/state.svelte';
import { Button } from '$lib/components/ui/button';
import Canvas from './Canvas.svelte';
import Sidebar from './Sidebar.svelte';

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
  <header class="flex h-10 shrink-0 items-center gap-3 border-b border-border bg-background px-4">
    <div class="flex items-center gap-2">
      <svg class="h-[18px] w-[18px] text-foreground" viewBox="0 0 20 20" aria-hidden="true">
        <rect x="2" y="4" width="12" height="3" rx="0.5" fill="currentColor" />
        <rect x="2" y="9" width="16" height="3" rx="0.5" fill="currentColor" />
        <rect x="2" y="14" width="8" height="3" rx="0.5" fill="currentColor" />
      </svg>
      <span class="text-[13.5px] font-medium tracking-tight">Ranymizer</span>
    </div>

    <span
      class="rounded-sm border border-border px-1.5 py-px font-mono text-[11px] text-muted-foreground"
    >
      {meta}
    </span>

    {#if editor.hasMultiple}
      <div
        class="ml-1 flex items-center gap-1 rounded-md border border-border bg-card p-0.5"
        title="Switch page (PageUp / PageDown)"
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
        <span class="px-1 font-mono text-[11px] tabular-nums text-foreground">
          {editor.activeIdx + 1} / {editor.pageCount}
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
      </div>
    {/if}

    <div class="flex-1"></div>
    <Button variant="outline" size="sm" onclick={() => editor.reset()}>new image</Button>
  </header>

  {#if editor.error}
    <div
      class="mx-4 mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 font-mono text-xs text-destructive"
    >
      {editor.error}
    </div>
  {/if}

  <div class="flex min-h-0 flex-1 max-md:flex-col">
    <Canvas />
    <Sidebar onDownload={downloadImage} onCopy={copyToClipboard} onExportText={exportText} />
  </div>
</div>
