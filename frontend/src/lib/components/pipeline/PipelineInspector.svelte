<script lang="ts">
/**
 * Right-side properties panel. Shows the full settings form for whichever
 * node is currently selected in the SvelteFlow graph. Mirror of Figma's
 * right panel — nodes stay light, the inspector carries the noisy forms.
 */
import * as v from 'valibot';
import { Copy, FileJson, Plus, Settings2, Trash2, Upload, X } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
import { CustomLabelKeySchema } from '$lib/pipelineConfig.schema';
import {
  DEFAULT_LABEL_DESCRIPTIONS,
  DEFAULT_LABEL_RULES,
  DEFAULT_PII_LABELS,
  EMPTY_LABEL_RULE,
} from '$lib/types';
import LabelRuleCard from '../LabelRuleCard.svelte';
import ResizeHandle from '../ResizeHandle.svelte';

type Props = { selectedId: string | null };
let { selectedId }: Props = $props();

/** Last-run response for the active page — surfaced by the `output` node
 *  debug view. Defined as a derived snapshot so it tracks page switches
 *  without copying. */
const lastResponse = $derived({
  filename: editor.pages[editor.activeIdx]?.filename ?? null,
  width: editor.pages[editor.activeIdx]?.width ?? 0,
  height: editor.pages[editor.activeIdx]?.height ?? 0,
  spans: editor.spans,
  boxes: editor.boxes,
  ocrLines: editor.ocrLines,
});

let copyState = $state<'idle' | 'copied'>('idle');
async function copyResponseJson(): Promise<void> {
  try {
    await navigator.clipboard.writeText(JSON.stringify(lastResponse, null, 2));
    copyState = 'copied';
    setTimeout(() => (copyState = 'idle'), 1200);
  } catch {
    /* clipboard may be blocked in some browsers/contexts — ignore */
  }
}

// ── Image input node ───────────────────────────────────────────────
// Drop-zone + file picker reuses `editor.uploadFiles`. Replace clears
// the current set; Append adds to it (same flag the navbar uses).
let inputDragging = $state(false);
let appendMode = $state(true);

function onInputDrop(event: DragEvent): void {
  event.preventDefault();
  inputDragging = false;
  const files = event.dataTransfer?.files;
  if (files && files.length) editor.uploadFiles(Array.from(files), { append: appendMode });
}

function onInputPick(event: Event): void {
  const target = event.currentTarget as HTMLInputElement;
  const files = target.files ? Array.from(target.files) : [];
  if (files.length) editor.uploadFiles(files, { append: appendMode });
  target.value = '';
}

/** Repaint a thumbnail when the underlying page snapshot moves. Same
 *  pattern as Thumbnails.svelte — kept local because both components have
 *  different sizing and we don't want one to drag the other's dependencies. */
