<script lang="ts">
import { Loader2, Maximize2, Upload, ZoomIn, ZoomOut } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
import { Button } from '$lib/components/ui/button';
import { Separator } from '$lib/components/ui/separator';
import type { EditorBox } from '$lib/types';

// Imperative ref, read by the pointer handlers. Elements are never proxied.
let wrapEl = $state<HTMLDivElement>();
let scrollEl: HTMLDivElement | undefined;

// Pan state — spacebar or middle-mouse drags the scroll container.
let spaceDown = $state(false);
let panState = $state<{
  startX: number;
  startY: number;
  scrollLeft: number;
  scrollTop: number;
} | null>(null);

function fitToContainer() {
  if (scrollEl && editor.img) editor.zoomFit(scrollEl.clientWidth, scrollEl.clientHeight);
}

// Re-fit whenever a new image (or page) loads. Using filename + dimensions
// as the trigger because img is an HTMLImageElement that may be reused.
$effect(() => {
  if (!editor.img || !scrollEl) return;
  // Read these so the effect re-runs when the active page changes.
  void editor.filename;
  void editor.width;
  void editor.height;
  requestAnimationFrame(() => {
    if (scrollEl) editor.zoomFit(scrollEl.clientWidth, scrollEl.clientHeight);
  });
});

// When the selection changes (e.g. via the left sidebar row click), scroll
// the canvas so the selected box ends up roughly centred in the viewport.
$effect(() => {
  const sel = editor.selectedBox;
  if (!sel || !scrollEl) return;
  const cx = (sel.x + sel.w / 2) * editor.scale;
  const cy = (sel.y + sel.h / 2) * editor.scale;
  scrollEl.scrollTo({
    left: cx - scrollEl.clientWidth / 2,
    top: cy - scrollEl.clientHeight / 2,
    behavior: 'smooth',
  });
});

function cssVar(name: string): string {
  if (typeof document === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Canvas painting: outer runs once (grab the context), nested $effect
// re-runs on the reactive state it reads.
function paint(node: Element) {
  const canvas = node as HTMLCanvasElement;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  $effect(() => {
    if (!editor.img) return;

    canvas.width = editor.width;
    canvas.height = editor.height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(editor.img, 0, 0);

    // OCR detection overlay (toggle in the sidebar). Drawn before PII masks
    // so the black bars cleanly cover the lines they pass through.
    if (editor.showOcrLines && editor.ocrLines.length > 0) {
      ctx.save();
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.85)';
      ctx.lineWidth = Math.max(1, 1 / editor.scale);
      for (const ln of editor.ocrLines) {
        ctx.strokeRect(ln.x + 0.5, ln.y + 0.5, ln.w, ln.h);
      }
      ctx.restore();
    }

    if (editor.showCategoryColors) {
      // Preview — translucent fill so the underlying image stays partly
      // visible. Either per-category colour or a unified swatch colour.
      ctx.save();
      ctx.globalAlpha = editor.maskAlpha;
      const usePerCategory = editor.colorMaskMode === 'per-category';
      for (const b of editor.boxes) {
        if (!editor.isVisible(b)) continue;
        if (usePerCategory) {
          ctx.fillStyle = b.custom ? '#9ca3af' : (editor.catMeta[b.label]?.color ?? '#9ca3af');
        } else {
          ctx.fillStyle = editor.maskColor;
        }
        ctx.fillRect(b.x, b.y, b.w, b.h);
      }
      ctx.restore();
    } else {
      ctx.fillStyle = editor.maskColor;
      for (const b of editor.boxes) {
        if (!editor.isVisible(b)) continue;
        ctx.fillRect(b.x, b.y, b.w, b.h);
      }
    }

    // Overlap warning — solid amber stroke on any visible box that shares
    // area with another. Drawn after masks so it sits on top of black bars.
    if (editor.overlappingIds.size > 0) {
      ctx.save();
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = Math.max(1.5, 2 / editor.scale);
      for (const b of editor.boxes) {
        if (!editor.isVisible(b)) continue;
        if (!editor.overlappingIds.has(b.id)) continue;
        ctx.strokeRect(b.x + 0.5, b.y + 0.5, b.w, b.h);
      }
      ctx.restore();
    }

    if (editor.selectedIds.size > 0) {
      ctx.save();
      const primary = cssVar('--primary') || '#818cf8';
      ctx.shadowColor = primary;
      ctx.shadowBlur = 12 / editor.scale;
      ctx.strokeStyle = primary;
      ctx.lineWidth = Math.max(2, 2.5 / editor.scale);
      for (const b of editor.boxes) {
        if (!editor.selectedIds.has(b.id)) continue;
        ctx.strokeRect(b.x - 1, b.y - 1, b.w + 2, b.h + 2);
      }
      ctx.shadowBlur = 0;
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = Math.max(1, 1 / editor.scale);
      ctx.setLineDash([4 / editor.scale, 3 / editor.scale]);
      for (const b of editor.boxes) {
        if (!editor.selectedIds.has(b.id)) continue;
        ctx.strokeRect(b.x, b.y, b.w, b.h);
      }
      ctx.restore();
    }

    if (editor.drag?.type === 'draw') {
      const b = editor.drag.newBox;
      ctx.save();
      ctx.fillStyle = 'rgba(0,0,0,.7)';
      ctx.fillRect(b.x, b.y, b.w, b.h);
      ctx.strokeStyle = cssVar('--primary') || '#818cf8';
      ctx.lineWidth = Math.max(1, 1 / editor.scale);
      ctx.strokeRect(b.x, b.y, b.w, b.h);
      ctx.restore();
    }
  });
}

// Capture the scroll container and zoom-to-fit once it is laid out.
function setupScroll(node: Element) {
  const el = node as HTMLDivElement;
  scrollEl = el;
  const id = requestAnimationFrame(() => {
    if (editor.img) editor.zoomFit(el.clientWidth, el.clientHeight);
  });
  return () => {
    cancelAnimationFrame(id);
    scrollEl = undefined;
  };
}

function canvasXY(ev: MouseEvent) {
  if (!wrapEl) return { x: 0, y: 0 };
  const rect = wrapEl.getBoundingClientRect();
  return {
    x: (ev.clientX - rect.left) / editor.scale,
    y: (ev.clientY - rect.top) / editor.scale,
  };
}

function hitTest(x: number, y: number): EditorBox | null {
  for (let i = editor.boxes.length - 1; i >= 0; i--) {
    const b = editor.boxes[i];
    if (!editor.isVisible(b)) continue;
    if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) return b;
  }
  return null;
}

