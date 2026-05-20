<script lang="ts">
import { Upload } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';

let isDragging = $state(false);

function uploadFilesFrom(target: { files: FileList | null | undefined }): void {
  const files = target.files;
  if (!files || !files.length) return;
  editor.uploadFiles(Array.from(files));
}

function onDrop(event: DragEvent): void {
  event.preventDefault();
  isDragging = false;
  uploadFilesFrom({ files: event.dataTransfer?.files });
}

function onFileInput(event: Event): void {
  const input = event.target as HTMLInputElement;
  uploadFilesFrom(input);
  // Reset so re-selecting the same file still triggers onchange.
  input.value = '';
}
</script>

<div class="flex h-screen flex-col overflow-y-auto">
  <header class="flex h-10 shrink-0 items-center gap-3 border-b border-border px-4">
    <div class="flex items-center gap-2">
      <svg class="h-[18px] w-[18px] text-foreground" viewBox="0 0 20 20" aria-hidden="true">
        <rect x="2" y="4" width="12" height="3" rx="0.5" fill="currentColor" />
        <rect x="2" y="9" width="16" height="3" rx="0.5" fill="currentColor" />
        <rect x="2" y="14" width="8" height="3" rx="0.5" fill="currentColor" />
      </svg>
      <span class="text-[13.5px] font-medium tracking-tight">Ranymizer</span>
      <span
        class="ml-1 rounded-sm border border-border px-1.5 py-px font-mono text-[11px] text-muted-foreground"
      >
        v0.1 · prototype · sv
      </span>
    </div>
    <div class="flex-1"></div>
    <div class="font-mono text-[11px] text-muted-foreground">
      <kbd class="rounded border border-border bg-card px-1 py-px text-[10.5px] text-text2">⌘V</kbd>
      paste
      <span class="mx-1.5 opacity-40">·</span>
      <kbd class="rounded border border-border bg-card px-1 py-px text-[10.5px] text-text2">⌘O</kbd>
      open
    </div>
  </header>

  <div class="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-6 pt-14 pb-8">
    <h1
      class="font-serif text-[30px] font-normal leading-[1.15] tracking-tight text-foreground"
    >
      Redact Swedish screenshots before sharing.
    </h1>
    <p class="max-w-[52ch] text-sm text-muted-foreground">
      Drop in images or a PDF. Ranymizer reads the text, marks names, emails, phone numbers,
      addresses, personnummer, organisationsnummer, bank details, dates and URLs, and lets you
      decide what gets blacked out before anything leaves the page.
    </p>

    <label
      class="dropzone relative flex aspect-[3/1] min-h-[140px] cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-border bg-card transition-colors hover:border-primary hover:bg-accent"
      class:dragover={isDragging}
      ondragenter={(e) => {
        e.preventDefault();
        isDragging = true;
      }}
      ondragover={(e) => {
        e.preventDefault();
        isDragging = true;
      }}
      ondragleave={() => (isDragging = false)}
      ondrop={onDrop}
    >
      <input
        type="file"
        accept="application/pdf,image/png,image/jpeg,image/webp,image/bmp,image/tiff"
        multiple
        class="absolute inset-0 cursor-pointer opacity-0"
        onchange={onFileInput}
      />
      <Upload class="mb-1 h-7 w-7 text-muted-foreground" strokeWidth={1.5} />
      <div class="text-[13.5px] font-medium text-foreground">
        Drop images or a PDF, paste from clipboard, or click to browse
      </div>
      <div class="font-mono text-[11px] text-muted-foreground">
        png · jpg · webp · bmp · tiff · pdf · multi-select supported
      </div>
    </label>
  </div>

  <footer
    class="mx-auto mt-1 mb-6 max-w-[720px] px-6 text-[11.5px] leading-snug text-muted-foreground"
  >
    Local-first — your image and the recognised text never leave the page. Showcase uses a Python
    <code class="font-mono">gr.Server</code>; the upcoming desktop build runs OCR + PII fully
    on-device.
    <span class="font-mono text-[10.5px] text-text3"
      >· ocr: paddleocr 3.5 · pii: gliner2</span
    >
  </footer>
</div>