function paintThumbnail(canvas: HTMLCanvasElement, pageIdx: number): void {
  $effect(() => {
    void editor.activeIdx;
    void editor.maskColor;
    if (pageIdx === editor.activeIdx) {
      void editor.boxes;
    } else {
      void editor.pages[pageIdx]?.boxes;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const rendered = editor.renderThumbnailCanvas(pageIdx, 240);
    if (!rendered) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    canvas.width = rendered.width;
    canvas.height = rendered.height;
    ctx.drawImage(rendered, 0, 0);
  });
}

// Resizable — same drag handle UX as the editor's left text panel and right
// tool sidebar. State lives here; drag mechanics + CSS in <ResizeHandle>.
let width = $state(480);

/** Per-label realistic sample for the regex preview chip. */
const SAMPLES: Record<string, string> = {
  person: 'Sven Andersson',
  email: 'sven.andersson@exempel.se',
  phone_number: '+46 70-123 45 67',
  address: 'Sveavägen 12, 113 57 Stockholm',
  date_of_birth: '1985-03-15',
  personnummer: '850315-2384',
  organisationsnummer: '556677-1234',
  bank_account: '5050-1055',
  iban: 'SE3550000000054910000003',
  card_number: '4111 1111 1111 1111',
  url: 'https://ranymizer.dev',
  ip_address: '192.168.1.1',
  username: 'sven_a',
};

function persist(): void {
  editor.persistPipelineConfig();
}

// — PaddleOCR controls —
const paddle = $derived(editor.pipelineConfig.paddleocr);

// — GLiNER2 controls —
const gliner = $derived(editor.pipelineConfig.gliner);
const enabledSet = $derived(new Set(gliner.enabledLabels));
const customKeys = $derived(Object.keys(gliner.customLabels));
const allLabelKeys = $derived([...DEFAULT_PII_LABELS, ...customKeys]);

function toggleLabel(label: string): void {
  const enabled = new Set(gliner.enabledLabels);
  if (enabled.has(label)) enabled.delete(label);
  else enabled.add(label);
  gliner.enabledLabels = [...enabled];
  persist();
}

let editingRuleFor = $state<string | null>(null);

function startCustomising(label: string): void {
  const def = DEFAULT_LABEL_RULES[label] ?? EMPTY_LABEL_RULE;
  gliner.rules = { ...gliner.rules, [label]: { ...def } };
  if (gliner.descriptions[label] === undefined) {
    gliner.descriptions = {
      ...gliner.descriptions,
      [label]: (DEFAULT_LABEL_DESCRIPTIONS[label] ?? '') + ' ',
    };
  }
  editingRuleFor = label;
  persist();
}

function isCustomised(label: string): boolean {
  const r = gliner.rules[label];
  if (r) {
    const def = DEFAULT_LABEL_RULES[label] ?? EMPTY_LABEL_RULE;
    if (
      r.regex !== def.regex ||
      r.regexMode !== def.regexMode ||
      r.threshold !== def.threshold ||
      r.validateLuhn !== def.validateLuhn
    ) {
      return true;
    }
  }
  const d = gliner.descriptions[label];
  return d !== undefined && d !== DEFAULT_LABEL_DESCRIPTIONS[label];
}

const customisedLabels = $derived(allLabelKeys.filter(isCustomised));

// — Custom label add form —
let newKey = $state('');
let newName = $state('');
let newDesc = $state('');
let newColor = $state('#a855f7');
let addError = $state<string | null>(null);

function addCustom(): void {
  addError = null;
  const slug = newKey.trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
  const parsed = v.safeParse(CustomLabelKeySchema, slug);
  if (!parsed.success) {
    addError = parsed.issues[0]?.message ?? 'Invalid key';
    return;
  }
  const key = parsed.output;
  if ((DEFAULT_PII_LABELS as readonly string[]).includes(key) || gliner.customLabels[key]) {
    addError = `"${key}" already exists`;
    return;
  }
  gliner.customLabels = {
    ...gliner.customLabels,
    [key]: {
      displayLabel: newName.trim() || key,
      color: newColor,
      description: newDesc.trim() || `User-defined label "${key}"`,
    },
  };
  gliner.descriptions = {
    ...gliner.descriptions,
    [key]: newDesc.trim() || `User-defined label "${key}"`,
  };
  if (!gliner.enabledLabels.includes(key)) {
    gliner.enabledLabels = [...gliner.enabledLabels, key];
  }
  persist();
  newKey = '';
  newName = '';
  newDesc = '';
}

function removeCustom(key: string): void {
  const { [key]: _drop, ...rest } = gliner.customLabels;
  gliner.customLabels = rest;
  gliner.enabledLabels = gliner.enabledLabels.filter((l) => l !== key);
  const { [key]: _d2, ...descRest } = gliner.descriptions;
  gliner.descriptions = descRest;
  const { [key]: _d3, ...ruleRest } = gliner.rules;
  gliner.rules = ruleRest;
  if (editingRuleFor === key) editingRuleFor = null;
  persist();
}

const inputCls =
  'min-w-0 w-full rounded-sm border border-border bg-background px-2 py-1 text-[12px] text-foreground outline-none focus:border-primary';
</script>

<aside
  class="relative flex h-full shrink-0 flex-col overflow-hidden border-l border-border bg-card"
  style:width="{width}px"
>
  <ResizeHandle side="left" bind:width min={320} max={720} />
  {#if !selectedId}
    <div class="flex flex-1 items-center justify-center px-6 text-center text-[11.5px] leading-relaxed text-muted-foreground">
      Click a node in the graph to edit its settings here.
    </div>
  {:else if selectedId === 'paddle'}
    <header class="border-b border-border px-4 py-3">
      <div class="text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">Node</div>
      <div class="text-[13.5px] font-semibold text-foreground">PaddleOCR</div>
      <div class="font-mono text-[10.5px] text-muted-foreground">text detection + recognition</div>
    </header>
    <div class="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
      <label class="flex flex-col gap-1 text-[11px] text-muted-foreground">
        <div class="flex items-center justify-between">
          <span class="text-foreground">Layout threshold</span>
          <span class="font-mono tabular-nums text-foreground">
            {paddle.layoutThreshold.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min="0.1"
          max="0.95"
          step="0.05"
          value={paddle.layoutThreshold}
          oninput={(e) => {
            paddle.layoutThreshold = Number((e.currentTarget as HTMLInputElement).value);
            persist();
          }}
          class="accent-primary"
        />
        <span class="text-[10.5px] text-text3">
          Minimum confidence per region. Lower = more (noisy) boxes; higher = stricter.
        </span>
      </label>

      <div class="flex flex-col gap-1">
        <div class="text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
          Preprocessing
        </div>
        <div class="flex flex-col gap-1.5">
          {#each [
            ['useDocOrientationClassify', 'Orient classify', 'Detect 0/90/180/270° and rotate upright.'],
            ['useDocUnwarping', 'Doc unwarp', 'Flatten curved / perspective scans (slow).'],
            ['useTextlineOrientation', 'Textline orient', 'Per-line rotation; catches vertical labels.'],
            ['useChartRecognition', 'Chart recog.', 'Branch for plots/diagrams. Off for plain text.'],
            ['useSealRecognition', 'Seal recog.', 'Round/oval seal text (bolagsstämpel, notary).'],
            ['useOcrForImageBlock', 'OCR in image blocks', 'Run OCR inside layout-detected image regions.'],
          ] as [key, label, hint] (key)}
            {@const k = key as keyof typeof paddle}
            <label class="flex flex-col gap-0.5 rounded-md border border-border bg-background/40 px-2 py-1.5">
              <span class="flex items-center gap-2 text-[12px] text-foreground">
                <input
                  type="checkbox"
                  class="accent-primary"
                  checked={paddle[k] as boolean}
                  onchange={() => {
                    paddle[k] = !paddle[k] as never;
                    persist();
                  }}
                />
                <span class="flex-1">{label}</span>
              </span>
              <span class="ml-6 text-[10px] text-text3">{hint}</span>
            </label>
          {/each}
        </div>
      </div>

      <!-- Last OCR output — text + line count from the most recent Run. -->
      <details class="rounded border border-border" open={editor.sourceText.length > 0}>
        <summary class="cursor-pointer list-none px-2.5 py-1.5 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3 hover:text-foreground">
          Last OCR output
          <span class="ml-1 font-mono tabular-nums text-muted-foreground">
            ({editor.sourceText.length} chars · {editor.ocrLines.length} lines)
          </span>
        </summary>
        {#if editor.sourceText.length === 0}
          <div class="border-t border-border px-2.5 py-2 text-[10.5px] text-muted-foreground">
            Press Run to populate this.
          </div>
        {:else}
          <pre class="m-0 max-h-48 overflow-auto border-t border-border bg-background/40 px-2.5 py-2 font-mono text-[10.5px] leading-snug text-foreground whitespace-pre-wrap">{editor.sourceText}</pre>
        {/if}
      </details>
    </div>
  {:else if selectedId === 'gliner'}
    <header class="border-b border-border px-4 py-3">
      <div class="text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">Node</div>
      <div class="text-[13.5px] font-semibold text-foreground">GLiNER2 — PII detection</div>
      <div class="font-mono text-[10.5px] text-muted-foreground">
        thresh {gliner.threshold.toFixed(2)} · {gliner.enabledLabels.length} labels
      </div>
    </header>
    <div class="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
      <!-- Model + threshold -->
      <div class="grid grid-cols-[2fr_1fr] gap-2">
        <label class="flex flex-col gap-1 text-[11px] text-muted-foreground">
          <span class="text-foreground">Model</span>
          <input
            type="text"
            class={inputCls}
            value={gliner.modelName}
            oninput={(e) => {
              gliner.modelName = (e.currentTarget as HTMLInputElement).value;
              persist();
            }}
          />
        </label>
        <label class="flex flex-col gap-1 text-[11px] text-muted-foreground">
          <div class="flex items-center justify-between">
            <span class="text-foreground">Threshold</span>
            <span class="font-mono tabular-nums text-foreground">{gliner.threshold.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min="0.1"
            max="0.95"
            step="0.05"
            value={gliner.threshold}
            oninput={(e) => {
              gliner.threshold = Number((e.currentTarget as HTMLInputElement).value);
              persist();
            }}
            class="accent-primary"
          />
        </label>
      </div>

      <!-- Labels grid -->
      <div>
        <div class="mb-1.5 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
          Active labels
        </div>
        <div class="grid max-h-[180px] grid-cols-1 gap-0.5 overflow-y-auto pr-1 sm:grid-cols-2">
          {#each allLabelKeys as label (label)}
            {@const isOn = enabledSet.has(label)}
            {@const meta = editor.catMeta[label] ?? { color: '#888', label: label }}
            <div
              class="flex items-center gap-1 rounded-sm px-1 py-0.5 text-left transition-colors hover:bg-surface2 data-[active=false]:opacity-40"
              data-active={isOn}
            >
              <button
                type="button"
                class="flex flex-1 items-center gap-1.5 truncate text-left"
                onclick={() => toggleLabel(label)}
                aria-pressed={isOn}
              >
                <span
                  class="h-2.5 w-[2px] shrink-0 rounded-[1px]"
                  style:background={meta.color}
                ></span>
                <span class="flex-1 truncate text-[11px] text-foreground">{meta.label}</span>
              </button>
              <button
                type="button"
                class="rounded-sm p-0.5 text-text3 hover:bg-primary/10 hover:text-foreground data-[on=true]:text-primary"
                data-on={editingRuleFor === label}
                onclick={() => {
                  if (editingRuleFor === label) editingRuleFor = null;
                  else if (!isCustomised(label)) startCustomising(label);
                  else editingRuleFor = label;
                }}
                title="Edit rule (regex / threshold / Luhn)"
                aria-label="Edit rule"
              >
                <Settings2 class="h-3 w-3" />
              </button>
              {#if customKeys.includes(label)}
                <button
                  type="button"
                  class="rounded-sm p-0.5 text-text3 hover:bg-destructive/10 hover:text-destructive"
                  onclick={() => removeCustom(label)}
                  title="Delete custom label"
                  aria-label="Delete custom label"
                >
                  <Trash2 class="h-3 w-3" />
                </button>
              {/if}
            </div>
          {/each}
        </div>
      </div>

      <!-- Inline rule editor -->
      {#if editingRuleFor}
        <div class="rounded-md border border-primary bg-background/40 p-2">
          <div class="mb-1.5 flex items-center gap-2">
            <span class="font-mono text-[10px] uppercase tracking-[0.08em] text-text3">Rule for</span>
            <span class="text-[11.5px] font-medium text-foreground">
              {editor.catMeta[editingRuleFor]?.label ?? editingRuleFor}
            </span>
            <span class="flex-1"></span>
            <button
              type="button"
              class="rounded-sm p-0.5 text-text3 hover:bg-surface2 hover:text-foreground"
              onclick={() => (editingRuleFor = null)}
              aria-label="Close rule editor"
              title="Close"
            >
              <X class="h-3 w-3" />
            </button>
          </div>
          <LabelRuleCard label={editingRuleFor} sample={SAMPLES[editingRuleFor] ?? ''} />
        </div>
      {/if}

      <!-- Customised rule shortcuts -->
      {#if customisedLabels.length > 0 && !editingRuleFor}
        <div>
          <div class="mb-1 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
            Rules ({customisedLabels.length})
          </div>
          <div class="flex flex-wrap gap-1">
            {#each customisedLabels as label (label)}
              <button
                type="button"
                class="flex items-center gap-1 rounded-sm border border-border bg-background/40 px-1.5 py-0.5 text-[10.5px] text-foreground hover:border-primary"
                onclick={() => (editingRuleFor = label)}
              >
                <span
                  class="h-2 w-[2px] rounded-[1px]"
                  style:background={editor.catMeta[label]?.color ?? '#888'}
                ></span>
                <span class="truncate">{editor.catMeta[label]?.label ?? label}</span>
              </button>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Add custom label -->
      <details class="rounded-md border border-dashed border-border bg-background/40 p-2">
        <summary class="cursor-pointer text-[10.5px] text-muted-foreground">
          + Add custom label
        </summary>
        <div class="mt-2 grid grid-cols-[1fr_1fr_auto] gap-1.5">
          <input
            type="text"
            placeholder="key"
            class="min-w-0 rounded-sm border border-border bg-background px-1.5 py-1 text-[10.5px] text-foreground"
            bind:value={newKey}
          />
          <input
            type="text"
            placeholder="Display name"
            class="min-w-0 rounded-sm border border-border bg-background px-1.5 py-1 text-[10.5px] text-foreground"
            bind:value={newName}
          />
          <input
            type="color"
            class="h-7 w-9 cursor-pointer rounded-sm border border-border bg-transparent p-0.5"
            bind:value={newColor}
          />
        </div>
        <textarea
          rows="2"
          placeholder='Description ("Project code, 4 digits")'
          class="mt-1.5 min-w-0 w-full resize-y rounded-sm border border-border bg-background px-1.5 py-1 text-[10.5px] text-foreground"
          bind:value={newDesc}
        ></textarea>
        <div class="mt-1.5 flex items-center gap-2">
          <button
            type="button"
            class="flex items-center gap-1 rounded-sm border border-primary bg-primary/10 px-2 py-1 text-[10.5px] text-foreground hover:bg-primary/20"
            onclick={addCustom}
            disabled={!newKey.trim()}
          >
            <Plus class="h-3 w-3" /> Add
          </button>
          {#if addError}
            <span class="text-[10px] text-destructive">{addError}</span>
          {/if}
        </div>
      </details>

      <!-- Last detected spans from the most recent Run. -->
      <details class="rounded border border-border" open={editor.spans.length > 0}>
        <summary class="cursor-pointer list-none px-2.5 py-1.5 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3 hover:text-foreground">
          Last spans
          <span class="ml-1 font-mono tabular-nums text-muted-foreground">
            ({editor.spans.length})
          </span>
        </summary>
        {#if editor.spans.length === 0}
          <div class="border-t border-border px-2.5 py-2 text-[10.5px] text-muted-foreground">
            Press Run to populate this. Empty here = GLiNER2 returned no spans
            for the current threshold + labels + post-filter combo.
          </div>
        {:else}
          <ul class="max-h-64 divide-y divide-border overflow-auto border-t border-border">
            {#each editor.spans as span, i (i)}
              <li class="grid grid-cols-[auto_1fr_auto] items-center gap-2 px-2.5 py-1 text-[11px]">
                <span class="rounded-sm bg-background/40 px-1 font-mono text-[10px] text-muted-foreground">
                  {span.label}
                </span>
                <span class="truncate text-foreground" title={span.text}>{span.text}</span>
                <span class="font-mono text-[10px] tabular-nums text-text3">
                  {(span.confidence ?? 0).toFixed(2)}
                </span>
              </li>
            {/each}
          </ul>
        {/if}
      </details>
    </div>
  {:else if selectedId === 'input'}
    <header class="border-b border-border px-4 py-3">
      <div class="text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">Input</div>
      <div class="flex items-center gap-2">
        <Upload class="h-4 w-4 text-primary" />
        <div class="text-[13.5px] font-semibold text-foreground">Source images</div>
      </div>
      <p class="mt-1 text-[11px] text-muted-foreground">
        Drop PNG / JPG / WebP / PDF here. PDFs are rasterised page-by-page. The carousel below shows everything currently loaded.
      </p>
    </header>

    <div class="flex flex-1 flex-col gap-3 overflow-hidden p-3">
      <!-- Append / Replace toggle. Same flag editor.uploadFiles() reads. -->
      <div class="flex items-center justify-between rounded border border-border bg-background/40 px-2.5 py-1.5">
        <span class="text-[11px] text-muted-foreground">On upload</span>
        <div class="flex items-center gap-0.5 rounded-sm border border-border bg-card p-0.5">
          <button
            type="button"
            class="rounded-sm px-2 py-0.5 text-[10.5px] text-muted-foreground transition-colors data-[active=true]:bg-accent data-[active=true]:text-accent-foreground"
            data-active={appendMode === true}
            onclick={() => (appendMode = true)}
          >
            Append
          </button>
          <button
            type="button"
            class="rounded-sm px-2 py-0.5 text-[10.5px] text-muted-foreground transition-colors data-[active=true]:bg-accent data-[active=true]:text-accent-foreground"
            data-active={appendMode === false}
            onclick={() => (appendMode = false)}
          >
            Replace
          </button>
        </div>
      </div>

      <!-- Drop-zone — same UX as the canvas's empty-state dropzone. -->
      <label
        for="pipeline-input-file"
        class="flex cursor-pointer flex-col items-center justify-center gap-2 rounded border border-dashed bg-background/40 px-4 py-6 text-center transition-colors hover:border-primary/60 hover:bg-background/60"
        class:border-primary={inputDragging}
        class:bg-primary={false}
        class:border-border={!inputDragging}
        ondragover={(e) => {
          e.preventDefault();
          inputDragging = true;
        }}
        ondragleave={() => (inputDragging = false)}
        ondrop={onInputDrop}
      >
        <Upload class="h-5 w-5 text-text3" />
        <div class="text-[11.5px] font-medium text-foreground">Drop files here</div>
        <div class="text-[10.5px] text-muted-foreground">or click to choose</div>
        <input
          id="pipeline-input-file"
          type="file"
          multiple
          accept="image/*,application/pdf"
          class="sr-only"
          onchange={onInputPick}
        />
      </label>

      <!-- Loaded pages carousel — click-to-go-to-page mirrors the bottom strip. -->
      <div class="flex min-h-0 flex-1 flex-col rounded border border-border">
        <div class="flex items-center justify-between border-b border-border px-2.5 py-1.5">
          <span class="text-[10px] font-medium uppercase tracking-[0.08em] text-text3">
            Loaded
          </span>
          <span class="font-mono text-[10.5px] tabular-nums text-muted-foreground">
            {editor.pages.length}
          </span>
        </div>
        {#if editor.pages.length === 0}
          <div class="flex flex-1 items-center justify-center px-4 py-6 text-center text-[11px] text-muted-foreground">
            No images uploaded yet.
          </div>
        {:else}
          <div class="grid flex-1 grid-cols-2 gap-2 overflow-y-auto p-2">
            {#each editor.pages as p, i (p.objectUrl)}
              <button
                type="button"
                class="group relative aspect-square overflow-hidden rounded-md border bg-background transition-colors data-[active=true]:border-primary"
                class:border-border={editor.activeIdx !== i}
                data-active={editor.activeIdx === i}
                onclick={() => editor.goTo(i)}
                title={p.filename}
              >
                <canvas
                  class="block h-full w-full object-cover"
                  {@attach (node: HTMLCanvasElement) => paintThumbnail(node, i)}
                  aria-label={p.filename}
                ></canvas>
                <span
                  class="absolute bottom-0 left-0 right-0 truncate bg-background/85 px-1 py-px text-center font-mono text-[9.5px] text-muted-foreground"
                >
                  {i + 1} · {p.filename}
                </span>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {:else if selectedId === 'output'}
    <header class="border-b border-border px-4 py-3">
      <div class="text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">Output</div>
      <div class="flex items-center gap-2">
        <FileJson class="h-4 w-4 text-primary" />
        <div class="text-[13.5px] font-semibold text-foreground">Last response</div>
      </div>
      <p class="mt-1 text-[11px] text-muted-foreground">
        Raw payload returned by <code>/anonymize_screenshot</code> for the active page. Use it to verify which settings actually took effect.
      </p>
    </header>

    <div class="flex flex-1 flex-col gap-3 overflow-hidden p-3">
      <!-- Summary chips: counts per category from the last run. -->
      <div class="grid grid-cols-3 gap-2 text-center text-[10.5px]">
        <div class="rounded border border-border bg-background/40 px-2 py-1.5">
          <div class="font-mono text-[15px] tabular-nums text-foreground">{lastResponse.spans.length}</div>
          <div class="mt-0.5 text-text3">spans</div>
        </div>
        <div class="rounded border border-border bg-background/40 px-2 py-1.5">
          <div class="font-mono text-[15px] tabular-nums text-foreground">{lastResponse.boxes.length}</div>
          <div class="mt-0.5 text-text3">boxes</div>
        </div>
        <div class="rounded border border-border bg-background/40 px-2 py-1.5">
          <div class="font-mono text-[15px] tabular-nums text-foreground">{lastResponse.ocrLines.length}</div>
          <div class="mt-0.5 text-text3">ocr lines</div>
        </div>
      </div>

      {#if lastResponse.spans.length > 0}
        <!-- Per-label tally — fastest sanity check that a knob changed
             behaviour (e.g. URL appearing/disappearing after relaxing the
             regex). -->
        <div class="rounded border border-border">
          <div class="border-b border-border px-2.5 py-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-text3">
            By label
          </div>
          <ul class="divide-y divide-border">
            {#each Object.entries(lastResponse.spans.reduce((acc: Record<string, number>, s) => { acc[s.label] = (acc[s.label] ?? 0) + 1; return acc; }, {})).sort((a, b) => b[1] - a[1]) as [label, count] (label)}
              <li class="flex items-center justify-between px-2.5 py-1 font-mono text-[11px]">
                <span class="truncate text-foreground">{label}</span>
                <span class="tabular-nums text-text3">{count}</span>
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      <!-- JSON block + copy. Limit height so the panel stays scrollable. -->
      <div class="flex min-h-0 flex-1 flex-col rounded border border-border">
        <div class="flex items-center justify-between border-b border-border px-2.5 py-1.5">
          <span class="text-[10px] font-medium uppercase tracking-[0.08em] text-text3">JSON</span>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[10.5px] text-muted-foreground hover:bg-accent hover:text-foreground"
            onclick={copyResponseJson}
            disabled={lastResponse.spans.length === 0 && lastResponse.boxes.length === 0 && lastResponse.ocrLines.length === 0}
          >
            <Copy class="h-3 w-3" />
            {copyState === 'copied' ? 'Copied' : 'Copy'}
          </button>
        </div>
        <pre class="m-0 min-h-0 flex-1 overflow-auto bg-background/40 p-2.5 font-mono text-[10.5px] leading-snug text-foreground"><code>{JSON.stringify(lastResponse, null, 2)}</code></pre>
      </div>
    </div>
  {:else}
    <header class="border-b border-border px-4 py-3">
      <div class="text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">Node</div>
      <div class="text-[13.5px] font-semibold text-foreground">{selectedId}</div>
    </header>
    <div class="flex flex-1 items-center justify-center px-6 text-center text-[11.5px] text-muted-foreground">
      No settings for this node.
    </div>
  {/if}
</aside>
