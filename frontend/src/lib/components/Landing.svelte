<script lang="ts">
import { onMount } from 'svelte';
import { Upload } from 'lucide-svelte';
import { toast } from 'svelte-sonner';
import { editor } from '$lib/state.svelte';
import { exampleUrl, fetchExampleAsFile, fetchExamples } from '$lib/api';
import { Card } from '$lib/components/ui/card';

let examples = $state<string[]>([]);
let examplesState = $state<'loading' | 'empty' | 'error' | 'ready'>('loading');
let isDragging = $state(false);

onMount(async () => {
  try {
    examples = await fetchExamples();
    examplesState = examples.length ? 'ready' : 'empty';
  } catch {
    examplesState = 'error';
  }
});

function onDrop(e: DragEvent) {
  e.preventDefault();
  isDragging = false;
  const files = e.dataTransfer?.files;
  if (files && files.length) editor.uploadFiles(Array.from(files));
}

function onFile(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = input.files;
  if (files && files.length) editor.uploadFiles(Array.from(files));
  // Reset so re-selecting the same file still triggers onchange.
  input.value = '';
}

async function loadExample(name: string) {
  try {
    const file = await fetchExampleAsFile(name);
    editor.upload(file);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    toast.error(`could not load example: ${msg}`);
  }
}
</script>

<div class="flex h-screen flex-col overflow-y-auto">
  <!-- App bar -->
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

    <!-- Dropzone -->
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
        onchange={onFile}
      />
      <Upload class="mb-1 h-7 w-7 text-muted-foreground" strokeWidth={1.5} />
      <div class="text-[13.5px] font-medium text-foreground">
        Drop images or a PDF, paste from clipboard, or click to browse
      </div>
      <div class="font-mono text-[11px] text-muted-foreground">
        png · jpg · webp · bmp · tiff · pdf · multi-select supported
      </div>
    </label>

    <!-- Examples -->
    <Card class="overflow-hidden p-0">
      <div
        class="flex items-center justify-between gap-3 border-b border-border px-3 py-2 font-mono text-[10.5px] text-muted-foreground"
      >
        <span class="text-text2">try an example · click to load</span>
        <span>all content is fictitious · mock data for testing only</span>
      </div>
      <div class="flex gap-2 overflow-x-auto p-2.5 [scrollbar-width:thin]">
        {#if examplesState === 'loading'}
          <div class="p-4 font-mono text-[11px] text-muted-foreground">loading examples…</div>
        {:else if examplesState === 'empty'}
          <div class="p-4 font-mono text-[11px] text-muted-foreground">
            drop swedish screenshots into ./example-images/ to preload them here
          </div>
        {:else if examplesState === 'error'}
          <div class="p-4 font-mono text-[11px] text-muted-foreground">
            could not load examples
          </div>
        {:else}
          {#each examples as name, i (name)}
            <button
              type="button"
              class="group relative h-[108px] w-[108px] shrink-0 overflow-hidden rounded-md border border-border bg-surface2 transition-all hover:-translate-y-px hover:border-primary"
              title={`load ${name}`}
              onclick={() => loadExample(name)}
            >
              <span
                class="absolute left-1.5 top-1 z-10 rounded-sm bg-black/55 px-1 py-px font-mono text-[9.5px] tracking-wide text-white"
              >
                {String(i + 1).padStart(2, '0')}
              </span>
              <img
                loading="lazy"
                src={exampleUrl(name, true)}
                alt=""
                class="block h-full w-full object-cover"
              />
            </button>
          {/each}
        {/if}
      </div>
    </Card>
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
