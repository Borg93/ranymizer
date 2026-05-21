<script lang="ts">
/**
 * Right-side properties panel. Shows the full settings form for whichever
 * node is currently selected in the SvelteFlow graph. Mirror of Figma's
 * right panel — nodes stay light, the inspector carries the noisy forms.
 */
import * as v from 'valibot';
import { Plus, Settings2, Trash2, X } from 'lucide-svelte';
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
  if (DEFAULT_PII_LABELS.includes(key) || gliner.customLabels[key]) {
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