function startPan(ev: MouseEvent) {
  if (!scrollEl) return;
  ev.preventDefault();
  panState = {
    startX: ev.clientX,
    startY: ev.clientY,
    scrollLeft: scrollEl.scrollLeft,
    scrollTop: scrollEl.scrollTop,
  };
}

function onMouseDown(ev: MouseEvent) {
  // Pan modes: right button, middle button, or left button while space is held.
  if (ev.button === 1 || ev.button === 2 || (ev.button === 0 && spaceDown)) {
    startPan(ev);
    return;
  }
  if (ev.button !== 0) return;
  ev.preventDefault();
  const { x, y } = canvasXY(ev);
  const hit = hitTest(x, y);

  if (editor.mode === 'draw' && !hit) {
    editor.clearSelection();
    editor.drag = {
      type: 'draw',
      startX: x,
      startY: y,
      newBox: { x, y, w: 0, h: 0, label: 'custom', text: '' },
    };
  } else if (hit) {
    editor.selectOnly(hit.id);
    editor.beginMove();
    editor.drag = {
      type: 'move',
      startX: x,
      startY: y,
      origBox: { x: hit.x, y: hit.y, w: hit.w, h: hit.h },
      boxId: hit.id,
    };
  } else {
    editor.clearSelection();
    editor.drag = null;
  }
}

function onMouseMove(ev: MouseEvent) {
  if (panState && scrollEl) {
    scrollEl.scrollLeft = panState.scrollLeft - (ev.clientX - panState.startX);
    scrollEl.scrollTop = panState.scrollTop - (ev.clientY - panState.startY);
    return;
  }
  if (!wrapEl) return;
  const rect = wrapEl.getBoundingClientRect();
  const inside =
    ev.clientX >= rect.left &&
    ev.clientX <= rect.right &&
    ev.clientY >= rect.top &&
    ev.clientY <= rect.bottom;
  if (inside) {
    editor.cursor = {
      x: Math.round((ev.clientX - rect.left) / editor.scale),
      y: Math.round((ev.clientY - rect.top) / editor.scale),
    };
  }

  if (!editor.drag) return;
  const { x, y } = canvasXY(ev);

  if (editor.drag.type === 'draw') {
    const sx = editor.drag.startX;
    const sy = editor.drag.startY;
    editor.drag = {
      ...editor.drag,
      newBox: {
        x: Math.max(0, Math.min(editor.width, Math.min(sx, x))),
        y: Math.max(0, Math.min(editor.height, Math.min(sy, y))),
        w: Math.min(Math.abs(x - sx), editor.width),
        h: Math.min(Math.abs(y - sy), editor.height),
        label: 'custom',
        text: '',
      },
    };
  } else if (editor.drag.type === 'move') {
    const dx = x - editor.drag.startX;
    const dy = y - editor.drag.startY;
    const o = editor.drag.origBox;
    editor.moveBox(editor.drag.boxId, o.x + dx, o.y + dy);
  }
}

function onMouseUp() {
  if (panState) {
    panState = null;
    return;
  }
  if (!editor.drag) return;
  if (editor.drag.type === 'draw') {
    const b = editor.drag.newBox;
    if (b.w > 3 && b.h > 3) editor.addCustomBox(b.x, b.y, b.w, b.h);
  }
  editor.drag = null;
}

function onKeyDown(ev: KeyboardEvent) {
  if (ev.code !== 'Space' || ev.repeat) return;
  const t = ev.target as HTMLElement | null;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
  ev.preventDefault();
  spaceDown = true;
}

// Ctrl/Cmd + wheel zooms smoothly; plain wheel falls through to scrolling.
// Multiplier per pixel of deltaY — small enough that trackpad pinch-zoom
// (which emits many tiny events with ctrlKey set) feels continuous, not jumpy.
function onWheel(ev: WheelEvent) {
  if (!(ev.ctrlKey || ev.metaKey)) return;
  ev.preventDefault();
  const factor = Math.exp(-ev.deltaY * 0.0015);
  editor.zoomBy(factor);
}

function onKeyUp(ev: KeyboardEvent) {
  if (ev.code === 'Space') spaceDown = false;
}

const overBox = $derived.by(() => {
  if (editor.mode !== 'select' || !editor.cursor) return false;
  return hitTest(editor.cursor.x, editor.cursor.y) !== null;
});

// Empty-state dropzone (shown only when no pages have been uploaded yet).
let dropzoneDragging = $state(false);
function onDropzoneDrop(event: DragEvent) {
  event.preventDefault();
  dropzoneDragging = false;
  const files = event.dataTransfer?.files;
  if (files && files.length) editor.uploadFiles(Array.from(files));
}
function onDropzoneFiles(event: Event) {
  const input = event.currentTarget as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  if (files.length) editor.uploadFiles(files);
  input.value = '';
}

const cursorClass = $derived.by(() => {
  if (panState) return 'cursor-grabbing';
  if (spaceDown) return 'cursor-grab';
  if (editor.mode === 'draw') return 'cursor-crosshair';
  if (editor.drag?.type === 'move') return 'cursor-grabbing';
  if (overBox) return 'cursor-move';
  return 'cursor-default';
});
</script>

<svelte:window
  onmousemove={onMouseMove}
  onmouseup={onMouseUp}
  onresize={fitToContainer}
  onkeydown={onKeyDown}
  onkeyup={onKeyUp}
/>

<div class="relative flex min-h-0 min-w-0 flex-1 flex-col bg-background">
  {#if editor.loading && editor.hasImage}
    <!-- Canvas-scoped loading overlay so the sidebars + navbar stay
         interactive. The initial-load uses the full-screen Loading
         component instead. -->
    <div
      class="pointer-events-none absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-background/55 backdrop-blur-[2px]"
    >
      <Loader2 class="h-5 w-5 animate-spin text-primary" />
      <span class="font-mono text-[11px] tracking-wide text-muted-foreground">
        {editor.loadingMessage || 'running pipeline…'}
      </span>
    </div>
  {/if}

  <div
    class="canvas-scroll relative flex-1 overflow-auto"
    onwheel={onWheel}
    {@attach setupScroll}
  >
    <div class="relative flex min-h-full min-w-full items-center justify-center p-7">
      {#if editor.hasImage}
        <div
          class="relative shrink-0 {cursorClass}"
          bind:this={wrapEl}
          onmousedown={onMouseDown}
          oncontextmenu={(e) => e.preventDefault()}
          role="presentation"
        >
          <canvas
            class="block"
            style:width="{editor.width * editor.scale}px"
            style:height="{editor.height * editor.scale}px"
            {@attach paint}
          ></canvas>
        </div>
      {:else}
        <label
          class="dropzone-empty flex aspect-[3/1] w-full max-w-[640px] cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-card transition-colors hover:border-primary hover:bg-accent"
          class:dragover={dropzoneDragging}
          ondragenter={(e) => {
            e.preventDefault();
            dropzoneDragging = true;
          }}
          ondragover={(e) => {
            e.preventDefault();
            dropzoneDragging = true;
          }}
          ondragleave={() => (dropzoneDragging = false)}
          ondrop={onDropzoneDrop}
        >
          <input
            type="file"
            accept="application/pdf,image/png,image/jpeg,image/webp,image/bmp,image/tiff"
            multiple
            class="absolute inset-0 cursor-pointer opacity-0"
            onchange={onDropzoneFiles}
          />
          <Upload class="h-7 w-7 text-muted-foreground" strokeWidth={1.5} />
          <div class="text-[13.5px] font-medium text-foreground">
            Drop images or a PDF, paste, or click to browse
          </div>
          <div class="font-mono text-[11px] text-muted-foreground">
            png · jpg · webp · bmp · tiff · pdf · ⌘V also works
          </div>
        </label>
      {/if}
    </div>
  </div>

  <!-- Zoom toolbar -->
  <div
    class="absolute bottom-10 right-3.5 z-10 flex items-center rounded-md border border-border bg-card p-0.5 shadow-sm"
  >
    <Button variant="ghost" size="sm" class="h-7 px-2" onclick={() => editor.zoomStep(-1)}>
      <ZoomOut class="h-3.5 w-3.5" />
    </Button>
    <Separator orientation="vertical" class="mx-px h-5" />
    <span class="px-2 font-mono text-[11px] text-foreground">
      {Math.round(editor.scale * 100)}%
    </span>
    <Separator orientation="vertical" class="mx-px h-5" />
    <Button variant="ghost" size="sm" class="h-7 px-2" onclick={() => editor.zoomStep(1)}>
      <ZoomIn class="h-3.5 w-3.5" />
    </Button>
    <Separator orientation="vertical" class="mx-px h-5" />
    <Button
      variant="ghost"
      size="sm"
      class="h-7 px-2 font-mono text-[11px]"
      onclick={fitToContainer}
    >
      <Maximize2 class="mr-1 h-3 w-3" />
      fit
    </Button>
    <Button
      variant="ghost"
      size="sm"
      class="h-7 px-2 font-mono text-[11px]"
      onclick={() => editor.zoomReset()}
    >
      1:1
    </Button>
  </div>

  <!-- Status bar -->
  <div
    class="flex h-[26px] shrink-0 items-center gap-3 border-t border-border bg-card px-3 font-mono text-[11px] text-text3"
  >
    <span>zoom</span>
    <span class="text-muted-foreground">{Math.round(editor.scale * 100)}%</span>
    <span class="opacity-40">·</span>
    <span>cursor</span>
    <span class="text-muted-foreground">
      {editor.cursor ? `${editor.cursor.x}, ${editor.cursor.y}` : '—'}
    </span>
    <span class="opacity-40">·</span>
    <span>selection</span>
    <span class="text-muted-foreground">
      {editor.selectedBox ? `${editor.selectedBox.w}×${editor.selectedBox.h}` : '—'}
    </span>
    <span class="flex-1"></span>
    <span>{editor.mode}</span>
  </div>
</div>

<style>
  /* Checkerboard behind the canvas. */
  .canvas-scroll {
    background:
      linear-gradient(45deg, var(--surface2) 25%, transparent 25%),
      linear-gradient(-45deg, var(--surface2) 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, var(--surface2) 75%),
      linear-gradient(-45deg, transparent 75%, var(--surface2) 75%);
    background-color: var(--background);
    background-size: 16px 16px;
    background-position: 0 0, 0 8px, 8px -8px, 8px 0;
  }
</style>
